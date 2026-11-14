from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from asm.assembler import Program, assemble
from iss.core import Core, CoreConfig
from iss.machine import Machine
from iss.models import (
    I2cTarget,
    PinRecorder,
    SpiTarget,
    UartFrame,
    UartSource,
    decodeUart,
    i2cRead,
    i2cResult,
    i2cWrite,
)

examplesDir = Path(__file__).resolve().parents[2] / "asm" / "examples"
clockHz = 48_000_000
txPin = 8
sckPin = 9
mosiPin = 10
csPin = 11
dinPin = 9
rxPin = 15
misoPin = 16
sdaPin = 0
sclPin = 1
i2cAddress = 0x42
i2cBusIdle = (1 << sdaPin) | (1 << sclPin)
i2cBusErrorFlag = 1
fastModeDivider = 9
byteShift = 8
byteBits = 8
uartTxTicksPerBit = 4
uartRxTicksPerBit = 8
uartFrameBits = 10
spiTicksPerBit = 4
ws2812Divider = 6
ws2812LimitsNs = {"T0H": (250, 550), "T0L": (700, 1000), "T1H": (650, 950), "T1L": (300, 600)}
txData = [0x55, 0x00, 0xFF, 0xA3, 0x5C]


def loadExample(name: str) -> Program:
    return assemble((examplesDir / f"{name}.pasm").read_text())


def feedHost(core: Core, pending: deque[int]) -> None:
    if pending and core.hostWrite(pending[0]):
        pending.popleft()


def runUartTx(data: Sequence[int], clkDiv: int) -> PinRecorder:
    config = CoreConfig(clkDiv=clkDiv, outBase=txPin, outCount=1, sideBase=txPin)
    machine = Machine([(loadExample("uartTx"), config)])
    recorder = PinRecorder(txPin)
    pending = deque(data)

    def environment(cycle: int, outputs: int) -> int:
        recorder.sample(cycle, outputs)
        feedHost(machine.cores[0], pending)
        return 0

    machine.run((len(data) + 2) * uartFrameBits * uartTxTicksPerBit * clkDiv, environment)
    return recorder


@pytest.mark.parametrize("clkDiv", [1, 3, 104])
def testUartTxSendsBytes(clkDiv: int) -> None:
    recorder = runUartTx(txData, clkDiv)
    assert decodeUart(recorder, uartTxTicksPerBit * clkDiv) == txData


@pytest.mark.parametrize("clkDiv", [1, 3, 104])
def testUartTxEdgesAreOnExactBitBoundaries(clkDiv: int) -> None:
    recorder = runUartTx(txData, clkDiv)
    bitCycles = uartTxTicksPerBit * clkDiv
    assert recorder.edges[:2] == [(0, 0), (1, 1)]
    firstStart = recorder.edges[2][0]
    assert all((cycle - firstStart) % bitCycles == 0 for cycle, _ in recorder.edges[2:])
    lastStopStart = ((len(txData) - 1) * uartFrameBits + byteBits + 1) * bitCycles
    assert recorder.edges[-1] == (firstStart + lastStopStart, 1)


def testUartTxDividerGives115200BaudAt48Megahertz() -> None:
    assert abs(clockHz / (uartTxTicksPerBit * 104) / 115200 - 1) < 0.002


def runUartRx(sources: Sequence[UartSource], clkDiv: int, cycles: int) -> tuple[Machine, list[int]]:
    config = CoreConfig(clkDiv=clkDiv, inBase=rxPin, jmpPin=rxPin)
    machine = Machine([(loadExample("uartRx"), config)])
    received: list[int] = []

    def environment(cycle: int, outputs: int) -> int:
        word = machine.cores[0].hostRead()
        if word is not None:
            received.append(word >> byteShift)
        level = 1
        for source in sources:
            level &= source.level(cycle)
        return level << rxPin

    machine.run(cycles, environment)
    return machine, received


@pytest.mark.parametrize("baudError", [-0.02, 0.0, 0.02])
@pytest.mark.parametrize("clkDiv", [1, 13, 52])
def testUartRxReceivesBytes(clkDiv: int, baudError: float) -> None:
    cyclesPerBit = uartRxTicksPerBit * clkDiv * (1 + baudError)
    source = UartSource([UartFrame(value) for value in txData], cyclesPerBit, startCycle=20)
    cycles = int((len(txData) + 2) * uartFrameBits * cyclesPerBit)
    machine, received = runUartRx([source], clkDiv, cycles)
    assert received == txData
    assert not machine.flags.isSet(0)


