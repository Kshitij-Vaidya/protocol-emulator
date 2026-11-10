from collections import Counter
from dataclasses import dataclass
from enum import IntEnum

from asm import isa

dataMask = 0xFFFF
fifoDepth = 4
bitCountBins = ("1", "15", "16", "other")


@dataclass(frozen=True)
class ExecuteSample:
    instr: int
    pc: int
    jmpTaken: bool
    aluFirst: int
    movSource: int
    refill: bool
    pushDue: bool
    sideActive: bool
    delay: int
    wasStalled: bool


@dataclass(frozen=True)
class StateSample:
    pc: int
    isStalled: bool
    timeoutFlag: bool
    txLevel: int
    rxLevel: int
    pinDir: int


def _names(enum: type[IntEnum]) -> list[str]:
    return [member.name for member in enum]


def _bitCountBin(operands: int) -> str:
    count = operands & 0xF
    if count == 0:
        return "16"
    return str(count) if count in (1, 15) else "other"


coverBins: dict[str, list[str]] = {
    "opcode": _names(isa.Opcode),
    "jmp": [
        f"{name}.{taken}"
        for name in _names(isa.JmpCondition)
        for taken in ("taken", "notTaken")
        if (name, taken) != ("always", "notTaken")
    ],
    "wait": [
        f"{name}.{outcome}"
        for name in _names(isa.WaitSource)
        for outcome in ("met", "stall", "timeout")
    ],
    "inSource": _names(isa.InSource),
    "inBitCount": list(bitCountBins),
    "outDestination": _names(isa.OutDestination),
    "outBitCount": list(bitCountBins),
    "pushPull": [
        f"{kind}.{condition}.{block}"
        for kind in ("push", "pull")
        for condition in ("always", "if")
        for block in ("noblock", "block")
    ],
    "pushPullStall": ["push.full", "pull.empty"],
    "movDestination": _names(isa.MovDestination),
    "movOperation": _names(isa.MovOperation),
    "movSource": _names(isa.MovSource),
    "aluCarry": ["add.carry", "add.noCarry", "subtract.borrow", "subtract.noBorrow"],
    "setDestination": _names(isa.SetDestination),
    "setData": ["0", "63", "other"],
    "flag": _names(isa.FlagOperation) + ["wait.stall"],
    "txLevel": [str(level) for level in range(fifoDepth + 1)],
    "rxLevel": [str(level) for level in range(fifoDepth + 1)],
    "event": [
        "delay",
        "sideSet",
        "autoPull",
        "autoPush",
        "execOut",
        "execMov",
        "wrap",
        "pinDirChange",
    ],
}


