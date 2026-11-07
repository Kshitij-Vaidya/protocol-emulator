from collections import deque
from collections.abc import Callable, Sequence

from asm.assembler import Program
from iss.core import Core, CoreConfig, FlagBank

bidirectionalMask = 0xFF
outputOnlyMask = 0x7F << 8
inputMask = bidirectionalMask | (0x1F << 15)

Environment = Callable[[int, int], int]


class Machine:
    def __init__(
        self, cores: Sequence[tuple[Program, CoreConfig]], syncStages: int = 2
    ) -> None:
        self.flags = FlagBank()
        self.cores = [Core(program, config, self.flags) for program, config in cores]
        self.cycle = 0
        self._syncStages = syncStages
        self._syncPipe: deque[int] = deque()

    @property
    def outputEnables(self) -> int:
        enables = 0
        for core in self.cores:
            enables |= (core.pinDir & bidirectionalMask) | outputOnlyMask
        return enables

    @property
    def outputs(self) -> int:
        levels = 0
        for core in self.cores:
            levels |= core.pinOut & ((core.pinDir & bidirectionalMask) | outputOnlyMask)
        return levels

    def step(self, inputs: int) -> None:
        inputs &= inputMask
        if not self._syncPipe:
            self._syncPipe.extend([inputs] * self._syncStages)
        self._syncPipe.append(inputs)
        synchronized = self._syncPipe.popleft()
        for core in self.cores:
            core.clock(synchronized)
        self.cycle += 1

    def run(self, cycles: int, environment: Environment) -> None:
        for _ in range(cycles):
            self.step(environment(self.cycle, self.outputs))
