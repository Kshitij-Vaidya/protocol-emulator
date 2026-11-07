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
