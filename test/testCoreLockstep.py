import os
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, ReadOnly, RisingEdge

from asm.assembler import Program, assemble
from iss.core import CoreConfig, IssError
from iss.machine import Machine, bidirectionalMask, outputOnlyMask
from iss.models import I2cTarget, SpiTarget, UartFrame, UartSource, i2cRead, i2cResult, i2cWrite
from functionalCoverage import ExecuteSample, FunctionalCoverage, StateSample
from programGenerator import randomEnvironment, randomHostReads, randomScenario

examplesDir = Path(__file__).resolve().parent.parent / "sw" / "asm" / "examples"
clkPeriodNs = 20
byteShift = 8
outputMask = bidirectionalMask | outputOnlyMask
stateNames = ("pc", "x", "y", "t", "isr", "osr", "isrCount", "osrCount", "timeoutFlag")

Environment = Callable[[int, int], int]
EnvironmentFactory = Callable[[Machine], Environment]
HostReads = Callable[[int], bool]


@dataclass
class Scenario:
    program: Program
    config: CoreConfig
    cycles: int
    environment: Environment = lambda cycle, outputs: 0
    environmentFactory: EnvironmentFactory | None = None
    hostWords: Sequence[int] = ()
    hostReads: HostReads = lambda cycle: True
    syncBypass: int = 0
    idleInputs: int = 0
    allowReserved: bool = False
    coverage: FunctionalCoverage | None = None
    received: list[int] = field(default_factory=list)


def loadExample(name: str) -> Program:
    return assemble((examplesDir / f"{name}.pasm").read_text())


def toInt(value: Any) -> int:
    return int(value)


def configSignals(program: Program, config: CoreConfig) -> dict[str, int]:
    return {
        "clkDiv": config.clkDiv,
        "outBase": config.outBase,
        "outCount": config.outCount,
        "setBase": config.setBase,
        "setCount": config.setCount,
        "sideBase": config.sideBase,
        "sideCount": program.sideSet.sideCount,
        "sideEn": int(program.sideSet.sideEn),
        "sidePinDir": int(program.sideSet.sidePinDir),
        "inBase": config.inBase,
        "jmpPin": config.jmpPin,
        "outShiftRight": int(config.outShiftRight),
        "inShiftRight": int(config.inShiftRight),
        "autoPull": int(config.autoPull),
        "autoPush": int(config.autoPush),
        "pullThreshold": config.pullThreshold,
        "pushThreshold": config.pushThreshold,
        "wrapBottom": program.wrapBottom,
        "wrapTop": program.wrapTop,
        "startPc": 0,
    }


idleSignals = (
    "run",
    "restart",
    "loadEn",
    "txWriteEn",
    "rxReadEn",
    "pinsIn",
    "loadAddr",
    "loadData",
    "txWriteData",
)


def startClock(dut: Any) -> None:
    cocotb.start_soon(Clock(dut.clk, clkPeriodNs, unit="ns").start())


async def resetAndLoad(dut: Any, scenario: Scenario) -> None:
    await FallingEdge(dut.clk)
    for name in idleSignals:
        getattr(dut, name).value = 0
    dut.pinsIn.value = scenario.idleInputs
    for name, value in configSignals(scenario.program, scenario.config).items():
        getattr(dut, name).value = value
    dut.syncBypass.value = scenario.syncBypass
    dut.rstN.value = 0
    await ClockCycles(dut.clk, 2)
    dut.rstN.value = 1
    for address, word in enumerate(scenario.program.words):
        await FallingEdge(dut.clk)
        dut.loadEn.value = 1
        dut.loadAddr.value = address
        dut.loadData.value = word
    await FallingEdge(dut.clk)
    dut.loadEn.value = 0


