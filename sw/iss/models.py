from bisect import bisect_right
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

byteBits = 8
uartFrameBits = 10


class ProtocolError(Exception):
    pass


class PinRecorder:
    def __init__(self, pin: int) -> None:
        self.pin = pin
        self.edges: list[tuple[int, int]] = []
        self._edgeCycles: list[int] = []

    def sample(self, cycle: int, outputs: int) -> None:
        level = (outputs >> self.pin) & 1
        if not self.edges or self.edges[-1][1] != level:
            self.edges.append((cycle, level))
            self._edgeCycles.append(cycle)

    def levelAt(self, cycle: int) -> int:
        index = bisect_right(self._edgeCycles, cycle) - 1
        return self.edges[index][1] if index >= 0 else 0

    def pulses(self) -> list[tuple[int, int]]:
        return [
            (level, nextCycle - cycle)
            for (cycle, level), (nextCycle, _) in zip(self.edges, self.edges[1:])
        ]


@dataclass(frozen=True)
class UartFrame:
    data: int
    stopLevel: int = 1


class UartSource:
    def __init__(
        self, frames: Sequence[UartFrame], cyclesPerBit: float, startCycle: int
    ) -> None:
        self.frames = frames
        self.cyclesPerBit = cyclesPerBit
        self.startCycle = startCycle

    def level(self, cycle: int) -> int:
        bitIndex = int((cycle - self.startCycle) // self.cyclesPerBit)
        frameIndex, bitInFrame = divmod(bitIndex, uartFrameBits)
        if cycle < self.startCycle or frameIndex >= len(self.frames):
            return 1
        frame = self.frames[frameIndex]
        if bitInFrame == 0:
            return 0
        if bitInFrame > byteBits:
            return frame.stopLevel
        return (frame.data >> (bitInFrame - 1)) & 1


def decodeUart(recorder: PinRecorder, cyclesPerBit: int, fromCycle: int = 1) -> list[int]:
    received = []
    for edgeCycle, level in recorder.edges:
        if level != 0 or edgeCycle < fromCycle:
            continue
        data = 0
        for bit in range(byteBits):
            center = edgeCycle + cyclesPerBit * (bit + 1) + cyclesPerBit // 2
            data |= recorder.levelAt(center) << bit
        stopCenter = edgeCycle + cyclesPerBit * (uartFrameBits - 1) + cyclesPerBit // 2
        if recorder.levelAt(stopCenter) != 1:
            raise ProtocolError(f"framing error in the frame at cycle {edgeCycle}")
        received.append(data)
        fromCycle = stopCenter
    return received


class SpiTarget:
    def __init__(self, responses: Iterable[int]) -> None:
        self._responses = deque(responses)
        self.received: list[int] = []
        self._rxShift = 0
        self._rxBits = 0
        self._txShift = self._nextResponse()
        self._previousSck = 0

    def _nextResponse(self) -> int:
        return self._responses.popleft() if self._responses else 0

    @property
    def miso(self) -> int:
        return (self._txShift >> 7) & 1

    def update(self, sck: int, mosi: int) -> None:
        if sck and not self._previousSck:
            self._rxShift = ((self._rxShift << 1) | mosi) & 0xFF
            self._rxBits += 1
            if self._rxBits == byteBits:
                self.received.append(self._rxShift)
                self._rxBits = 0
        if self._previousSck and not sck:
            self._txShift = (self._txShift << 1) & 0xFF
            if self._rxBits == 0:
                self._txShift = self._nextResponse()
        self._previousSck = sck


i2cStartBit = 15
i2cStopBit = 14
i2cDataShift = 6
i2cAckShift = 5
i2cResultBits = byteBits + 1


def i2cWrite(data: int, start: bool = False, stop: bool = False) -> int:
    return (
        (int(start) << i2cStartBit)
        | (int(stop) << i2cStopBit)
        | ((data & 0xFF) << i2cDataShift)
        | (1 << i2cAckShift)
    )


def i2cRead(ack: bool, stop: bool = False) -> int:
    return (int(stop) << i2cStopBit) | (0xFF << i2cDataShift) | (int(not ack) << i2cAckShift)


def i2cResult(word: int) -> tuple[int, bool]:
    return (word >> 1) & 0xFF, not word & 1


class I2cTarget:
    def __init__(self, address: int, readData: Iterable[int] = (), stretchCycles: int = 0) -> None:
        self.address = address
        self.stretchCycles = stretchCycles
        self.received: list[int] = []
        self.controllerAcks: list[bool] = []
        self.starts = 0
        self.stops = 0
        self.sdaDrive = False
        self.sclDrive = False
        self._readData = deque(readData)
        self._state = "idle"
        self._isRead = False
        self._clockCount = 0
        self._shift = 0
        self._txByte = 0
        self._stretchLeft = 0
        self._previousScl = 1
        self._previousSda = 1

    def update(self, scl: int, sda: int) -> None:
        if self._stretchLeft:
            self._stretchLeft -= 1
            self.sclDrive = self._stretchLeft > 0
        if scl and self._previousScl and sda != self._previousSda:
            self._busCondition(sda)
        elif scl and not self._previousScl:
            self._rising(sda)
        elif self._previousScl and not scl:
            self._falling()
        self._previousScl = scl
        self._previousSda = sda

    def _busCondition(self, sda: int) -> None:
        self.sdaDrive = False
        self._clockCount = 0
        self._shift = 0
        if sda:
            self.stops += 1
            self._state = "idle"
        else:
            self.starts += 1
            self._state = "address"

    def _rising(self, sda: int) -> None:
        if self._state in ("idle", "ignore"):
            return
        self._clockCount += 1
        if self._clockCount <= byteBits and self._state != "read":
            self._shift = ((self._shift << 1) | sda) & 0xFF
        if self._clockCount == i2cResultBits and self._state == "read":
            self.controllerAcks.append(not sda)

    def _falling(self) -> None:
        if self._state in ("idle", "ignore") or self._clockCount == 0:
            return
        if self._clockCount == byteBits:
            self._endOfByte()
        elif self._clockCount == i2cResultBits:
            self._endOfAck()
        elif self._state == "read":
            self.sdaDrive = not (self._txByte >> (byteBits - 1 - self._clockCount)) & 1

    def _endOfByte(self) -> None:
        if self._state == "address":
            if self._shift >> 1 != self.address:
                self._state = "ignore"
                return
            self._isRead = bool(self._shift & 1)
            self.sdaDrive = True
        elif self._state == "write":
            self.received.append(self._shift)
            self.sdaDrive = True
        else:
            self.sdaDrive = False

    def _endOfAck(self) -> None:
        self._clockCount = 0
        self._shift = 0
        self.sdaDrive = False
        if self._state == "address":
            self._state = "read" if self._isRead else "write"
        elif self._state == "read" and not self.controllerAcks[-1]:
            self._state = "ignore"
            return
        if self._state == "read":
            self._txByte = self._readData.popleft() if self._readData else 0xFF
            self.sdaDrive = not (self._txByte >> (byteBits - 1)) & 1
        if self.stretchCycles:
            self.sclDrive = True
            self._stretchLeft = self.stretchCycles


ps2FrameBits = 11
ps2HostBits = 10
ps2ResultShift = 6
ps2StopBit = 9


def ps2Parity(data: int) -> int:
    return 1 - bin(data & 0xFF).count("1") % 2


def ps2HostWord(data: int) -> int:
    return (data & 0xFF) | (ps2Parity(data) << byteBits) | (1 << ps2StopBit)


def ps2Result(word: int) -> tuple[int, bool]:
    frame = word >> ps2ResultShift
    data = frame & 0xFF
    isValid = (frame >> byteBits) & 1 == ps2Parity(data) and bool((frame >> ps2StopBit) & 1)
    return data, isValid


class Ps2Device:
    def __init__(
        self,
        halfPeriod: int,
        outgoing: Iterable[int] = (),
        replies: dict[int, Sequence[int]] | None = None,
        requestCycles: int = 0,
        gapCycles: int = 0,
        badParity: Iterable[int] = (),
    ) -> None:
        self.halfPeriod = halfPeriod
        self.requestCycles = requestCycles or 2 * halfPeriod
        self.gapCycles = gapCycles or 2 * halfPeriod
        self.replies = replies or {}
        self.received: list[int] = []
        self.receiveErrors = 0
        self.clkDrive = False
        self.dataDrive = False
        self._outgoing = deque(outgoing)
        self._badParity = set(badParity)
        self._state = "idle"
        self._bits: list[int] = []
        self._time = 0
        self._lowCycles = 0
        self._idleCycles = 0
        self._sentCount = 0

    def update(self, clk: int, data: int) -> None:
        handlers = {
            "idle": self._idle,
            "request": self._request,
            "sending": self._sending,
            "receiving": self._receiving,
        }
        handlers[self._state](clk, data)

    def _idle(self, clk: int, data: int) -> None:
        self._lowCycles = self._lowCycles + 1 if not clk else 0
        if self._lowCycles >= self.requestCycles and not data:
            self._state = "request"
            return
        self._idleCycles = self._idleCycles + 1 if clk and data else 0
        if self._outgoing and self._idleCycles >= self.gapCycles:
            value = self._outgoing.popleft()
            parity = ps2Parity(value) ^ int(self._sentCount in self._badParity)
            self._sentCount += 1
            self._bits = [0, *[(value >> bit) & 1 for bit in range(byteBits)], parity, 1]
            self._time = 0
            self._state = "sending"

    def _sending(self, clk: int, data: int) -> None:
        bitIndex, phase = divmod(self._time, 2 * self.halfPeriod)
        if bitIndex >= ps2FrameBits:
            self.clkDrive = False
            self.dataDrive = False
            self._idleCycles = 0
            self._state = "idle"
            return
        self.dataDrive = not self._bits[bitIndex]
        self.clkDrive = phase >= self.halfPeriod
        self._time += 1

    def _request(self, clk: int, data: int) -> None:
        if clk:
            self._bits = []
            self._time = 0
            self._state = "receiving"

    def _receiving(self, clk: int, data: int) -> None:
        bitIndex, phase = divmod(self._time, 2 * self.halfPeriod)
        self._time += 1
        if bitIndex > ps2HostBits:
            self.clkDrive = False
            self.dataDrive = False
            self._finishReceive()
            return
        self.clkDrive = phase < self.halfPeriod
        if bitIndex < ps2HostBits and phase == self.halfPeriod:
            self._bits.append(data)
        self.dataDrive = bitIndex == ps2HostBits

    def _finishReceive(self) -> None:
        value = sum(bit << index for index, bit in enumerate(self._bits[:byteBits]))
        isValid = self._bits[byteBits] == ps2Parity(value) and self._bits[ps2StopBit] == 1
        if isValid:
            self.received.append(value)
            self._outgoing.extend(self.replies.get(value, ()))
        else:
            self.receiveErrors += 1
        self._idleCycles = 0
        self._state = "idle"


jtagPairsPerWord = 8
jtagTdoShift = 8
jtagIrLength = 4
jtagIdcodeInstruction = 0b0001
jtagBypassInstruction = 0b1111
jtagIdcodeLength = 32

tapNext: dict[str, tuple[str, str]] = {
    "testLogicReset": ("runTestIdle", "testLogicReset"),
    "runTestIdle": ("runTestIdle", "selectDr"),
    "selectDr": ("captureDr", "selectIr"),
    "captureDr": ("shiftDr", "exit1Dr"),
    "shiftDr": ("shiftDr", "exit1Dr"),
    "exit1Dr": ("pauseDr", "updateDr"),
    "pauseDr": ("pauseDr", "exit2Dr"),
    "exit2Dr": ("shiftDr", "updateDr"),
    "updateDr": ("runTestIdle", "selectDr"),
    "selectIr": ("captureIr", "testLogicReset"),
    "captureIr": ("shiftIr", "exit1Ir"),
    "shiftIr": ("shiftIr", "exit1Ir"),
    "exit1Ir": ("pauseIr", "updateIr"),
    "pauseIr": ("pauseIr", "exit2Ir"),
    "exit2Ir": ("shiftIr", "updateIr"),
    "updateIr": ("runTestIdle", "selectDr"),
}


def jtagWords(pairs: Sequence[tuple[int, int]]) -> list[int]:
    words = []
    for first in range(0, len(pairs), jtagPairsPerWord):
        word = 0
        for index, (tms, tdi) in enumerate(pairs[first : first + jtagPairsPerWord]):
            word |= ((tms << 1) | tdi) << (2 * index)
        words.append(word)
    return words


def jtagTdoBits(words: Sequence[int]) -> list[int]:
    return [(word >> (jtagTdoShift + bit)) & 1 for word in words for bit in range(byteBits)]


def jtagShift(tdiBits: Sequence[int], exitAfter: bool = True) -> list[tuple[int, int]]:
    last = len(tdiBits) - 1
    return [(int(exitAfter and index == last), bit) for index, bit in enumerate(tdiBits)]


class JtagTap:
    def __init__(self, idcode: int) -> None:
        self.idcode = idcode
        self.state = "testLogicReset"
        self.instruction = jtagIdcodeInstruction
        self.tdo = 0
        self._shift = 0
        self._length = 0
        self._previousTck = 0
        self.states: list[str] = []

    def update(self, tck: int, tms: int, tdi: int) -> None:
        if tck and not self._previousTck:
            self._rising(tms, tdi)
        elif self._previousTck and not tck and self.state in ("shiftDr", "shiftIr"):
            self.tdo = self._shift & 1
        self._previousTck = tck

    def _rising(self, tms: int, tdi: int) -> None:
        if self.state in ("shiftDr", "shiftIr"):
            self._shift = (self._shift >> 1) | (tdi << (self._length - 1))
        self.state = tapNext[self.state][tms]
        self.states.append(self.state)
        if self.state == "testLogicReset":
            self.instruction = jtagIdcodeInstruction
        elif self.state == "captureDr":
            isIdcode = self.instruction == jtagIdcodeInstruction
            self._shift = self.idcode if isIdcode else 0
            self._length = jtagIdcodeLength if isIdcode else 1
        elif self.state == "captureIr":
            self._shift = 0b0001
            self._length = jtagIrLength
        elif self.state == "updateIr":
            self.instruction = self._shift & ((1 << jtagIrLength) - 1)
