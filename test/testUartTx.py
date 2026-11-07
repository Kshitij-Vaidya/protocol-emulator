import random

import cocotb
from cocotb.handle import LogicObject
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge
from cocotb.utils import get_sim_time
from cocotbext.uart import UartSink

from hostInterface import (
    Dut,
    baudRate,
    clkPeriodNs,
    clksPerBit,
    frameBits,
    readBytes,
    resetDutObject,
    sendByte,
    waitForReady,
)


async def measureLowCycles(signal: LogicObject) -> int:
    await FallingEdge(signal)
    fallTimeNs = get_sim_time(unit="ns")
    await RisingEdge(signal)
    return round((get_sim_time(unit="ns") - fallTimeNs) / clkPeriodNs)


async def sampleFrame(dut: Dut) -> list[int]:
    await FallingEdge(dut.uartTxPin)
    await ClockCycles(dut.clk, clksPerBit // 2)
    bits = []
    for _ in range(frameBits):
        bits.append(int(dut.uartTxPin.value))
        await ClockCycles(dut.clk, clksPerBit)
    return bits


@cocotb.test()
async def testIdleLineIsHighAndReady(dut: Dut) -> None:
    await resetDutObject(dut)
    await ClockCycles(dut.clk, 3 * clksPerBit)
    assert int(dut.uartTxPin.value) == 1, "TX line is not high after reset"
    assert int(dut.txReady.value) == 1, "txReady pin is not high after reset"


@cocotb.test()
async def testFrameHasExactBitTiming(dut: Dut) -> None:
    await resetDutObject(dut)
    data = 0x4B
    sampler = cocotb.start_soon(sampleFrame(dut))
    await sendByte(dut, data)
    bits = await sampler
    expected = [0] + [(data >> i) & 1 for i in range(8)] + [1]
    assert bits == expected, f"Frame bits {bits} do not match {expected}"


@cocotb.test()
async def testStartBitLastsOneBitPeriod(dut: Dut) -> None:
    await resetDutObject(dut)
    measurement = cocotb.start_soon(measureLowCycles(dut.uartTxPin))
    await sendByte(dut, 0x01)
    lowCycles = await measurement
    assert lowCycles == clksPerBit, f"start bit low for {lowCycles} cycles, expected {clksPerBit}"


@cocotb.test()
async def testReadyLowForTheWholeFrame(dut: Dut) -> None:
    await resetDutObject(dut)
    measurement = cocotb.start_soon(measureLowCycles(dut.txReady))
    await sendByte(dut, 0x3C)
    busyCycles = await measurement
    assert busyCycles == frameBits * clksPerBit, (
        f"txReady low for {busyCycles} cycles, expected {frameBits * clksPerBit}"
    )


@cocotb.test()
async def testRandomBytesMatchUartModel(dut: Dut) -> None:
    await resetDutObject(dut)
    sink = UartSink(dut.uartTxPin, baud=baudRate, bits=8)
    rng = random.Random(cocotb.RANDOM_SEED)
    sent = bytes(rng.randrange(256) for _ in range(16))
    for value in sent:
        await waitForReady(dut)
        await sendByte(dut, value)
    received = await readBytes(sink, len(sent))
    assert received == sent, f"received {received.hex()} expected {sent.hex()}"
