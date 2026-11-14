import os
from collections import Counter, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from asm.assembler import Program, assemble
from iss.core import CoreConfig, IssError
from iss.machine import Machine, bidirectionalMask, outputOnlyMask
from programGenerator import flagHeavyMix, randomEnvironment, randomHostReads, randomScenario

clkPeriodNs = 20
coreCount = 2
configWidth = 91
dataWidth = 16
outputMask = bidirectionalMask | outputOnlyMask
stateNames = ("pc", "x", "y", "t", "isr", "osr", "isrCount", "osrCount", "timeoutFlag")
secondCoreSeedOffset = 1_000_003

Environment = Callable[[int, int], int]
HostReads = Callable[[int], bool]


@dataclass
class CoreSetup:
    program: Program
    config: CoreConfig
    hostWords: Sequence[int] = ()
    hostReads: HostReads = lambda cycle: True
    received: list[int] = field(default_factory=list)


@dataclass
class MultiScenario:
    cores: Sequence[CoreSetup]
    cycles: int
    environment: Environment = lambda cycle, outputs: 0
    syncBypass: int = 0
    idleInputs: int = 0
    allowReserved: bool = False
    events: Counter[str] = field(default_factory=Counter)


def packConfig(program: Program, config: CoreConfig) -> int:
    fields = (
        (0, 8),
        (config.clkDiv, 16),
        (config.outBase, 5),
        (config.outCount, 5),
        (config.setBase, 5),
        (config.setCount, 3),
        (config.sideBase, 5),
        (program.sideSet.sideCount, 2),
        (int(program.sideSet.sideEn), 1),
        (int(program.sideSet.sidePinDir), 1),
        (config.inBase, 5),
        (config.jmpPin, 5),
        (int(config.outShiftRight), 1),
        (int(config.inShiftRight), 1),
        (int(config.autoPull), 1),
        (int(config.autoPush), 1),
        (config.pullThreshold, 5),
        (config.pushThreshold, 5),
        (program.wrapBottom, 8),
        (program.wrapTop, 8),
    )
    packed = 0
    for value, width in fields:
        packed = (packed << width) | (value & ((1 << width) - 1))
    return packed


def field16(value: int, index: int) -> int:
    return (value >> (index * dataWidth)) & 0xFFFF


async def resetAndLoad(dut: Any, scenario: MultiScenario) -> None:
    await FallingEdge(dut.clk)
    for name in ("run", "restart", "loadEn", "txWriteEn", "rxReadEn", "txWriteData", "loadAddr"):
        getattr(dut, name).value = 0
    dut.pinsIn.value = scenario.idleInputs
    dut.syncBypass.value = scenario.syncBypass
    packed = 0
    for index, setup in enumerate(scenario.cores):
        packed |= packConfig(setup.program, setup.config) << (index * configWidth)
    dut.coreConfig.value = packed
    dut.rstN.value = 0
    for _ in range(2):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rstN.value = 1
    for index, setup in enumerate(scenario.cores):
        for address, word in enumerate(setup.program.words):
            await FallingEdge(dut.clk)
            dut.loadEn.value = 1 << index
            dut.loadAddr.value = address
            dut.loadData.value = word
    await FallingEdge(dut.clk)
    dut.loadEn.value = 0


def rtlState(dut: Any) -> dict[str, int]:
    state: dict[str, int] = {}
    txLevels = int(dut.txLevel.value)
    rxLevels = int(dut.rxLevel.value)
    for index in range(coreCount):
        coreInst = getattr(dut, f"coreSlice{index}").coreInst
        for name in stateNames:
            state[f"{index}.{name}"] = int(getattr(coreInst, name).value)
        state[f"{index}.txLevel"] = (txLevels >> (3 * index)) & 7
        state[f"{index}.rxLevel"] = (rxLevels >> (3 * index)) & 7
    pinOut = int(dut.pinOut.value)
    pinDir = int(dut.pinDir.value)
    state["flags"] = int(dut.flags.value)
    state["outputs"] = pinOut & ((pinDir & bidirectionalMask) | outputOnlyMask)
    state["outputEnables"] = pinDir & bidirectionalMask
    return state


def issState(machine: Machine) -> dict[str, int]:
    state: dict[str, int] = {}
    for index, core in enumerate(machine.cores):
        for name in stateNames:
            state[f"{index}.{name}"] = int(getattr(core, name))
        state[f"{index}.txLevel"] = len(core.txFifo)
        state[f"{index}.rxLevel"] = len(core.rxFifo)
    state["flags"] = machine.flags.value
    state["outputs"] = machine.outputs & outputMask
    state["outputEnables"] = machine.outputEnables & bidirectionalMask
    return state


def countEvents(dut: Any, events: Counter[str]) -> None:
    sets = [int(getattr(dut, f"coreSlice{index}").flagSets.value) for index in range(coreCount)]
    clears = [int(getattr(dut, f"coreSlice{index}").flagClears.value) for index in range(coreCount)]
    if (sets[0] & clears[1]) | (sets[1] & clears[0]):
        events["setAndClearOnSameCycle"] += 1
    if sets[0] & sets[1]:
        events["bothSetOnSameCycle"] += 1
    if clears[0] & clears[1]:
        events["bothClearOnSameCycle"] += 1
    if sets[0] or clears[0]:
        events["core0ChangesFlag"] += 1
    if sets[1] or clears[1]:
        events["core1ChangesFlag"] += 1