def testUartRxFramingErrorSetsFlagAndRecovers() -> None:
    clkDiv = 5
    cyclesPerBit = uartRxTicksPerBit * clkDiv
    badFrames = [UartFrame(0x41), UartFrame(0x80, stopLevel=0)]
    first = UartSource(badFrames, cyclesPerBit, startCycle=20)
    secondStart = 20 + (len(badFrames) + 1) * uartFrameBits * cyclesPerBit
    second = UartSource([UartFrame(0x7E)], cyclesPerBit, startCycle=secondStart)
    cycles = secondStart + 2 * uartFrameBits * cyclesPerBit
    machine, received = runUartRx([first, second], clkDiv, cycles)
    assert received == [0x41, 0x7E]
    assert machine.flags.isSet(0)


def runSpi(
    sent: Sequence[int], responses: Sequence[int], clkDiv: int, syncBypass: int
) -> tuple[SpiTarget, list[int], PinRecorder]:
    config = CoreConfig(
        clkDiv=clkDiv,
        outBase=mosiPin,
        outCount=1,
        sideBase=sckPin,
        inBase=misoPin,
        outShiftRight=False,
        inShiftRight=False,
        autoPull=True,
        pullThreshold=byteBits,
        autoPush=True,
        pushThreshold=byteBits,
    )
    machine = Machine([(loadExample("spiMode0"), config)], syncBypass)
    core = machine.cores[0]
    target = SpiTarget(responses)
    recorder = PinRecorder(sckPin)
    pending = deque(value << byteShift for value in sent)
    received: list[int] = []

    def environment(cycle: int, outputs: int) -> int:
        recorder.sample(cycle, outputs)
        target.update((outputs >> sckPin) & 1, (outputs >> mosiPin) & 1)
        feedHost(core, pending)
        word = core.hostRead()
        if word is not None:
            received.append(word & 0xFF)
        return target.miso << misoPin

    machine.run((len(sent) + 1) * byteBits * spiTicksPerBit * clkDiv, environment)
    return target, received, recorder


spiSent = [0x9A, 0x00, 0xFF, 0x3C]
spiResponses = [0xC5, 0x81, 0x7E, 0x0F]


@pytest.mark.parametrize(("clkDiv", "syncBypass"), [(2, 0), (4, 0), (1, 1 << misoPin)])
def testSpiMode0ExchangesBytes(clkDiv: int, syncBypass: int) -> None:
    target, received, recorder = runSpi(spiSent, spiResponses, clkDiv, syncBypass)
    assert target.received == spiSent
    assert received == spiResponses
    rising = [cycle for cycle, level in recorder.edges if level == 1]
    assert {later - earlier for earlier, later in zip(rising, rising[1:])} == {
        spiTicksPerBit * clkDiv
    }


def testSpiAtFullSpeedFailsWithoutSynchronizerBypass() -> None:
    target, received, _ = runSpi(spiSent, spiResponses, clkDiv=1, syncBypass=0)
    assert target.received == spiSent
    assert received != spiResponses


def runSpiCs(
    sent: Sequence[int], responses: Sequence[int], clkDiv: int
) -> tuple[SpiTarget, list[int], PinRecorder, PinRecorder]:
    config = CoreConfig(
        clkDiv=clkDiv,
        outBase=mosiPin,
        outCount=1,
        setBase=csPin,
        setCount=1,
        sideBase=sckPin,
        inBase=misoPin,
        outShiftRight=False,
        inShiftRight=False,
    )
    machine = Machine([(loadExample("spiMode0Cs"), config)])
    core = machine.cores[0]
    target = SpiTarget(responses)
    sckRecorder = PinRecorder(sckPin)
    csRecorder = PinRecorder(csPin)
    pending = deque(value << byteShift for value in sent)
    received: list[int] = []

    def environment(cycle: int, outputs: int) -> int:
        sckRecorder.sample(cycle, outputs)
        csRecorder.sample(cycle, outputs)
        target.update((outputs >> sckPin) & 1, (outputs >> mosiPin) & 1)
        feedHost(core, pending)
        word = core.hostRead()
        if word is not None:
            received.append(word & 0xFF)
        return target.miso << misoPin

    machine.run((len(sent) + 1) * 2 * byteBits * spiTicksPerBit * clkDiv, environment)
    return target, received, sckRecorder, csRecorder


