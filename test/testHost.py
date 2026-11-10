import random
from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles
from cocotbext.spi import SpiBus, SpiConfig
from cocotbext.spi.devices.generic import SpiSlaveLoopback
from cocotbext.uart import UartSink, UartSource

from asm.assembler import Program, assemble
from hostInterface import (
    Dut,
    Register,
    Status,
    clkFreqHz,
    configWords,
    idValue,
    loadProgram,
    readOne,
    readRegister,
    resetDut,
    startProgram,
    writeRegister,
)
from iss.core import CoreConfig

examplesDir = Path(__file__).resolve().parent.parent / "sw" / "asm" / "examples"
programWords = 256
addrBits = 8
byteShift = 8
txPin = 8
rxPin = 15
uartBaud = 500_000
spiSckPin = 9
spiMosiPin = 10
spiCsPin = 11
spiMisoPin = 16
byteMask = 0xFF


def loadExample(name: str) -> Program:
    return assemble((examplesDir / f"{name}.pasm").read_text())


@cocotb.test()
async def testIdRegisterReads(dut: Dut) -> None:
    await resetDut(dut)
    assert await readOne(dut, Register.id) == idValue


@cocotb.test()
async def testConfigRegistersReadBack(dut: Dut) -> None:
    await resetDut(dut)
    config = CoreConfig(
        clkDiv=1234, outBase=9, outCount=3, setBase=4, setCount=5, inBase=17, jmpPin=18
    )
    values = configWords(assemble(".side_set 2 opt\n.wrap_target\nnop\nnop\n.wrap\n"), config)
    values[Register.startPc] = 0x42
    values[Register.bypassLow] = 0xA5A5
    values[Register.bypassHigh] = 0x000F
    for register, value in values.items():
        await writeRegister(dut, register, [value])
    for register, value in values.items():
        assert await readOne(dut, register) == value, register.name


@cocotb.test()
async def testEveryAddressBitSelectsADistinctWord(dut: Dut) -> None:
    await resetDut(dut)
    addresses = [0] + [1 << bit for bit in range(addrBits)]
    for address in addresses:
        await writeRegister(dut, Register.memAddr, [address])
        await writeRegister(dut, Register.memData, [0xC000 | address])
    for address in addresses:
        await writeRegister(dut, Register.memAddr, [address])
        assert await readOne(dut, Register.memData) == 0xC000 | address


@cocotb.test()
async def testBurstLoadReadsBack(dut: Dut) -> None:
    await resetDut(dut)
    words = [random.getrandbits(16) for _ in range(32)]
    await loadProgram(dut, words, startAddress=programWords - 16)
    await writeRegister(dut, Register.memAddr, [programWords - 16])
    assert await readRegister(dut, Register.memData, len(words)) == words
    assert await readOne(dut, Register.memAddr) == (programWords - 16 + len(words)) % programWords


@cocotb.test()
async def testWriteWhileRunningIsRejected(dut: Dut) -> None:
    await resetDut(dut)
    await loadProgram(dut, [0x1111, 0x0000])
    await writeRegister(dut, Register.ctrl, [1])
    assert await readOne(dut, Register.status) & Status.active
    await writeRegister(dut, Register.memAddr, [0])
    await writeRegister(dut, Register.memData, [0x2222])
    assert await readOne(dut, Register.status) & Status.rejected
    await writeRegister(dut, Register.ctrl, [0])
    assert not await readOne(dut, Register.status) & Status.rejected
    await writeRegister(dut, Register.memAddr, [0])
    assert await readOne(dut, Register.memData) == 0x1111


@cocotb.test()
async def testHostExecuteRunsOneInstruction(dut: Dut) -> None:
    await resetDut(dut)
    for line in ("set x, 9", "set y, 7", "add x, y", "mov isr, x", "push"):
        await writeRegister(dut, Register.execute, assemble(line).words)
    assert await readOne(dut, Register.rxFifo) == 16
    assert await readOne(dut, Register.rxFifo) == 0
    assert not await readOne(dut, Register.status) & Status.rejected


@cocotb.test()
async def testRxFifoBurstReadsInOrder(dut: Dut) -> None:
    await resetDut(dut)
    for value in (3, 5, 7, 9):
        await writeRegister(dut, Register.execute, assemble(f"set x, {value}").words)
        await writeRegister(dut, Register.execute, assemble("mov isr, x").words)
        await writeRegister(dut, Register.execute, assemble("push noblock").words)
    assert await readRegister(dut, Register.rxFifo, 5) == [3, 5, 7, 9, 0]


@cocotb.test()
async def testUartTxFirmwareSendsBytes(dut: Dut) -> None:
    await resetDut(dut)
    clkDiv = clkFreqHz // (4 * uartBaud)
    config = CoreConfig(clkDiv=clkDiv, outBase=txPin, outCount=1, sideBase=txPin)
    sink = UartSink(dut.pin8, baud=uartBaud, bits=8)
    data = bytes([0x55, 0x00, 0xFF, 0xA3])
    await startProgram(dut, loadExample("uartTx"), config)
    await writeRegister(dut, Register.txFifo, list(data))
    received = bytearray()
    for _ in range(len(data)):
        received.extend(await sink.read(1))
    assert bytes(received) == data


@cocotb.test()
async def testUartRxFirmwareReceivesBytes(dut: Dut) -> None:
    await resetDut(dut)
    clkDiv = clkFreqHz // (8 * uartBaud)
    config = CoreConfig(clkDiv=clkDiv, inBase=rxPin, jmpPin=rxPin)
    source = UartSource(dut.pin15, baud=uartBaud, bits=8)
    data = bytes([0x5A, 0xC3, 0x01, 0xFE])
    await startProgram(dut, loadExample("uartRx"), config)
    await source.write(data)
    await source.wait()
    await ClockCycles(dut.clk, 200)
    words = await readRegister(dut, Register.rxFifo, len(data))
    assert bytes(word >> byteShift for word in words) == data


@cocotb.test()
async def testSpiFirmwareExchangesBytesWithLoopbackTarget(dut: Dut) -> None:
    await resetDut(dut)
    bus = SpiBus(dut, sclk_name="pin9", mosi_name="pin10", miso_name="pin16", cs_name="pin11")
    target = SpiSlaveLoopback(bus, SpiConfig(word_width=8, cpol=False, cpha=False))
    config = CoreConfig(
        clkDiv=2,
        outBase=spiMosiPin,
        outCount=1,
        setBase=spiCsPin,
        setCount=1,
        sideBase=spiSckPin,
        inBase=spiMisoPin,
        outShiftRight=False,
        inShiftRight=False,
    )
    sent = [0x9A, 0x00, 0xFF, 0x3C]
    await startProgram(dut, loadExample("spiMode0Cs"), config)
    await writeRegister(dut, Register.txFifo, [value << byteShift for value in sent])
    await ClockCycles(dut.clk, 1000)
    words = await readRegister(dut, Register.rxFifo, len(sent))
    assert [word & byteMask for word in words] == [0x00, *sent[:-1]]
    assert await target.get_contents() == sent[-1]
    assert int(dut.pin11.value) == 1