async def runMultiLockstep(dut: Any, scenario: MultiScenario) -> int:
    await resetAndLoad(dut, scenario)
    machine = Machine(
        [(setup.program, setup.config) for setup in scenario.cores],
        scenario.syncBypass,
        scenario.idleInputs,
    )
    pending = [deque(setup.hostWords) for setup in scenario.cores]
    dut.run.value = (1 << coreCount) - 1
    await RisingEdge(dut.clk)
    for cycle in range(scenario.cycles):
        await FallingEdge(dut.clk)
        inputs = scenario.environment(cycle, machine.outputs)
        dut.pinsIn.value = inputs
        writeEnables = 0
        writeData = 0
        readEnables = 0
        for index, (core, setup) in enumerate(zip(machine.cores, scenario.cores)):
            if pending[index] and core.hostWrite(pending[index][0]):
                writeEnables |= 1 << index
                writeData |= pending[index].popleft() << (index * dataWidth)
            word = core.hostRead() if setup.hostReads(cycle) else None
            if word is not None:
                readEnables |= 1 << index
                actual = field16(int(dut.rxReadData.value), index)
                assert actual == word, f"cycle {cycle}: core {index} RX FIFO head"
                setup.received.append(word)
        dut.txWriteEn.value = writeEnables
        dut.txWriteData.value = writeData
        dut.rxReadEn.value = readEnables
        try:
            machine.step(inputs)
        except IssError:
            if not scenario.allowReserved:
                raise
            return cycle
        await ReadOnly()
        countEvents(dut, scenario.events)
        await RisingEdge(dut.clk)
        await ReadOnly()
        expected = issState(machine)
        actual = rtlState(dut)
        mismatches = {
            name: (actual[name], expected[name])
            for name in expected
            if actual[name] != expected[name]
        }
        assert not mismatches, f"cycle {cycle}: (rtl, iss) {mismatches}"
    return scenario.cycles


def startClock(dut: Any) -> None:
    cocotb.start_soon(Clock(dut.clk, clkPeriodNs, unit="ns").start())


directedPairs = {
    "handshake": (
        "wait 1 flag 1\nset pins, 1\nflag set 2\nwait 1 flag 7\n",
        "nop [5]\nflag set 1\nwait 1 flag 2\nset pins, 2\nwait 1 flag 7\n",
    ),
    "setBeatsClear": (
        "loop:\nflag set 4\njmp loop\n",
        "loop:\nflag clear 4\njmp loop\n",
    ),
    "twoWaiters": (
        "wait 1 flag 3\nset pins, 1\nwait 1 flag 7\n",
        "wait 1 flag 3\nset pins, 2\nflag set 3 [3]\nwait 1 flag 7\n",
    ),
}


@cocotb.test()
async def testDirectedFlagScenariosLockstep(dut: Any) -> None:
    startClock(dut)
    events: dict[str, Counter[str]] = {}
    for name, (first, second) in directedPairs.items():
        dut._log.info("directed pair %s", name)
        cores = [
            CoreSetup(assemble(first), CoreConfig(setBase=8, setCount=2)),
            CoreSetup(assemble(second), CoreConfig(setBase=8, setCount=2)),
        ]
        scenario = MultiScenario(cores, 60)
        await runMultiLockstep(dut, scenario)
        events[name] = scenario.events
    assert events["setBeatsClear"]["setAndClearOnSameCycle"] > 0


@cocotb.test()
async def testRandomProgramPairsLockstep(dut: Any) -> None:
    startClock(dut)
    seedBase = int(os.environ.get("LOCKSTEP_SEED_BASE", "1"))
    seedCount = int(os.environ.get("MULTI_LOCKSTEP_SEEDS", "30"))
    cycles = int(os.environ.get("LOCKSTEP_CYCLES", "300"))
    events: Counter[str] = Counter()
    for seed in range(seedBase, seedBase + seedCount):
        generated = [
            randomScenario(seed, flagHeavyMix),
            randomScenario(seed + secondCoreSeedOffset, flagHeavyMix),
        ]
        cores = [
            CoreSetup(
                item.program,
                item.config,
                item.hostWords,
                randomHostReads(seed + index * secondCoreSeedOffset, item),
            )
            for index, item in enumerate(generated)
        ]
        scenario = MultiScenario(
            cores,
            cycles,
            environment=randomEnvironment(seed, generated[0]),
            syncBypass=generated[0].syncBypass,
            idleInputs=generated[0].idleInputs,
            allowReserved=True,
        )
        checked = await runMultiLockstep(dut, scenario)
        events.update(scenario.events)
        dut._log.info("seed %d: %d cycles checked", seed, checked)
    dut._log.info("cross-core events: %s", dict(events))
    assert events["core0ChangesFlag"] > 0 and events["core1ChangesFlag"] > 0
