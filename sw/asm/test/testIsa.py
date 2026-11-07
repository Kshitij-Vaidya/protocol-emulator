import itertools

import pytest

from asm import isa

sideSetConfigs = [
    isa.SideSetConfig(sideCount, sideEn)
    for sideCount, sideEn in itertools.product(range(4), (False, True))
    if not (sideEn and sideCount == 0)
]


@pytest.mark.parametrize("sideSet", sideSetConfigs)
def testTimingFieldRoundTrips(sideSet: isa.SideSetConfig) -> None:
    sides: list[int | None] = list(range(sideSet.maxSide + 1)) if sideSet.sideCount else []
    if sideSet.sideEn or not sideSet.sideCount:
        sides.append(None)
    for side, delay in itertools.product(sides, range(sideSet.maxDelay + 1)):
        field = sideSet.packTiming(side, delay)
        assert 0 <= field <= isa.timingMask
        assert sideSet.unpackTiming(field) == (side, delay)