def rtlState(dut: Any) -> dict[str, int]:
    coreInst = dut.coreInst
    state = {name: toInt(getattr(coreInst, name).value) for name in stateNames}
    pinOut = toInt(dut.pinOut.value)
    pinDir = toInt(dut.pinDir.value)
    state["flags"] = toInt(coreInst.flags.value)
    state["outputs"] = pinOut & ((pinDir & bidirectionalMask) | outputOnlyMask)
    state["outputEnables"] = pinDir & bidirectionalMask
    state["txLevel"] = toInt(dut.txLevel.value)
    state["rxLevel"] = toInt(dut.rxLevel.value)
    return state


def executeSample(dut: Any) -> ExecuteSample | None:
    coreInst = dut.coreInst
    if not toInt(coreInst.execute.value):
        return None
    return ExecuteSample(
        instr=toInt(coreInst.instr.value),
        pc=toInt(coreInst.pc.value),
        jmpTaken=bool(toInt(coreInst.jmpTaken.value)),
        aluFirst=toInt(coreInst.aluFirst.value),
        movSource=toInt(coreInst.movSource.value),
        refill=bool(toInt(coreInst.refill.value)),
        pushDue=bool(toInt(coreInst.pushDue.value)),
        sideActive=bool(toInt(coreInst.sideActive.value)),
        delay=toInt(coreInst.delay.value),
        wasStalled=bool(toInt(coreInst.isStalled.value)),
    )


def stateSample(dut: Any) -> StateSample:
    coreInst = dut.coreInst
    return StateSample(
        pc=toInt(coreInst.pc.value),
        isStalled=bool(toInt(coreInst.isStalled.value)),
        timeoutFlag=bool(toInt(coreInst.timeoutFlag.value)),
        txLevel=toInt(dut.txLevel.value),
        rxLevel=toInt(dut.rxLevel.value),
        pinDir=toInt(dut.pinDir.value),
    )


def issState(machine: Machine) -> dict[str, int]:
    core = machine.cores[0]
    state = {name: int(getattr(core, name)) for name in stateNames}
    state["flags"] = machine.flags.value
    state["outputs"] = machine.outputs & outputMask
    state["outputEnables"] = core.pinDir & bidirectionalMask
    state["txLevel"] = len(core.txFifo)
    state["rxLevel"] = len(core.rxFifo)
    return state


async def runLockstep(dut: Any, scenario: Scenario) -> int:
    await resetAndLoad(dut, scenario)
    machine = Machine(
        [(scenario.program, scenario.config)], scenario.syncBypass, scenario.idleInputs
    )
    core = machine.cores[0]
    environment = (
        scenario.environment
        if scenario.environmentFactory is None
        else scenario.environmentFactory(machine)
    )
    pending = deque(scenario.hostWords)
    dut.run.value = 1
    await RisingEdge(dut.clk)
    await ReadOnly()
    previous = stateSample(dut)
    wrap = (scenario.program.wrapBottom, scenario.program.wrapTop)
    for cycle in range(scenario.cycles):
        await FallingEdge(dut.clk)
        inputs = environment(cycle, machine.outputs)
        dut.pinsIn.value = inputs
        isWrite = bool(pending) and core.hostWrite(pending[0])
        dut.txWriteEn.value = int(isWrite)
        dut.txWriteData.value = pending.popleft() if isWrite else 0
        word = core.hostRead() if scenario.hostReads(cycle) else None
        dut.rxReadEn.value = int(word is not None)
        if word is not None:
            assert toInt(dut.rxReadData.value) == word, f"cycle {cycle}: RX FIFO head"
            scenario.received.append(word)
        try:
            machine.step(inputs)
        except IssError:
            if not scenario.allowReserved:
                raise
            return cycle
        before = None
        if scenario.coverage is not None:
            await ReadOnly()
            before = executeSample(dut)
        await RisingEdge(dut.clk)
        await ReadOnly()
        if scenario.coverage is not None:
            after = stateSample(dut)
            scenario.coverage.sample(before, after, previous, wrap)
            previous = after
        expected = issState(machine)
        actual = rtlState(dut)
        mismatches = {
            name: (actual[name], expected[name])
            for name in expected
            if actual[name] != expected[name]
        }
        assert not mismatches, f"cycle {cycle}: (rtl, iss) {mismatches}"
    return scenario.cycles


