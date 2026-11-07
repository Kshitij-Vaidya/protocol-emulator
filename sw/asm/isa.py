from dataclasses import dataclass
from enum import IntEnum

programWords = 256
timingBits = 4
opcodeShift = 13
timingShift = 9
fieldShift = 6
maxBitCount = 16
pinCount = 32
flagCount = 8
jmpOffsetMin = -32
jmpOffsetMax = 31
setDataMax = 63


class Opcode(IntEnum):
    jmp = 0
    wait = 1
    shiftIn = 2
    shiftOut = 3
    pushPull = 4
    mov = 5
    set = 6
    flag = 7


class MovOperation(IntEnum):
    copy = 0
    invert = 1
    reverse = 2
    add = 3
    subtract = 4
    bitAnd = 5
    bitOr = 6
    bitXor = 7


jmpConditions = {
    "": 0,
    "!x": 1,
    "x--": 2,
    "y--": 3,
    "x!=y": 4,
    "pin": 5,
    "!osre": 6,
    "timeout": 7,
}
waitSources = {"gpio": 0, "pin": 1, "flag": 2}
inSources = {"pins": 0, "x": 1, "y": 2, "null": 3, "isr": 6, "osr": 7}
outDestinations = {
    "pins": 0,
    "x": 1,
    "y": 2,
    "null": 3,
    "pindirs": 4,
    "pc": 5,
    "isr": 6,
    "exec": 7,
}
movDestinations = {
    "pins": 0,
    "x": 1,
    "y": 2,
    "t": 3,
    "exec": 4,
    "pc": 5,
    "isr": 6,
    "osr": 7,
}
movSources = {
    "pins": 0,
    "x": 1,
    "y": 2,
    "null": 3,
    "status": 4,
    "isr": 5,
    "osr": 6,
    "t": 7,
}
aluDestinations = frozenset({"x", "y", "t"})
setDestinations = {"pins": 0, "x": 1, "y": 2, "t": 3, "pindirs": 4}
flagOperations = {"set": 0, "clear": 1, "wait": 2}


@dataclass(frozen=True)
class SideSetConfig:
    sideCount: int = 0
    sideEn: bool = False
    sidePinDir: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.sideCount <= 3:
            raise ValueError(f"sideCount must be 0 to 3, not {self.sideCount}")
        if self.sideEn and self.sideCount == 0:
            raise ValueError("sideEn needs sideCount of 1 or more")

    @property
    def delayBits(self) -> int:
        return timingBits - self.sideCount - int(self.sideEn)

    @property
    def maxDelay(self) -> int:
        return (1 << self.delayBits) - 1

    @property
    def maxSide(self) -> int:
        return (1 << self.sideCount) - 1

    def packTiming(self, side: int | None, delay: int) -> int:
        field = delay
        if side is not None:
            field |= side << self.delayBits
            if self.sideEn:
                field |= 1 << (timingBits - 1)
        return field


def encode(opcode: Opcode, timing: int, operands: int) -> int:
    return (opcode << opcodeShift) | (timing << timingShift) | operands
