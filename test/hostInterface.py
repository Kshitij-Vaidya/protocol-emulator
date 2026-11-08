from collections.abc import Sequence
from enum import IntEnum
from typing import Protocol

import cocotb
from cocotb.clock import Clock
from cocotb.handle import LogicArrayObject, LogicObject
from cocotb.triggers import ClockCycles, FallingEdge

from asm.assembler import Program
from iss.core import CoreConfig

clkPeriodNs = 20
clkFreqHz = 50_000_000
sckHalfPeriodCycles = 8
wordBits = 16
commandBits = 8
writeFlag = 0x80
idValue = 0x5045


class Dut(Protocol):
    clk: LogicObject
    rst_n: LogicObject
    ena: LogicObject
    hostSck: LogicObject
    hostCsN: LogicObject
    hostMosi: LogicObject
    hostMiso: LogicObject
    pin15: LogicObject
    pins16To19: LogicArrayObject
    pin8: LogicObject
    uio_in: LogicArrayObject
    uio_out: LogicArrayObject
    uio_oe: LogicArrayObject
    uo_out: LogicArrayObject


class Register(IntEnum):
    ctrl = 0x00
    status = 0x01
    memAddr = 0x02
    memData = 0x03
    startPc = 0x04
    execute = 0x05
    clkDiv = 0x06
    pinOut = 0x07
    pinSet = 0x08
    pinSide = 0x09
    pinIn = 0x0A
    shift = 0x0B
    wrap = 0x0C
    txFifo = 0x0D
    rxFifo = 0x0E
    bypassLow = 0x0F
    bypassHigh = 0x10
    id = 0x11


class Status(IntEnum):
    active = 1 << 0
    rejected = 1 << 1


async def resetDut(dut: Dut) -> None:
    cocotb.start_soon(Clock(dut.clk, clkPeriodNs, unit="ns").start())
    dut.ena.value = 1
    dut.hostSck.value = 0
    dut.hostCsN.value = 1
    dut.hostMosi.value = 0
    dut.pin15.value = 1
    dut.pins16To19.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 4)


async def _halfPeriod(dut: Dut) -> None:
    await ClockCycles(dut.clk, sckHalfPeriodCycles, rising=False)


async def _exchangeBits(dut: Dut, value: int, bitCount: int) -> int:
    received = 0
    for bit in reversed(range(bitCount)):
        dut.hostMosi.value = (value >> bit) & 1
        await _halfPeriod(dut)
        misoLevel = dut.hostMiso.value
        received = (received << 1) | (int(misoLevel) if misoLevel.is_resolvable else 0)
        dut.hostSck.value = 1
        await _halfPeriod(dut)
        dut.hostSck.value = 0
    return received


async def _transfer(dut: Dut, command: int, words: Sequence[int]) -> list[int]:
    await FallingEdge(dut.clk)
    dut.hostCsN.value = 0
    await _halfPeriod(dut)
    await _exchangeBits(dut, command, commandBits)
    received = [await _exchangeBits(dut, word, wordBits) for word in words]
    await _halfPeriod(dut)
    dut.hostCsN.value = 1
    await _halfPeriod(dut)
    return received


async def writeRegister(dut: Dut, register: Register, words: Sequence[int]) -> None:
    await _transfer(dut, writeFlag | register, words)


async def readRegister(dut: Dut, register: Register, count: int = 1) -> list[int]:
    return await _transfer(dut, register, [0] * count)


async def readOne(dut: Dut, register: Register) -> int:
    return (await readRegister(dut, register))[0]


async def loadProgram(dut: Dut, words: Sequence[int], startAddress: int = 0) -> None:
    await writeRegister(dut, Register.memAddr, [startAddress])
    await writeRegister(dut, Register.memData, words)


def configWords(program: Program, config: CoreConfig) -> dict[Register, int]:
    sideSet = program.sideSet
    return {
        Register.clkDiv: config.clkDiv,
        Register.pinOut: config.outBase | (config.outCount << 8),
        Register.pinSet: config.setBase | (config.setCount << 8),
        Register.pinSide: config.sideBase
        | (sideSet.sideCount << 8)
        | (int(sideSet.sideEn) << 10)
        | (int(sideSet.sidePinDir) << 11),
        Register.pinIn: config.inBase | (config.jmpPin << 8),
        Register.shift: int(config.outShiftRight)
        | (int(config.inShiftRight) << 1)
        | (int(config.autoPull) << 2)
        | (int(config.autoPush) << 3)
        | (config.pullThreshold << 4)
        | (config.pushThreshold << 9),
        Register.wrap: program.wrapBottom | (program.wrapTop << 8),
    }


async def startProgram(dut: Dut, program: Program, config: CoreConfig, syncBypass: int = 0) -> None:
    await loadProgram(dut, program.words)
    for register, value in configWords(program, config).items():
        await writeRegister(dut, register, [value])
    await writeRegister(dut, Register.bypassLow, [syncBypass & 0xFFFF])
    await writeRegister(dut, Register.bypassHigh, [syncBypass >> 16])
    await writeRegister(dut, Register.ctrl, [0b11])
