import random
from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge
from cocotbext.i2c import I2cMemory
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
from iss.models import i2cRead, i2cResult, i2cWrite

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
sdaPin = 0
sclPin = 1
i2cAddress = 0x50
fifoDepth = 4
rxLevelShift = 5
rxLevelMask = 0x7
stretchCycles = 100


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


@cocotb.test()
async def testClockDividerWriteWhileRunningTakesEffect(dut: Dut) -> None:
    await resetDut(dut)
    program = assemble(".wrap_target\nset pins, 1\nset pins, 0\n.wrap\n")
    config = CoreConfig(clkDiv=60000, setBase=txPin, setCount=1)
    await startProgram(dut, program, config)
    await ClockCycles(dut.clk, 2000)
    await writeRegister(dut, Register.clkDiv, [1])
    levels = set()
    for _ in range(200):
        await ClockCycles(dut.clk, 1)
        levels.add(int(dut.pin8.value))
    assert levels == {0, 1}


class StretchingMemory(I2cMemory):
    def __init__(self, dut: Dut, cycles: int, address: int) -> None:
        self._clk = dut.clk
        self._cycles = cycles
        super().__init__(
            sda=dut.sda, sda_o=dut.sdaTarget, scl=dut.scl, scl_o=dut.sclTarget, addr=address
        )

    async def handle_write(self, data: int) -> None:
        await ClockCycles(self._clk, self._cycles)
        await super().handle_write(data)


class LowMonitor:
    def __init__(self, dut: Dut) -> None:
        self.longest = 0
        cocotb.start_soon(self._run(dut))

    async def _run(self, dut: Dut) -> None:
        current = 0
        while True:
            await RisingEdge(dut.clk)
            current = current + 1 if not int(dut.scl.value) else 0
            self.longest = max(self.longest, current)


async def rxLevel(dut: Dut) -> int:
    return (await readOne(dut, Register.status) >> rxLevelShift) & rxLevelMask


async def i2cTransfer(dut: Dut, words: list[int]) -> list[tuple[int, bool]]:
    results: list[tuple[int, bool]] = []
    for first in range(0, len(words), fifoDepth):
        chunk = words[first : first + fifoDepth]
        await writeRegister(dut, Register.txFifo, chunk)
        for _ in range(200):
            if await rxLevel(dut) == len(chunk):
                break
            await ClockCycles(dut.clk, 100)
        results.extend(i2cResult(word) for word in await readRegister(dut, Register.rxFifo, len(chunk)))
    return results


@cocotb.test()
async def testI2cFirmwareWritesAndReadsI2cMemory(dut: Dut) -> None:
    await resetDut(dut)
    memory = StretchingMemory(dut, stretchCycles, i2cAddress)
    sclLow = LowMonitor(dut)
    memory.write_mem(0x20, bytes([0x5E, 0xA1]))
    config = CoreConfig(
        clkDiv=4,
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
    await startProgram(dut, loadExample("i2cController"), config)
    writeAddress = i2cAddress << 1
    readAddress = writeAddress | 1
    written = await i2cTransfer(
        dut,
        [i2cWrite(writeAddress, start=True), i2cWrite(0x10), i2cWrite(0xC3), i2cWrite(0x3C, stop=True)],
    )
    assert written == [(writeAddress, True), (0x10, True), (0xC3, True), (0x3C, True)]
    assert memory.read_mem(0x10, 2) == bytes([0xC3, 0x3C])
    read = await i2cTransfer(
        dut,
        [
            i2cWrite(writeAddress, start=True),
            i2cWrite(0x20),
            i2cWrite(readAddress, start=True),
            i2cRead(ack=True),
            i2cRead(ack=False, stop=True),
        ],
    )
    assert read == [
        (writeAddress, True),
        (0x20, True),
        (readAddress, True),
        (0x5E, True),
        (0xA1, False),
    ]
    assert int(dut.sda.value) == 1
    assert int(dut.scl.value) == 1
    assert sclLow.longest >= stretchCycles
