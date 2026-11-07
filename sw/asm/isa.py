from dataclasses import dataclass
from enum import IntEnum

programWords = 256
timingBits = 4
opcodeShift = 13
timingShift = 9
fieldShift = 6
operandMask = (1 << timingShift) - 1
timingMask = (1 << timingBits) - 1
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


class JmpCondition(IntEnum):
    always = 0
    xZero = 1
    xDecrement = 2
    yDecrement = 3
    xNotEqualY = 4
    pin = 5
    osrNotEmpty = 6
    timeout = 7


class WaitSource(IntEnum):
    gpio = 0
    pin = 1
    flag = 2


class InSource(IntEnum):
    pins = 0
    x = 1
    y = 2
    null = 3
    isr = 6
    osr = 7


class OutDestination(IntEnum):
    pins = 0
    x = 1
    y = 2
    null = 3
    pindirs = 4
    pc = 5
    isr = 6
    exec = 7


class MovDestination(IntEnum):
    pins = 0
    x = 1
    y = 2
    t = 3
    exec = 4
    pc = 5
    isr = 6
    osr = 7


class MovSource(IntEnum):
    pins = 0
    x = 1
    y = 2
    null = 3
    status = 4
    isr = 5
    osr = 6
    t = 7


class SetDestination(IntEnum):
    pins = 0
    x = 1
    y = 2
    t = 3
    pindirs = 4


class FlagOperation(IntEnum):
    set = 0
    clear = 1
    wait = 2


jmpConditions = {
    "": JmpCondition.always,
    "!x": JmpCondition.xZero,
    "x--": JmpCondition.xDecrement,
    "y--": JmpCondition.yDecrement,
    "x!=y": JmpCondition.xNotEqualY,
    "pin": JmpCondition.pin,
    "!osre": JmpCondition.osrNotEmpty,
    "timeout": JmpCondition.timeout,
}
waitSources = {member.name: member for member in WaitSource}
inSources = {member.name: member for member in InSource}
outDestinations = {member.name: member for member in OutDestination}
movDestinations = {member.name: member for member in MovDestination}
movSources = {member.name: member for member in MovSource}
aluDestinations = frozenset({"x", "y", "t"})
setDestinations = {member.name: member for member in SetDestination}
flagOperations = {member.name: member for member in FlagOperation}


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

    def unpackTiming(self, field: int) -> tuple[int | None, int]:
        delay = field & self.maxDelay
        isSideSet = self.sideCount > 0 and (not self.sideEn or bool(field >> (timingBits - 1)))
        side = (field >> self.delayBits) & self.maxSide if isSideSet else None
        return side, delay

    def packTiming(self, side: int | None, delay: int) -> int:
        field = delay
        if side is not None:
            field |= side << self.delayBits
            if self.sideEn:
                field |= 1 << (timingBits - 1)
        return field


def encode(opcode: Opcode, timing: int, operands: int) -> int:
    return (opcode << opcodeShift) | (timing << timingShift) | operands
