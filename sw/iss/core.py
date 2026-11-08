from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from asm import isa
from asm.assembler import Program

dataBits = 16
dataMask = (1 << dataBits) - 1
fifoDepth = 4
pinMask = isa.pinCount - 1
offsetBits = 6


class IssError(Exception):
    pass


class FlagBank:
    def __init__(self) -> None:
        self.value = 0

    def isSet(self, index: int) -> bool:
        return bool((self.value >> index) & 1)

    def set(self, index: int) -> None:
        self.value |= 1 << index

    def clear(self, index: int) -> None:
        self.value &= ~(1 << index)


@dataclass(frozen=True)
class CoreConfig:
    clkDiv: int = 1
    outBase: int = 0
    outCount: int = 0
    setBase: int = 0
    setCount: int = 0
    sideBase: int = 0
    inBase: int = 0
    jmpPin: int = 0
    outShiftRight: bool = True
    inShiftRight: bool = True
    autoPull: bool = False
    pullThreshold: int = dataBits
    autoPush: bool = False
    pushThreshold: int = dataBits

    def __post_init__(self) -> None:
        _requireRange("clkDiv", self.clkDiv, 1, dataMask)
        for name in ("outBase", "setBase", "sideBase", "inBase", "jmpPin"):
            _requireRange(name, getattr(self, name), 0, pinMask)
        _requireRange("outCount", self.outCount, 0, dataBits)
        _requireRange("setCount", self.setCount, 0, 6)
        _requireRange("pullThreshold", self.pullThreshold, 1, dataBits)
        _requireRange("pushThreshold", self.pushThreshold, 1, dataBits)


def _requireRange(name: str, value: int, low: int, high: int) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name} must be {low} to {high}, not {value}")


def _reverseBits(value: int) -> int:
    return int(f"{value:0{dataBits}b}"[::-1], 2)


def _writeField(register: int, base: int, count: int, value: int) -> int:
    for bit in range(count):
        pin = (base + bit) & pinMask
        register = (register & ~(1 << pin)) | (((value >> bit) & 1) << pin)
    return register