class FunctionalCoverage:
    def __init__(self) -> None:
        self.hits: Counter[tuple[str, str]] = Counter()

    def _hit(self, group: str, name: str) -> None:
        if name not in coverBins[group]:
            raise KeyError(f"no bin {group}.{name}")
        self.hits[(group, name)] += 1

    def sample(
        self,
        before: ExecuteSample | None,
        after: StateSample,
        previous: StateSample,
        wrap: tuple[int, int],
    ) -> None:
        self._hit("txLevel", str(after.txLevel))
        self._hit("rxLevel", str(after.rxLevel))
        if (after.pinDir ^ previous.pinDir) & 0xFF:
            self._hit("event", "pinDirChange")
        if before is None:
            return
        opcode = isa.Opcode(before.instr >> isa.opcodeShift)
        operands = before.instr & isa.operandMask
        self._hit("opcode", opcode.name)
        if before.delay and not after.isStalled:
            self._hit("event", "delay")
        if before.sideActive:
            self._hit("event", "sideSet")
        wrapBottom, wrapTop = wrap
        if before.pc == wrapTop and after.pc == wrapBottom and wrapTop != isa.programWords - 1:
            self._hit("event", "wrap")
        handlers = {
            isa.Opcode.jmp: self._jmp,
            isa.Opcode.wait: self._wait,
            isa.Opcode.shiftIn: self._shiftIn,
            isa.Opcode.shiftOut: self._shiftOut,
            isa.Opcode.pushPull: self._pushPull,
            isa.Opcode.mov: self._mov,
            isa.Opcode.set: self._set,
            isa.Opcode.flag: self._flag,
        }
        handlers[opcode](operands, before, after)

    def _jmp(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        condition = isa.JmpCondition((operands >> isa.fieldShift) & 7)
        self._hit("jmp", f"{condition.name}.{'taken' if before.jmpTaken else 'notTaken'}")

    def _wait(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        source = (operands >> isa.fieldShift) & 3
        if source > isa.WaitSource.flag:
            return
        if after.isStalled:
            outcome = "stall"
        elif after.timeoutFlag:
            outcome = "timeout"
        else:
            outcome = "met"
        self._hit("wait", f"{isa.WaitSource(source).name}.{outcome}")

    def _shiftIn(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        source = (operands >> isa.fieldShift) & 7
        if source in {member.value for member in isa.InSource}:
            self._hit("inSource", isa.InSource(source).name)
        self._hit("inBitCount", _bitCountBin(operands))
        if before.pushDue and not after.isStalled:
            self._hit("event", "autoPush")

    def _shiftOut(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        destination = isa.OutDestination((operands >> isa.fieldShift) & 7)
        self._hit("outDestination", destination.name)
        self._hit("outBitCount", _bitCountBin(operands))
        if before.refill and not after.isStalled:
            self._hit("event", "autoPull")
        if destination == isa.OutDestination.exec and not after.isStalled:
            self._hit("event", "execOut")

    def _pushPull(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        kind = "pull" if (operands >> 8) & 1 else "push"
        condition = "if" if (operands >> 7) & 1 else "always"
        block = "block" if (operands >> 6) & 1 else "noblock"
        self._hit("pushPull", f"{kind}.{condition}.{block}")
        if after.isStalled:
            self._hit("pushPullStall", "push.full" if kind == "push" else "pull.empty")

    def _mov(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        destination = isa.MovDestination((operands >> isa.fieldShift) & 7)
        operation = isa.MovOperation((operands >> 3) & 7)
        self._hit("movDestination", destination.name)
        self._hit("movOperation", operation.name)
        self._hit("movSource", isa.MovSource(operands & 7).name)
        if destination == isa.MovDestination.exec:
            self._hit("event", "execMov")
        if operation == isa.MovOperation.add:
            isCarry = before.aluFirst + before.movSource > dataMask
            self._hit("aluCarry", "add.carry" if isCarry else "add.noCarry")
        elif operation == isa.MovOperation.subtract:
            isBorrow = before.aluFirst < before.movSource
            self._hit("aluCarry", "subtract.borrow" if isBorrow else "subtract.noBorrow")

    def _set(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        destination = (operands >> isa.fieldShift) & 7
        if destination <= isa.SetDestination.pindirs:
            self._hit("setDestination", isa.SetDestination(destination).name)
        data = operands & isa.setDataMax
        self._hit("setData", str(data) if data in (0, isa.setDataMax) else "other")

    def _flag(self, operands: int, before: ExecuteSample, after: StateSample) -> None:
        operation = (operands >> 7) & 3
        if operation > isa.FlagOperation.wait:
            return
        self._hit("flag", isa.FlagOperation(operation).name)
        if operation == isa.FlagOperation.wait and after.isStalled:
            self._hit("flag", "wait.stall")

    def holes(self) -> list[str]:
        return [
            f"{group}.{name}"
            for group, names in coverBins.items()
            for name in names
            if not self.hits[(group, name)]
        ]

    def report(self) -> list[str]:
        lines = []
        for group, names in coverBins.items():
            covered = sum(1 for name in names if self.hits[(group, name)])
            lines.append(f"{group}: {covered}/{len(names)}")
        total = sum(len(names) for names in coverBins.values())
        lines.append(f"total: {total - len(self.holes())}/{total}")
        return lines