@pytest.mark.parametrize("clkDiv", [2, 5])
def testSpiMode0WithChipSelectFramesEachByte(clkDiv: int) -> None:
    target, received, sckRecorder, csRecorder = runSpiCs(spiSent, spiResponses, clkDiv)
    assert target.received == spiSent
    assert received == spiResponses
    rising = [cycle for cycle, level in sckRecorder.edges if level == 1]
    assert len(rising) == len(spiSent) * byteBits
    assert all(csRecorder.levelAt(cycle) == 0 for cycle in rising)
    csFrames = [cycle for cycle, level in csRecorder.edges[1:] if level == 0]
    assert len(csFrames) == len(spiSent)
    assert csRecorder.edges[-1][1] == 1


def ws2812Bits(data: Sequence[int]) -> list[int]:
    return [(value >> bit) & 1 for value in data for bit in reversed(range(byteBits))]


def testWs2812TimingIsInsideDatasheetLimits() -> None:
    data = [0xA5, 0x0F, 0xF0]
    config = CoreConfig(
        clkDiv=ws2812Divider,
        sideBase=dinPin,
        outShiftRight=False,
        autoPull=True,
        pullThreshold=byteBits,
    )
    machine = Machine([(loadExample("ws2812b"), config)])
    recorder = PinRecorder(dinPin)
    pending = deque(value << byteShift for value in data)

    def environment(cycle: int, outputs: int) -> int:
        recorder.sample(cycle, outputs)
        feedHost(machine.cores[0], pending)
        return 0

    bits = ws2812Bits(data)
    machine.run((len(bits) + 4) * 10 * ws2812Divider, environment)
    pulses = recorder.pulses()
    highs = [duration for level, duration in pulses[1::2]]
    lows = [duration for level, duration in pulses[2::2]]
    tick = ws2812Divider
    assert highs == [tick * (7 if bit else 3) for bit in bits]
    assert lows == [tick * (3 if bit else 7) for bit in bits[:-1]]
    nsPerCycle = 1e9 / clockHz
    measured = {
        "T0H": highs[bits.index(0)],
        "T1H": highs[bits.index(1)],
        "T0L": lows[bits.index(0)],
        "T1L": lows[bits.index(1)],
    }
    for name, cycles in measured.items():
        low, high = ws2812LimitsNs[name]
        assert low <= cycles * nsPerCycle <= high, name


@dataclass
class I2cRun:
    results: list[tuple[int, bool]]
    machine: Machine
    trace: list[tuple[int, int]]