@cocotb.test()
async def testUartTxLockstep(dut: Any) -> None:
    startClock(dut)
    config = CoreConfig(clkDiv=2, outBase=8, outCount=1, sideBase=8)
    scenario = Scenario(loadExample("uartTx"), config, 400, hostWords=[0x55, 0xA3, 0x0F])
    await runLockstep(dut, scenario)


@cocotb.test()
async def testUartRxLockstep(dut: Any) -> None:
    startClock(dut)
    data = [0x5A, 0xC3, 0x01]
    rxPin = 15
    clkDiv = 2
    source = UartSource([UartFrame(value) for value in data], 8 * clkDiv, startCycle=5)
    config = CoreConfig(clkDiv=clkDiv, inBase=rxPin, jmpPin=rxPin)
    scenario = Scenario(
        loadExample("uartRx"),
        config,
        len(data) * 10 * 8 * clkDiv + 60,
        environment=lambda cycle, outputs: source.level(cycle) << rxPin,
        idleInputs=1 << rxPin,
    )
    await runLockstep(dut, scenario)
    assert [word >> byteShift for word in scenario.received] == data


@cocotb.test()
async def testSpiLockstep(dut: Any) -> None:
    startClock(dut)
    sckPin, mosiPin, misoPin = 9, 10, 16
    target = SpiTarget([0xC5, 0x81, 0x7E])

    def environment(cycle: int, outputs: int) -> int:
        target.update((outputs >> sckPin) & 1, (outputs >> mosiPin) & 1)
        return target.miso << misoPin

    config = CoreConfig(
        clkDiv=1,
        outBase=mosiPin,
        outCount=1,
        sideBase=sckPin,
        inBase=misoPin,
        outShiftRight=False,
        inShiftRight=False,
        autoPull=True,
        pullThreshold=8,
        autoPush=True,
        pushThreshold=8,
    )
    sent = [0x9A, 0x00, 0xFF]
    scenario = Scenario(
        loadExample("spiMode0"),
        config,
        len(sent) * 8 * 4 + 40,
        environment=environment,
        hostWords=[value << byteShift for value in sent],
        syncBypass=1 << misoPin,
    )
    await runLockstep(dut, scenario)
    assert target.received == sent
    assert [word & 0xFF for word in scenario.received] == [0xC5, 0x81, 0x7E]


@cocotb.test()
async def testWs2812Lockstep(dut: Any) -> None:
    startClock(dut)
    config = CoreConfig(clkDiv=1, sideBase=9, outShiftRight=False, autoPull=True, pullThreshold=8)
    hostWords = [0xA5 << byteShift, 0x0F << byteShift]
    scenario = Scenario(loadExample("ws2812b"), config, 300, hostWords=hostWords)
    await runLockstep(dut, scenario)


