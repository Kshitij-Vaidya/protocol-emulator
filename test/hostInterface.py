from enum import IntEnum
from typing import Protocol

import cocotb
from cocotb.clock import Clock
from cocotb.handle import LogicArrayObject, LogicObject
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.uart import UartSink

clkPeriodNs = 20
clkFreqHz = 50_000_000
baudRate = 115_200
clksPerBit = round(clkFreqHz / baudRate)
frameBits = 10
syncLatencyCycles = 3
holdCycles = 4
sendBit = 1 << 0
cmdShift = 1
byteSelShift = 3
byteMask = 0xFF
byteWidth = 8


class Dut(Protocol):
    clk: LogicObject
    rst_n: LogicObject
    ena: LogicObject
    ui_in: LogicArrayObject
    uio_in: LogicArrayObject
    uartTxPin: LogicObject
    txReady: LogicObject


class Command(IntEnum):
    idle = 0b00
    setAddr = 0b01
    writeLow = 0b10
    writeHigh = 0b11


async def resetDutObject(dut: Dut) -> None:
    cocotb.start_soon(Clock(dut.clk, clkPeriodNs, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def applyCommand(dut: Dut, command: Command, data: int) -> None:
    dut.uio_in.value = Command.idle << cmdShift
    await ClockCycles(dut.clk, holdCycles)
    dut.ui_in.value = data
    await ClockCycles(dut.clk, holdCycles)
    dut.uio_in.value = command << cmdShift
    await ClockCycles(dut.clk, holdCycles)
    dut.uio_in.value = Command.idle << cmdShift
    await ClockCycles(dut.clk, holdCycles)


async def writeWord(dut: Dut, addr: int, word: int) -> None:
    await applyCommand(dut, Command.setAddr, addr)
    await applyCommand(dut, Command.writeLow, word & byteMask)
    await applyCommand(dut, Command.writeHigh, word >> byteWidth)


async def pressSend(dut: Dut, byteSel: int) -> None:
    selectBits = byteSel << byteSelShift
    dut.uio_in.value = selectBits
    await ClockCycles(dut.clk, holdCycles)
    dut.uio_in.value = selectBits | sendBit
    await ClockCycles(dut.clk, syncLatencyCycles + 1)
    dut.uio_in.value = selectBits
    await ClockCycles(dut.clk, syncLatencyCycles)


async def sendByte(dut: Dut, data: int) -> None:
    await writeWord(dut, 0, data)
    await pressSend(dut, 0)


async def waitForReady(dut: Dut) -> None:
    while int(dut.txReady.value) == 0:
        await RisingEdge(dut.clk)


async def readBytes(sink: UartSink, count: int) -> bytes:
    received = bytearray()
    while len(received) < count:
        received.extend(await sink.read(1))
    return bytes(received)


async def readWord(dut: Dut, sink: UartSink, addr: int) -> int:
    await applyCommand(dut, Command.setAddr, addr)
    for byteSel in (0, 1):
        await waitForReady(dut)
        await pressSend(dut, byteSel)
    received = await readBytes(sink, 2)
    return int.from_bytes(received, "little")