def runI2c(words: Sequence[int], target: I2cTarget, clkDiv: int, cycles: int) -> I2cRun:
    config = CoreConfig(
        clkDiv=clkDiv,
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
    machine = Machine([(loadExample("i2cController"), config)], idleInputs=i2cBusIdle)
    core = machine.cores[0]
    pending = deque(words)
    run = I2cRun([], machine, [])

    def busLevels() -> tuple[int, int]:
        enables = machine.outputEnables
        scl = int(not ((enables >> sclPin) & 1 or target.sclDrive))
        sda = int(not ((enables >> sdaPin) & 1 or target.sdaDrive))
        return scl, sda

    def environment(cycle: int, outputs: int) -> int:
        target.update(*busLevels())
        scl, sda = busLevels()
        run.trace.append((scl, sda))
        feedHost(core, pending)
        word = core.hostRead()
        if word is not None:
            run.results.append(i2cResult(word))
        return (scl << sclPin) | (sda << sdaPin)

    machine.run(cycles, environment)
    return run


def levelRuns(trace: Sequence[tuple[int, int]], index: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    for sample in trace:
        level = sample[index]
        if runs and runs[-1][0] == level:
            runs[-1] = (level, runs[-1][1] + 1)
        else:
            runs.append((level, 1))
    return runs


def testI2cWriteIsAcknowledged() -> None:
    target = I2cTarget(i2cAddress)
    words = [i2cWrite(i2cAddress << 1, start=True), i2cWrite(0x12), i2cWrite(0x34, stop=True)]
    run = runI2c(words, target, clkDiv=2, cycles=1500)
    assert target.received == [0x12, 0x34]
    assert run.results == [(i2cAddress << 1, True), (0x12, True), (0x34, True)]
    assert (target.starts, target.stops) == (1, 1)
    assert run.trace[-1] == (1, 1)


def testI2cReadReturnsTargetBytes() -> None:
    target = I2cTarget(i2cAddress, readData=[0xA5, 0x3C])
    words = [
        i2cWrite((i2cAddress << 1) | 1, start=True),
        i2cRead(ack=True),
        i2cRead(ack=False, stop=True),
    ]
    run = runI2c(words, target, clkDiv=2, cycles=1500)
    assert run.results == [((i2cAddress << 1) | 1, True), (0xA5, True), (0x3C, False)]
    assert target.controllerAcks == [True, False]
    assert target.stops == 1


def testI2cWrongAddressIsNotAcknowledged() -> None:
    target = I2cTarget(i2cAddress)
    run = runI2c([i2cWrite(0x10 << 1, start=True, stop=True)], target, clkDiv=2, cycles=800)
    assert run.results == [(0x10 << 1, False)]
    assert target.received == []


def testI2cRepeatedStartSwitchesToRead() -> None:
    target = I2cTarget(i2cAddress, readData=[0x5E])
    words = [
        i2cWrite(i2cAddress << 1, start=True),
        i2cWrite(0x07),
        i2cWrite((i2cAddress << 1) | 1, start=True),
        i2cRead(ack=False, stop=True),
    ]
    run = runI2c(words, target, clkDiv=2, cycles=2000)
    assert target.received == [0x07]
    assert [data for data, _ in run.results] == [i2cAddress << 1, 0x07, (i2cAddress << 1) | 1, 0x5E]
    assert (target.starts, target.stops) == (2, 1)


def testI2cWaitsForClockStretch() -> None:
    stretchCycles = 150
    target = I2cTarget(i2cAddress, stretchCycles=stretchCycles)
    words = [i2cWrite(i2cAddress << 1, start=True), i2cWrite(0x99, stop=True)]
    run = runI2c(words, target, clkDiv=4, cycles=3000)
    assert target.received == [0x99]
    assert all(ack for _, ack in run.results)
    assert max(count for level, count in levelRuns(run.trace, 0) if level == 0) >= stretchCycles
    assert not run.machine.flags.isSet(i2cBusErrorFlag)


def testI2cStretchAboveTimeoutSetsBusErrorFlag() -> None:
    target = I2cTarget(i2cAddress, stretchCycles=1000)
    words = [i2cWrite(i2cAddress << 1, start=True), i2cWrite(0x99, stop=True)]
    run = runI2c(words, target, clkDiv=2, cycles=2000)
    assert run.machine.flags.isSet(i2cBusErrorFlag)
    assert target.received == []


def testI2cFastModeTimingAt48Mhz() -> None:
    target = I2cTarget(i2cAddress)
    words = [i2cWrite(i2cAddress << 1, start=True), i2cWrite(0xC3, stop=True)]
    run = runI2c(words, target, clkDiv=fastModeDivider, cycles=4000)
    assert target.received == [0xC3]
    sclRuns = levelRuns(run.trace, 0)[1:-1]
    lowCycles = min(count for level, count in sclRuns if level == 0)
    highCycles = min(count for level, count in sclRuns if level == 1)
    assert lowCycles / clockHz >= 1.3e-6
    assert highCycles / clockHz >= 0.6e-6
    assert (lowCycles + highCycles) / clockHz >= 1 / 400e3


def busConditionTimes(trace: Sequence[tuple[int, int]]) -> dict[str, list[int]]:
    times: dict[str, list[int]] = {"startSetup": [], "startHold": [], "stopSetup": []}
    sclRise = 0
    pendingStart: int | None = None
    for cycle in range(1, len(trace)):
        (sclBefore, sdaBefore), (scl, sda) = trace[cycle - 1], trace[cycle]
        if scl and not sclBefore:
            sclRise = cycle
        if not scl and sclBefore and pendingStart is not None:
            times["startHold"].append(cycle - pendingStart)
            pendingStart = None
        if scl and sclBefore and sda != sdaBefore:
            if sda:
                times["stopSetup"].append(cycle - sclRise)
            else:
                times["startSetup"].append(cycle - sclRise)
                pendingStart = cycle
    return times


def testI2cFastModeStartAndStopTimesAt48Mhz() -> None:
    target = I2cTarget(i2cAddress, readData=[0x5E])
    words = [
        i2cWrite(i2cAddress << 1, start=True),
        i2cWrite(0x07),
        i2cWrite((i2cAddress << 1) | 1, start=True),
        i2cRead(ack=False, stop=True),
    ]
    run = runI2c(words, target, clkDiv=fastModeDivider, cycles=8000)
    times = busConditionTimes(run.trace)
    assert len(times["startSetup"]) == 2
    assert len(times["stopSetup"]) == 1
    assert min(times["startSetup"][1:] + times["startHold"] + times["stopSetup"]) / clockHz >= 0.6e-6