@cocotb.test()
async def testI2cLockstep(dut: Any) -> None:
    startClock(dut)
    sdaPin, sclPin, address = 0, 1, 0x42
    target = I2cTarget(address, readData=[0x5E, 0xA1], stretchCycles=40)

    def environmentFactory(machine: Machine) -> Environment:
        def busLevels() -> tuple[int, int]:
            enables = machine.outputEnables
            scl = int(not ((enables >> sclPin) & 1 or target.sclDrive))
            sda = int(not ((enables >> sdaPin) & 1 or target.sdaDrive))
            return scl, sda

        def environment(cycle: int, outputs: int) -> int:
            target.update(*busLevels())
            scl, sda = busLevels()
            return (scl << sclPin) | (sda << sdaPin)

        return environment

    config = CoreConfig(
        clkDiv=2,
        outBase=sdaPin,
        outCount=1,
        setBase=sdaPin,
        setCount=2,
        sideBase=sclPin,
        inBase=sdaPin,
        jmpPin=sclPin,
        outShiftRight=False,
        inShiftRight=False,
    )
    words = [
        i2cWrite(address << 1, start=True),
        i2cWrite(0x07),
        i2cWrite((address << 1) | 1, start=True),
        i2cRead(ack=True),
        i2cRead(ack=False, stop=True),
    ]
    scenario = Scenario(
        loadExample("i2cController"),
        config,
        2400,
        environmentFactory=environmentFactory,
        hostWords=words,
        idleInputs=(1 << sdaPin) | (1 << sclPin),
    )
    await runLockstep(dut, scenario)
    assert target.received == [0x07]
    assert [i2cResult(word) for word in scenario.received] == [
        (address << 1, True),
        (0x07, True),
        ((address << 1) | 1, True),
        (0x5E, True),
        (0xA1, False),
    ]
    assert (target.starts, target.stops) == (2, 1)


directedPrograms = {
    "alu": """
        set x, 50
        set y, 7
        add x, y
        mov isr, x
        push
        set x, 0
        sub x, y
        xor x, y
        mov x, ::y
        mov x, ~null
        and x, y
        or x, t
        mov t, x
        mov y, status
        mov isr, y
        push
    """,
    "timeout": """
        set t, 5
        wait 1 gpio 15 timeout
        jmp timeout failed
        set pins, 1
    passed:
        jmp passed
    failed:
        set pins, 2
        jmp failed
    """,
    "exec": """
        set x, 3
    loop:
        jmp x-- loop [2]
        set y, 1
        pull
        out exec, 16
        mov isr, x
        push
        mov pc, y
    """,
    "pullPush": """
        set x, 5
        pull noblock
        mov isr, osr
        push noblock
        pull ifempty
        in osr, 4
        push iffull
        push
        jmp x!=y 0
    """,
    "flags": """
        flag set 3
        wait 1 flag 3
        mov isr, status
        flag set 5
        push
        set y, 31
        mov osr, y
        out pins, 2 [7]
        out pindirs, 2
        set pindirs, 3
        out null, 16
        jmp !osre 6
    """,
}


@cocotb.test()
async def testDirectedProgramsLockstep(dut: Any) -> None:
    startClock(dut)
    config = CoreConfig(clkDiv=1, outBase=0, outCount=2, setBase=8, setCount=2)
    for name, source in directedPrograms.items():
        execWord = assemble("set x, 9").words[0]
        scenario = Scenario(assemble(source), config, 80, hostWords=[execWord, 0x1234, 0xBEEF])
        dut._log.info("directed program %s", name)
        await runLockstep(dut, scenario)


@cocotb.test()
async def testRandomProgramsLockstep(dut: Any) -> None:
    startClock(dut)
    seedBase = int(os.environ.get("LOCKSTEP_SEED_BASE", "1"))
    seedCount = int(os.environ.get("LOCKSTEP_SEEDS", "50"))
    cycles = int(os.environ.get("LOCKSTEP_CYCLES", "300"))
    coverage = FunctionalCoverage()
    for seed in range(seedBase, seedBase + seedCount):
        generated = randomScenario(seed)
        scenario = Scenario(
            generated.program,
            generated.config,
            cycles,
            environment=randomEnvironment(seed, generated),
            hostWords=generated.hostWords,
            hostReads=randomHostReads(seed, generated),
            syncBypass=generated.syncBypass,
            idleInputs=generated.idleInputs,
            allowReserved=True,
            coverage=coverage,
        )
        checked = await runLockstep(dut, scenario)
        dut._log.info("seed %d: %d cycles checked", seed, checked)
    for line in coverage.report():
        dut._log.info("coverage %s", line)
    dut._log.info("coverage holes: %s", ", ".join(coverage.holes()) or "none")
