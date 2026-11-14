from bisect import bisect_right
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

byteBits = 8
uartFrameBits = 10


class ProtocolError(Exception):
    pass


class PinRecorder:
    def __init__(self, pin: int) -> None:
        self.pin = pin
        self.edges: list[tuple[int, int]] = []
        self._edgeCycles: list[int] = []

    def sample(self, cycle: int, outputs: int) -> None:
        level = (outputs >> self.pin) & 1
        if not self.edges or self.edges[-1][1] != level:
            self.edges.append((cycle, level))
            self._edgeCycles.append(cycle)

    def levelAt(self, cycle: int) -> int:
        index = bisect_right(self._edgeCycles, cycle) - 1
        return self.edges[index][1] if index >= 0 else 0

    def pulses(self) -> list[tuple[int, int]]:
        return [
            (level, nextCycle - cycle)
            for (cycle, level), (nextCycle, _) in zip(self.edges, self.edges[1:])
        ]


@dataclass(frozen=True)
class UartFrame:
    data: int
    stopLevel: int = 1


class UartSource:
    def __init__(
        self, frames: Sequence[UartFrame], cyclesPerBit: float, startCycle: int
    ) -> None:
        self.frames = frames
        self.cyclesPerBit = cyclesPerBit
        self.startCycle = startCycle

    def level(self, cycle: int) -> int:
        bitIndex = int((cycle - self.startCycle) // self.cyclesPerBit)
        frameIndex, bitInFrame = divmod(bitIndex, uartFrameBits)
        if cycle < self.startCycle or frameIndex >= len(self.frames):
            return 1
        frame = self.frames[frameIndex]
        if bitInFrame == 0:
            return 0
        if bitInFrame > byteBits:
            return frame.stopLevel
        return (frame.data >> (bitInFrame - 1)) & 1


def decodeUart(recorder: PinRecorder, cyclesPerBit: int, fromCycle: int = 1) -> list[int]:
    received = []
    for edgeCycle, level in recorder.edges:
        if level != 0 or edgeCycle < fromCycle:
            continue
        data = 0
        for bit in range(byteBits):
            center = edgeCycle + cyclesPerBit * (bit + 1) + cyclesPerBit // 2
            data |= recorder.levelAt(center) << bit
        stopCenter = edgeCycle + cyclesPerBit * (uartFrameBits - 1) + cyclesPerBit // 2
        if recorder.levelAt(stopCenter) != 1:
            raise ProtocolError(f"framing error in the frame at cycle {edgeCycle}")
        received.append(data)
        fromCycle = stopCenter
    return received


class SpiTarget:
    def __init__(self, responses: Iterable[int]) -> None:
        self._responses = deque(responses)
        self.received: list[int] = []
        self._rxShift = 0
        self._rxBits = 0
        self._txShift = self._nextResponse()
        self._previousSck = 0

    def _nextResponse(self) -> int:
        return self._responses.popleft() if self._responses else 0

    @property
    def miso(self) -> int:
        return (self._txShift >> 7) & 1

    def update(self, sck: int, mosi: int) -> None:
        if sck and not self._previousSck:
            self._rxShift = ((self._rxShift << 1) | mosi) & 0xFF
            self._rxBits += 1
            if self._rxBits == byteBits:
                self.received.append(self._rxShift)
                self._rxBits = 0
        if self._previousSck and not sck:
            self._txShift = (self._txShift << 1) & 0xFF
            if self._rxBits == 0:
                self._txShift = self._nextResponse()
        self._previousSck = sck


i2cStartBit = 15
i2cStopBit = 14
i2cDataShift = 6
i2cAckShift = 5
i2cResultBits = byteBits + 1


def i2cWrite(data: int, start: bool = False, stop: bool = False) -> int:
    return (
        (int(start) << i2cStartBit)
        | (int(stop) << i2cStopBit)
        | ((data & 0xFF) << i2cDataShift)
        | (1 << i2cAckShift)
    )


def i2cRead(ack: bool, stop: bool = False) -> int:
    return (int(stop) << i2cStopBit) | (0xFF << i2cDataShift) | (int(not ack) << i2cAckShift)


def i2cResult(word: int) -> tuple[int, bool]:
    return (word >> 1) & 0xFF, not word & 1


class I2cTarget:
    def __init__(self, address: int, readData: Iterable[int] = (), stretchCycles: int = 0) -> None:
        self.address = address
        self.stretchCycles = stretchCycles
        self.received: list[int] = []
        self.controllerAcks: list[bool] = []
        self.starts = 0
        self.stops = 0
        self.sdaDrive = False
        self.sclDrive = False
        self._readData = deque(readData)
        self._state = "idle"
        self._isRead = False
        self._clockCount = 0
        self._shift = 0
        self._txByte = 0
        self._stretchLeft = 0
        self._previousScl = 1
        self._previousSda = 1

    def update(self, scl: int, sda: int) -> None:
        if self._stretchLeft:
            self._stretchLeft -= 1
            self.sclDrive = self._stretchLeft > 0
        if scl and self._previousScl and sda != self._previousSda:
            self._busCondition(sda)
        elif scl and not self._previousScl:
            self._rising(sda)
        elif self._previousScl and not scl:
            self._falling()
        self._previousScl = scl
        self._previousSda = sda

    def _busCondition(self, sda: int) -> None:
        self.sdaDrive = False
        self._clockCount = 0
        self._shift = 0
        if sda:
            self.stops += 1
            self._state = "idle"
        else:
            self.starts += 1
            self._state = "address"

    def _rising(self, sda: int) -> None:
        if self._state in ("idle", "ignore"):
            return
        self._clockCount += 1
        if self._clockCount <= byteBits and self._state != "read":
            self._shift = ((self._shift << 1) | sda) & 0xFF
        if self._clockCount == i2cResultBits and self._state == "read":
            self.controllerAcks.append(not sda)

    def _falling(self) -> None:
        if self._state in ("idle", "ignore") or self._clockCount == 0:
            return
        if self._clockCount == byteBits:
            self._endOfByte()
        elif self._clockCount == i2cResultBits:
            self._endOfAck()
        elif self._state == "read":
            self.sdaDrive = not (self._txByte >> (byteBits - 1 - self._clockCount)) & 1

    def _endOfByte(self) -> None:
        if self._state == "address":
            if self._shift >> 1 != self.address:
                self._state = "ignore"
                return
            self._isRead = bool(self._shift & 1)
            self.sdaDrive = True
        elif self._state == "write":
            self.received.append(self._shift)
            self.sdaDrive = True
        else:
            self.sdaDrive = False

    def _endOfAck(self) -> None:
        self._clockCount = 0
        self._shift = 0
        self.sdaDrive = False
        if self._state == "address":
            self._state = "read" if self._isRead else "write"
        elif self._state == "read" and not self.controllerAcks[-1]:
            self._state = "ignore"
            return
        if self._state == "read":
            self._txByte = self._readData.popleft() if self._readData else 0xFF
            self.sdaDrive = not (self._txByte >> (byteBits - 1)) & 1
        if self.stretchCycles:
            self.sclDrive = True
            self._stretchLeft = self.stretchCycles
