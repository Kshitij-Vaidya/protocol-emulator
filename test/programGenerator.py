import random
from collections.abc import Callable
from dataclasses import dataclass

from asm import isa
from asm.assembler import Program
from iss.core import CoreConfig

dataBits = 16
dataMask = (1 << dataBits) - 1
inputMask = 0xFF | (0x1F << 15)
reservedInSources = (4, 5)
aluOperations = tuple(range(isa.MovOperation.add, isa.MovOperation.bitXor + 1))
aluDestinations = (int(isa.MovDestination.x), int(isa.MovDestination.y), int(isa.MovDestination.t))
bitCountCorners = (0, 1, 15)
dataCorners = (0, 1, 31, 32, 63)
wordCorners = (0x0000, 0x0001, 0x7FFF, 0x8000, 0xFFFF)


@dataclass(frozen=True)
class RandomScenario:
    program: Program
    config: CoreConfig
    hostWords: tuple[int, ...]
    syncBypass: int
    idleInputs: int
    toggleChance: float
    readChance: float


def _bitCount(rng: random.Random) -> int:
    if rng.random() < 0.4:
        return rng.choice(bitCountCorners)
    return rng.randrange(16)


def _jmp(rng: random.Random) -> int:
    condition = rng.randrange(8)
    offset = rng.randint(isa.jmpOffsetMin, isa.jmpOffsetMax) & 0x3F
    return (condition << isa.fieldShift) | offset


@dataclass(frozen=True)
class InstructionMix:
    weights: dict[isa.Opcode, int]
    flagIndexes: int = isa.flagCount


def _wait(rng: random.Random, mix: InstructionMix) -> int:
    polarity = rng.randrange(2)
    source = rng.randrange(3)
    isTimeoutEn = int(rng.random() < 0.8)
    index = rng.randrange(mix.flagIndexes if source == isa.WaitSource.flag else isa.pinCount)
    return (polarity << 8) | (source << isa.fieldShift) | (isTimeoutEn << 5) | index


def _shiftIn(rng: random.Random) -> int:
    source = rng.choice([code for code in range(8) if code not in reservedInSources])
    return (source << isa.fieldShift) | _bitCount(rng)


def _shiftOut(rng: random.Random) -> int:
    weights = [3, 3, 3, 3, 2, 1, 3, 1]
    destination = rng.choices(range(8), weights)[0]
    return (destination << isa.fieldShift) | _bitCount(rng)


def _pushPull(rng: random.Random) -> int:
    return rng.randrange(8) << isa.fieldShift


def _mov(rng: random.Random) -> int:
    source = rng.randrange(8)
    if rng.random() < 0.5:
        destination = rng.choice(aluDestinations)
        operation = rng.choice(aluOperations)
    else:
        destination = rng.choices(range(8), [3, 3, 3, 3, 1, 1, 3, 3])[0]
        operation = rng.randrange(isa.MovOperation.reverse + 1)
    return (destination << isa.fieldShift) | (operation << 3) | source


def _set(rng: random.Random) -> int:
    destination = rng.randrange(isa.SetDestination.pindirs + 1)
    data = rng.choice(dataCorners) if rng.random() < 0.4 else rng.randrange(isa.setDataMax + 1)
    return (destination << isa.fieldShift) | data


def _flag(rng: random.Random, mix: InstructionMix) -> int:
    operation = rng.choices(range(3), [4, 4, 1])[0]
    return (operation << 7) | rng.randrange(mix.flagIndexes)


operandMakers: dict[isa.Opcode, Callable[[random.Random, InstructionMix], int]] = {
    isa.Opcode.jmp: lambda rng, mix: _jmp(rng),
    isa.Opcode.wait: _wait,
    isa.Opcode.shiftIn: lambda rng, mix: _shiftIn(rng),
    isa.Opcode.shiftOut: lambda rng, mix: _shiftOut(rng),
    isa.Opcode.pushPull: lambda rng, mix: _pushPull(rng),
    isa.Opcode.mov: lambda rng, mix: _mov(rng),
    isa.Opcode.set: lambda rng, mix: _set(rng),
    isa.Opcode.flag: _flag,
}
opcodeWeights = {
    isa.Opcode.jmp: 15,
    isa.Opcode.wait: 6,
    isa.Opcode.shiftIn: 12,
    isa.Opcode.shiftOut: 12,
    isa.Opcode.pushPull: 15,
    isa.Opcode.mov: 20,
    isa.Opcode.set: 14,
    isa.Opcode.flag: 6,
}


