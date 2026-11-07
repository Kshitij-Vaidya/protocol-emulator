from collections import deque
from collections.abc import Sequence
from pathlib import Path

import pytest

from asm.assembler import Program, assemble
from iss.core import Core, CoreConfig
from iss.machine import Machine
from iss.models import PinRecorder, SpiTarget, UartFrame, UartSource, decodeUart

examplesDir = Path(__file__).resolve().parents[2] / "asm" / "examples"
clockHz = 48_000_000
txPin = 8
sckPin = 9
mosiPin = 10
dinPin = 9
rxPin = 15
misoPin = 16
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