class Core:
    def __init__(self, program: Program, config: CoreConfig, flags: FlagBank) -> None:
        self.config = config
        self.sideSet = program.sideSet
        self.wrapBottom = program.wrapBottom
        self.wrapTop = program.wrapTop
        self.memory = list(program.words) + [0] * (isa.programWords - len(program.words))
        self.flags = flags
        self.pc = 0
        self.x = 0
        self.y = 0
        self.t = 0
        self.isr = 0
        self.osr = 0
        self.isrCount = 0
        self.osrCount = dataBits
        self.txFifo: deque[int] = deque()
        self.rxFifo: deque[int] = deque()
        self.pinOut = 0
        self.pinDir = 0
        self.timeoutFlag = False
        self._divCount = 0
        self._delayCount = 0
        self._isStalled = False
        self._waitTicks = 0
        self._pendingExec: int | None = None
        self._jumpTarget: int | None = None
        self._inputs = 0
        self._hostWriteWord: int | None = None
        self._isHostReadPending = False
        self._handlers: dict[isa.Opcode, Callable[[int], bool]] = {
            isa.Opcode.jmp: self._jmp,
            isa.Opcode.wait: self._wait,
            isa.Opcode.shiftIn: self._shiftIn,
            isa.Opcode.shiftOut: self._shiftOut,
            isa.Opcode.pushPull: self._pushPull,
            isa.Opcode.mov: self._mov,
            isa.Opcode.set: self._set,
            isa.Opcode.flag: self._flag,
        }

    def hostWrite(self, word: int) -> bool:
        if len(self.txFifo) >= fifoDepth or self._hostWriteWord is not None:
            return False
        self._hostWriteWord = word & dataMask
        return True

    def hostRead(self) -> int | None:
        if not self.rxFifo or self._isHostReadPending:
            return None
        self._isHostReadPending = True
        return self.rxFifo[0]

    @property
    def status(self) -> int:
        txEmpty = int(not self.txFifo)
        rxFull = int(len(self.rxFifo) >= fifoDepth)
        return txEmpty | (rxFull << 1) | (int(self.timeoutFlag) << 2) | (self.flags.value << 8)

    def clock(self, inputs: int) -> None:
        isTick = self._divCount == 0
        self._divCount = (self._divCount + 1) % self.config.clkDiv
        if isTick:
            self._tick(inputs)
        self._applyHostAccess()

    def _applyHostAccess(self) -> None:
        if self._isHostReadPending:
            self.rxFifo.popleft()
            self._isHostReadPending = False
        if self._hostWriteWord is not None:
            self.txFifo.append(self._hostWriteWord)
            self._hostWriteWord = None

    def _tick(self, inputs: int) -> None:
        if self._delayCount:
            self._delayCount -= 1
            return
        self._inputs = inputs
        execWord = self._pendingExec
        self._pendingExec = None
        word = self.memory[self.pc] if execWord is None else execWord
        opcode = isa.Opcode(word >> isa.opcodeShift)
        side, delay = self.sideSet.unpackTiming((word >> isa.timingShift) & isa.timingMask)
        if side is not None:
            self._writeSideSet(side)
        self._jumpTarget = None
        if not self._handlers[opcode](word & isa.operandMask):
            self._isStalled = True
            self._pendingExec = execWord
            return
        self._isStalled = False
        self._advancePc(isExec=execWord is not None)
        if self._pendingExec is None:
            self._delayCount = delay

    def _advancePc(self, isExec: bool) -> None:
        if self._jumpTarget is not None:
            self.pc = self._jumpTarget
        elif isExec:
            return
        elif self.pc == self.wrapTop:
            self.pc = self.wrapBottom
        else:
            self.pc = (self.pc + 1) % isa.programWords

    def _writeSideSet(self, side: int) -> None:
        base, count = self.config.sideBase, self.sideSet.sideCount
        if self.sideSet.sidePinDir:
            self.pinDir = _writeField(self.pinDir, base, count, side)
        else:
            self.pinOut = _writeField(self.pinOut, base, count, side)

    def _readPins(self) -> int:
        base = self.config.inBase
        rotated = (self._inputs >> base) | (self._inputs << (isa.pinCount - base))
        return rotated & dataMask

    def _inputLevel(self, pin: int) -> int:
        return (self._inputs >> (pin & pinMask)) & 1

    def _jmp(self, operands: int) -> bool:
        condition = isa.JmpCondition((operands >> isa.fieldShift) & 7)
        offset = operands & ((1 << offsetBits) - 1)
        if offset >> (offsetBits - 1):
            offset -= 1 << offsetBits
        if self._isJumpTaken(condition):
            self._jumpTarget = (self.pc + offset) % isa.programWords
        return True

    def _isJumpTaken(self, condition: isa.JmpCondition) -> bool:
        if condition == isa.JmpCondition.xDecrement:
            isTaken = self.x != 0
            self.x = (self.x - 1) & dataMask
            return isTaken
        if condition == isa.JmpCondition.yDecrement:
            isTaken = self.y != 0
            self.y = (self.y - 1) & dataMask
            return isTaken
        conditions = {
            isa.JmpCondition.always: True,
            isa.JmpCondition.xZero: self.x == 0,
            isa.JmpCondition.xNotEqualY: self.x != self.y,
            isa.JmpCondition.pin: bool(self._inputLevel(self.config.jmpPin)),
            isa.JmpCondition.osrNotEmpty: self.osrCount < self.config.pullThreshold,
            isa.JmpCondition.timeout: self.timeoutFlag,
        }
        return conditions[condition]

    def _waitLevel(self, source: int, index: int) -> int:
        if source == isa.WaitSource.gpio:
            return self._inputLevel(index)
        if source == isa.WaitSource.pin:
            return self._inputLevel(self.config.inBase + index)
        if source == isa.WaitSource.flag:
            return int(self.flags.isSet(index & (isa.flagCount - 1)))
        raise IssError(f"reserved WAIT source {source} at PC {self.pc}")

    def _wait(self, operands: int) -> bool:
        polarity = (operands >> 8) & 1
        source = (operands >> isa.fieldShift) & 3
        isTimeoutEn = bool((operands >> 5) & 1)
        index = operands & 0x1F
        if not self._isStalled:
            self.timeoutFlag = False
            self._waitTicks = self.t
        if self._waitLevel(source, index) == polarity:
            if source == isa.WaitSource.flag and polarity:
                self.flags.clear(index & (isa.flagCount - 1))
            return True
        if not isTimeoutEn:
            return False
        if self._waitTicks == 0:
            self.timeoutFlag = True
            return True
        self._waitTicks -= 1
        return False

    @staticmethod
    def _bitCount(operands: int) -> int:
        return (operands & (isa.maxBitCount - 1)) or isa.maxBitCount

    def _inData(self, source: int) -> int:
        values = {
            isa.InSource.pins: self._readPins(),
            isa.InSource.x: self.x,
            isa.InSource.y: self.y,
            isa.InSource.null: 0,
            isa.InSource.isr: self.isr,
            isa.InSource.osr: self.osr,
        }
        if source not in values:
            raise IssError(f"reserved IN source {source} at PC {self.pc}")
        return values[isa.InSource(source)]

    def _shiftIn(self, operands: int) -> bool:
        count = self._bitCount(operands)
        isPushDue = (
            self.config.autoPush
            and min(self.isrCount + count, dataBits) >= self.config.pushThreshold
        )
        if isPushDue and len(self.rxFifo) >= fifoDepth:
            return False
        data = self._inData((operands >> isa.fieldShift) & 7) & ((1 << count) - 1)
        if self.config.inShiftRight:
            self.isr = ((self.isr >> count) | (data << (dataBits - count))) & dataMask
        else:
            self.isr = ((self.isr << count) | data) & dataMask
        self.isrCount = min(self.isrCount + count, dataBits)
        if isPushDue:
            self._pushIsr()
        return True

    def _pushIsr(self) -> None:
        self.rxFifo.append(self.isr)
        self._clearIsr()

    def _clearIsr(self) -> None:
        self.isr = 0
        self.isrCount = 0

    def _loadOsr(self, value: int) -> None:
        self.osr = value
        self.osrCount = 0

    def _shiftOut(self, operands: int) -> bool:
        if self.config.autoPull and self.osrCount >= self.config.pullThreshold:
            if not self.txFifo:
                return False
            self._loadOsr(self.txFifo.popleft())
        count = self._bitCount(operands)
        mask = (1 << count) - 1
        if self.config.outShiftRight:
            data = self.osr & mask
            self.osr >>= count
        else:
            data = (self.osr >> (dataBits - count)) & mask
            self.osr = (self.osr << count) & dataMask
        self.osrCount = min(self.osrCount + count, dataBits)
        self._writeOutDestination(isa.OutDestination((operands >> isa.fieldShift) & 7), data, count)
        return True

    def _writeOutPins(self, value: int) -> None:
        self.pinOut = _writeField(self.pinOut, self.config.outBase, self.config.outCount, value)

    def _writeOutDestination(self, destination: isa.OutDestination, data: int, count: int) -> None:
        if destination == isa.OutDestination.pins:
            self._writeOutPins(data)
        elif destination == isa.OutDestination.x:
            self.x = data
        elif destination == isa.OutDestination.y:
            self.y = data
        elif destination == isa.OutDestination.pindirs:
            self.pinDir = _writeField(self.pinDir, self.config.outBase, self.config.outCount, data)
        elif destination == isa.OutDestination.pc:
            self._jumpTarget = data % isa.programWords
        elif destination == isa.OutDestination.isr:
            self.isr = data
            self.isrCount = count
        elif destination == isa.OutDestination.exec:
            self._pendingExec = data

    def _pushPull(self, operands: int) -> bool:
        isPull = bool((operands >> 8) & 1)
        isConditional = bool((operands >> 7) & 1)
        isBlocking = bool((operands >> isa.fieldShift) & 1)
        if isPull:
            return self._pull(isConditional, isBlocking)
        return self._push(isConditional, isBlocking)

    def _push(self, isConditional: bool, isBlocking: bool) -> bool:
        if isConditional and self.isrCount < self.config.pushThreshold:
            return True
        if len(self.rxFifo) < fifoDepth:
            self._pushIsr()
            return True
        if isBlocking:
            return False
        self._clearIsr()
        return True

    def _pull(self, isConditional: bool, isBlocking: bool) -> bool:
        if isConditional and self.osrCount < self.config.pullThreshold:
            return True
        if self.txFifo:
            self._loadOsr(self.txFifo.popleft())
            return True
        if isBlocking:
            return False
        self._loadOsr(self.x)
        return True

    def _movSourceValue(self, source: isa.MovSource) -> int:
        values = {
            isa.MovSource.pins: self._readPins(),
            isa.MovSource.x: self.x,
            isa.MovSource.y: self.y,
            isa.MovSource.null: 0,
            isa.MovSource.status: self.status,
            isa.MovSource.isr: self.isr,
            isa.MovSource.osr: self.osr,
            isa.MovSource.t: self.t,
        }
        return values[source]

    def _aluOperand(self, destination: isa.MovDestination) -> int:
        operands = {
            isa.MovDestination.x: self.x,
            isa.MovDestination.y: self.y,
            isa.MovDestination.t: self.t,
        }
        if destination not in operands:
            raise IssError(f"MOV operation needs destination X, Y, or T at PC {self.pc}")
        return operands[destination]

    def _movResult(
        self, operation: isa.MovOperation, destination: isa.MovDestination, value: int
    ) -> int:
        if operation == isa.MovOperation.copy:
            return value
        if operation == isa.MovOperation.invert:
            return ~value & dataMask
        if operation == isa.MovOperation.reverse:
            return _reverseBits(value)
        first = self._aluOperand(destination)
        results = {
            isa.MovOperation.add: first + value,
            isa.MovOperation.subtract: first - value,
            isa.MovOperation.bitAnd: first & value,
            isa.MovOperation.bitOr: first | value,
            isa.MovOperation.bitXor: first ^ value,
        }
        return results[operation] & dataMask

    def _mov(self, operands: int) -> bool:
        destination = isa.MovDestination((operands >> isa.fieldShift) & 7)
        operation = isa.MovOperation((operands >> 3) & 7)
        value = self._movSourceValue(isa.MovSource(operands & 7))
        result = self._movResult(operation, destination, value)
        if destination == isa.MovDestination.pins:
            self._writeOutPins(result)
        elif destination == isa.MovDestination.x:
            self.x = result
        elif destination == isa.MovDestination.y:
            self.y = result
        elif destination == isa.MovDestination.t:
            self.t = result
        elif destination == isa.MovDestination.exec:
            self._pendingExec = result
        elif destination == isa.MovDestination.pc:
            self._jumpTarget = result % isa.programWords
        elif destination == isa.MovDestination.isr:
            self.isr = result
            self.isrCount = 0
        else:
            self._loadOsr(result)
        return True

    def _set(self, operands: int) -> bool:
        destination = (operands >> isa.fieldShift) & 7
        data = operands & isa.setDataMax
        base, count = self.config.setBase, self.config.setCount
        if destination == isa.SetDestination.pins:
            self.pinOut = _writeField(self.pinOut, base, count, data)
        elif destination == isa.SetDestination.x:
            self.x = data
        elif destination == isa.SetDestination.y:
            self.y = data
        elif destination == isa.SetDestination.t:
            self.t = data
        elif destination == isa.SetDestination.pindirs:
            self.pinDir = _writeField(self.pinDir, base, count, data)
        else:
            raise IssError(f"reserved SET destination {destination} at PC {self.pc}")
        return True

    def _flag(self, operands: int) -> bool:
        operation = (operands >> 7) & 3
        index = operands & (isa.flagCount - 1)
        if operation == isa.FlagOperation.set:
            self.flags.set(index)
            return True
        if operation == isa.FlagOperation.clear:
            self.flags.clear(index)
            return True
        if operation == isa.FlagOperation.wait:
            if not self._isStalled:
                self.flags.set(index)
            return not self.flags.isSet(index)
        raise IssError(f"reserved FLAG operation {operation} at PC {self.pc}")
