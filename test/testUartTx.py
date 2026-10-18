import random

import cocotb
from cocotb.clock import Clock
from cocotb.handle import HierarchyObject
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge
from cocotb.utils import get_sim_time
from cocotbext.uart import UartSink

clkPeriodNs = 20
clkFreqHz = 50_000_000
baudRate = 115_200
clksPerBit = round(clkFreqHz / baudRate)
frameBits = 10
syncLatencyCycles = 3


async def resetDutObject(dut: HierarchyObject) -> None:
    cocotb.start_soon(Clock(dut.clk, clkPeriodNs, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def pressSend(dut: HierarchyObject, data: int) -> None:
    dut.ui_in.value = data
    await ClockCycles(dut.clk, 1)
    dut.uio_in.value = 1
    await ClockCycles(dut.clk, syncLatencyCycles + 1)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, syncLatencyCycles)


async def waitForReady(dut: HierarchyObject) -> None:
    while int(dut.txReady.value) == 0:
        await RisingEdge(dut.clk)


async def measureLowCycles(signal: HierarchyObject) -> int:
    await FallingEdge(signal)
    fallTimeNs = get_sim_time(unit="ns")
    await RisingEdge(signal)
    return round((get_sim_time(unit="ns") - fallTimeNs) / clkPeriodNs)


async def readBytes(sink: UartSink, count: int) -> bytes:
    received = bytearray()
    while len(received) < count:
        received.extend(await sink.read(1))
    return bytes(received)


async def sampleFrame(dut: HierarchyObject) -> list[int]:
    await FallingEdge(dut.uartTxPin)
    await ClockCycles(dut.clk, clksPerBit // 2)
    bits = []
    for _ in range(frameBits):
        bits.append(int(dut.uartTxPin.value))
        await ClockCycles(dut.clk, clksPerBit)
    return bits


@cocotb.test()
async def testIdleLineIsHighAndReady(dut: HierarchyObject) -> None:
    await resetDutObject(dut)
    await ClockCycles(dut.clk, 3 * clksPerBit)
    assert int(dut.uartTxPin.value) == 1, "TX line is not high after reset"
    assert int(dut.txReady.value) == 1, "txReady pin is not high after reset"


@cocotb.test()
async def testFrameHasExactBitTiming(dut: HierarchyObject) -> None:
    await resetDutObject(dut)
    data = 0x4B
    sampler = cocotb.start_soon(sampleFrame(dut))
    await pressSend(dut, data)
    bits = await sampler
    expected = [0] + [(data >> i) & 1 for i in range(8)] + [1]
    assert bits == expected, f"Frame bits {bits} do not match {expected}"


@cocotb.test()
async def testStartBitLastsOneBitPeriod(dut: HierarchyObject) -> None:
    await resetDutObject(dut)
    measurement = cocotb.start_soon(measureLowCycles(dut.uartTxPin))
    await pressSend(dut, 0x01)
    lowCycles = await measurement
    assert lowCycles == clksPerBit, f"start bit low for {lowCycles} cycles, expected {clksPerBit}"


@cocotb.test()
async def testReadyLowForTheWholeFrame(dut: HierarchyObject) -> None:
    await resetDutObject(dut)
    measurement = cocotb.start_soon(measureLowCycles(dut.txReady))
    await pressSend(dut, 0x3C)
    busyCycles = await measurement
    assert busyCycles == frameBits * clksPerBit, (
        f"txReady low for {busyCycles} cycles, expected {frameBits * clksPerBit}"
    )


@cocotb.test()
async def testRandomBytesMatchUartModel(dut: HierarchyObject) -> None:
    await resetDutObject(dut)
    sink = UartSink(dut.uartTxPin, baud=baudRate, bits=8)
    rng = random.Random(cocotb.RANDOM_SEED)
    sent = bytes(rng.randrange(256) for _ in range(16))
    for value in sent:
        await waitForReady(dut)
        await pressSend(dut, value)
    received = await readBytes(sink, len(sent))
    assert received == sent, f"received {received.hex()} expected {sent.hex()}"