defaultMix = InstructionMix(opcodeWeights)
flagHeavyMix = InstructionMix(
    {**opcodeWeights, isa.Opcode.wait: 15, isa.Opcode.flag: 20}, flagIndexes=2
)


def randomInstruction(rng: random.Random, mix: InstructionMix = defaultMix) -> int:
    opcode = rng.choices(list(mix.weights), list(mix.weights.values()))[0]
    timing = 0 if rng.random() < 0.6 else rng.randint(0, isa.timingMask)
    return isa.encode(opcode, timing, operandMakers[opcode](rng, mix))


def randomSideSet(rng: random.Random) -> isa.SideSetConfig:
    sideCount = rng.choices(range(4), [4, 2, 2, 1])[0]
    sideEn = sideCount > 0 and rng.random() < 0.5
    return isa.SideSetConfig(sideCount, sideEn, rng.random() < 0.3)


def randomConfig(rng: random.Random) -> CoreConfig:
    return CoreConfig(
        clkDiv=rng.choices([1, 2, 3], [6, 2, 1])[0],
        outBase=rng.randrange(isa.pinCount),
        outCount=rng.randint(0, dataBits),
        setBase=rng.randrange(isa.pinCount),
        setCount=rng.randint(0, 6),
        sideBase=rng.randrange(isa.pinCount),
        inBase=rng.randrange(isa.pinCount),
        jmpPin=rng.randrange(isa.pinCount),
        outShiftRight=rng.random() < 0.5,
        inShiftRight=rng.random() < 0.5,
        autoPull=rng.random() < 0.5,
        pullThreshold=rng.choice([1, 8, 16, rng.randint(1, dataBits)]),
        autoPush=rng.random() < 0.5,
        pushThreshold=rng.choice([1, 8, 16, rng.randint(1, dataBits)]),
    )


def randomProgram(rng: random.Random, mix: InstructionMix) -> Program:
    words = tuple(randomInstruction(rng, mix) for _ in range(isa.programWords))
    wrapTop = rng.choice([isa.programWords - 1, rng.randrange(4, 48)])
    wrapBottom = rng.randint(0, wrapTop)
    return Program(words, {}, randomSideSet(rng), wrapBottom, wrapTop)


def randomHostWord(rng: random.Random) -> int:
    choice = rng.random()
    if choice < 0.5:
        return randomInstruction(rng)
    if choice < 0.7:
        return rng.choice(wordCorners)
    return rng.randrange(dataMask + 1)


def randomScenario(seed: int, mix: InstructionMix = defaultMix) -> RandomScenario:
    rng = random.Random(seed)
    program = randomProgram(rng, mix)
    config = randomConfig(rng)
    hostWords = tuple(randomHostWord(rng) for _ in range(rng.randint(0, 12)))
    syncBypass = rng.randrange(1 << isa.pinCount) & inputMask if rng.random() < 0.3 else 0
    idleInputs = rng.randrange(1 << isa.pinCount) & inputMask
    toggleChance = rng.random() * 0.2
    readChance = rng.choice([1.0, 0.1, 0.02])
    return RandomScenario(
        program, config, hostWords, syncBypass, idleInputs, toggleChance, readChance
    )


def randomEnvironment(seed: int, scenario: RandomScenario) -> Callable[[int, int], int]:
    rng = random.Random(seed ^ 0x5EED)
    levels = scenario.idleInputs

    def environment(cycle: int, outputs: int) -> int:
        nonlocal levels
        for pin in range(isa.pinCount):
            if (inputMask >> pin) & 1 and rng.random() < scenario.toggleChance:
                levels ^= 1 << pin
        return levels

    return environment


def randomHostReads(seed: int, scenario: RandomScenario) -> Callable[[int], bool]:
    rng = random.Random(seed ^ 0xFEED)
    return lambda cycle: rng.random() < scenario.readChance
