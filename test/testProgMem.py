import random

import cocotb
from cocotbext.uart import UartSink

from hostInterface import Dut, baudRate, readWord, resetDutObject, writeWord

memDepth = 256
wordMask = 0xFFFF


def addressPattern(addr: int) -> int:
    return ((addr ^ 0xA5) << 8) | addr


async def checkWord(dut: Dut, sink: UartSink, addr: int, expected: int) -> None:
    actual = await readWord(dut, sink, addr)
    assert actual == expected, f"word {addr:#04x} is {actual:#06x}, expected {expected:#06x}"


@cocotb.test()
async def testEveryAddressBitSelectsADistinctWord(dut: Dut) -> None:
    await resetDutObject(dut)
    sink = UartSink(dut.uartTxPin, baud=baudRate, bits=8)
    for addr in range(memDepth):
        await writeWord(dut, addr, addressPattern(addr))
    probeAddrs = [0, memDepth - 1] + [1 << bit for bit in range(8)]
    for addr in probeAddrs:
        await checkWord(dut, sink, addr, addressPattern(addr))


@cocotb.test()
async def testRandomWordsReadBack(dut: Dut) -> None:
    await resetDutObject(dut)
    sink = UartSink(dut.uartTxPin, baud=baudRate, bits=8)
    rng = random.Random(cocotb.RANDOM_SEED)
    written = {addr: rng.randrange(wordMask + 1) for addr in rng.sample(range(memDepth), 16)}
    for addr, word in written.items():
        await writeWord(dut, addr, word)
    readOrder = list(written)
    rng.shuffle(readOrder)
    for addr in readOrder:
        await checkWord(dut, sink, addr, written[addr])


@cocotb.test()
async def testOverwriteReplacesWord(dut: Dut) -> None:
    await resetDutObject(dut)
    sink = UartSink(dut.uartTxPin, baud=baudRate, bits=8)
    await writeWord(dut, 0x42, 0x1234)
    await writeWord(dut, 0x43, 0xFFFF)
    await writeWord(dut, 0x42, 0xBEEF)
    await checkWord(dut, sink, 0x42, 0xBEEF)
    await checkWord(dut, sink, 0x43, 0xFFFF)
