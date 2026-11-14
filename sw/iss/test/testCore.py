from collections.abc import Callable

import pytest

from asm import isa
from asm.assembler import Program, assemble
from iss.core import CoreConfig, IssError
from iss.machine import Machine
from iss.models import PinRecorder

firstOutput = 8
inputPin = 15


def recordPin(
    machine: Machine, cycles: int, pin: int = firstOutput, inputRise: int | None = None
) -> list[tuple[int, int]]:
    recorder = PinRecorder(pin)

    def environment(cycle: int, outputs: int) -> int:
        recorder.sample(cycle, outputs)
        isHigh = inputRise is not None and cycle >= inputRise
        return int(isHigh) << inputPin

    machine.run(cycles, environment)
    return recorder.edges


def readWords(machine: Machine, count: int, maxCycles: int = 1000) -> list[int]:
    core = machine.cores[0]
    words: list[int] = []
    for _ in range(maxCycles):
        machine.step(0)
        word = core.hostRead()
        if word is not None:
            words.append(word)
        if len(words) == count:
            return words
    raise AssertionError(f"received {words}, expected {count} words")


def singleCore(source: str, clkDiv: int = 1) -> Machine:
    config = CoreConfig(clkDiv=clkDiv, setBase=firstOutput, setCount=2)
    return Machine([(assemble(source), config)])


def testDelayAddsTicksAfterInstruction() -> None:
    machine = singleCore("set pins, 1 [3]\nset pins, 0 [1]\n")
    assert recordPin(machine, 14) == [(0, 0), (1, 1), (5, 0), (7, 1), (11, 0), (13, 1)]


def testClockDividerScalesTicks() -> None:
    machine = singleCore("set pins, 1\nset pins, 0 [1]\n", clkDiv=3)
    assert recordPin(machine, 20) == [(0, 0), (1, 1), (4, 0), (10, 1), (13, 0), (19, 1)]


def testSideSetAppliesWhileStalled() -> None:
    source = ".side_set 1\npull side 1\n"
    machine = Machine([(assemble(source), CoreConfig(sideBase=firstOutput))])
    assert recordPin(machine, 10) == [(0, 0), (1, 1)]
    assert machine.cores[0].pc == 0


@pytest.mark.parametrize(("syncBypass", "expectedEdge"), [(0, 16), (1 << inputPin, 14)])
def testDelayStartsAfterWaitAndInputIsSynchronized(syncBypass: int, expectedEdge: int) -> None:
    program = assemble(f"wait 1 gpio {inputPin} [2]\nset pins, 1\nwait 1 flag 0\n")
    machine = Machine([(program, CoreConfig(setBase=firstOutput, setCount=1))], syncBypass)
    assert recordPin(machine, 30, inputRise=10) == [(0, 0), (expectedEdge, 1)]


timeoutSource = f"""
    set t, 5
    wait 1 gpio {inputPin} timeout
    jmp timeout failed
    set pins, 1
passed:
    jmp passed
failed:
    set pins, 2
    jmp failed
"""


def testSyncBypassAppliesOnlyToSelectedPins() -> None:
    otherPin = inputPin + 1
    program = assemble("nop\nmov isr, pins\npush\nwait 1 flag 7\n")
    machine = Machine([(program, CoreConfig(inBase=inputPin))], syncBypass=1 << inputPin)
    bothHigh = (1 << inputPin) | (1 << otherPin)
    for inputs in (0, bothHigh, bothHigh):
        machine.step(inputs)
    assert machine.cores[0].hostRead() == 0b01


def testWaitTimesOutAfterTTicks() -> None:
    machine = singleCore(timeoutSource)
    assert recordPin(machine, 20, pin=firstOutput + 1) == [(0, 0), (9, 1)]
    assert machine.cores[0].timeoutFlag


def testWaitWithoutTimeoutContinues() -> None:
    machine = singleCore(timeoutSource)
    assert recordPin(machine, 20, inputRise=2) == [(0, 0), (7, 1)]
    assert not machine.cores[0].timeoutFlag


def testAluOperationsWrapAt16Bits() -> None:
    source = """
        set x, 50
        set y, 7
        add x, y
        mov isr, x
        push
        set x, 0
        sub x, y
        mov isr, x
        push
        xor x, y
        mov isr, x
        push
        mov x, ::y
        mov isr, x
        push
        mov x, ~null
        and x, y
        or x, t
        mov isr, x
        push
    """
    assert readWords(singleCore(source), 5) == [57, 0xFFF9, 0xFFFE, 0xE000, 7]


def testDecrementLoopCountsDownAndAlwaysDecrements() -> None:
    source = "set x, 3\nloop: jmp x-- loop\nmov isr, x\npush\n"
    assert readWords(singleCore(source), 1) == [0xFFFF]


def testOutExecRunsWordWithoutPcAdvance() -> None:
    machine = singleCore("pull\nout exec, 16\nmov isr, x\npush\n")
    machine.cores[0].hostWrite(assemble("set x, 9").words[0])
    assert readWords(machine, 1) == [9]


def testMovPcJumps() -> None:
    source = "set x, 3\nmov pc, x\nset x, 1\nmov isr, x\npush\n"
    assert readWords(singleCore(source), 1) == [3]


def testPullNoblockCopiesXWhenEmpty() -> None:
    assert readWords(singleCore("set x, 5\npull noblock\nmov isr, osr\npush\n"), 1) == [5]


def testPushNoblockDropsWhenFull() -> None:
    source = "set x, 1\nloop:\nmov isr, x\npush noblock\nadd x, x\njmp loop\n"
    machine = singleCore(source)
    machine.run(100, lambda cycle, outputs: 0)
    assert list(machine.cores[0].rxFifo) == [1, 2, 4, 8]


def testWaitOnFlagClearsFlag() -> None:
    first = assemble("wait 1 flag 2\nmov isr, status\npush\n")
    second = assemble("flag set 2\nwait 1 flag 7\n")
    machine = Machine([(first, CoreConfig()), (second, CoreConfig())])
    assert readWords(machine, 1) == [0x0001]


def testFlagWaitStallsUntilOtherCoreClears() -> None:
    first = assemble("flag wait 3\nset pins, 1\nwait 1 flag 7\n")
    second = assemble("nop [7]\nflag clear 3\nwait 1 flag 7\n")
    config = CoreConfig(setBase=firstOutput, setCount=1)
    machine = Machine([(first, config), (second, CoreConfig())])
    assert recordPin(machine, 20) == [(0, 0), (11, 1)]


def testFlagChangeIsVisibleToOtherCoresOnNextCycle() -> None:
    first = assemble("flag set 1\nwait 1 flag 7\n")
    second = assemble("wait 1 flag 1\nset pins, 1\nwait 1 flag 7\n")
    config = CoreConfig(setBase=firstOutput, setCount=1)
    machine = Machine([(first, CoreConfig()), (second, config)])
    assert recordPin(machine, 10) == [(0, 0), (3, 1)]


def testFlagSetWinsOverClearOnSameCycle() -> None:
    first = assemble("flag set 4\nwait 1 flag 7\n")
    second = assemble("flag clear 4\nwait 1 flag 7\n")
    machine = Machine([(first, CoreConfig()), (second, CoreConfig())])
    machine.step(0)
    assert machine.flags.isSet(4)


def testTwoCoresWaitingOnOneFlagBothContinue() -> None:
    waiter = assemble("wait 1 flag 2\nset pins, 1\nwait 1 flag 7\n")
    setter = assemble("nop [3]\nflag set 2\nwait 1 flag 7\n")
    machine = Machine(
        [
            (waiter, CoreConfig(setBase=firstOutput, setCount=1)),
            (waiter, CoreConfig(setBase=firstOutput + 1, setCount=1)),
            (setter, CoreConfig()),
        ]
    )
    first = PinRecorder(firstOutput)
    second = PinRecorder(firstOutput + 1)

    def environment(cycle: int, outputs: int) -> int:
        first.sample(cycle, outputs)
        second.sample(cycle, outputs)
        return 0

    machine.run(12, environment)
    assert first.edges == second.edges == [(0, 0), (7, 1)]
    assert not machine.flags.isSet(2)


def testBidirectionalPinDrivesOnlyWhenEnabled() -> None:
    program = assemble("set pins, 1\nset pindirs, 1\nwait 1 flag 7\n")
    machine = Machine([(program, CoreConfig(setCount=1))])
    machine.step(0)
    assert (machine.outputs & 1, machine.outputEnables & 1) == (0, 0)
    machine.step(0)
    assert (machine.outputs & 1, machine.outputEnables & 1) == (1, 1)


def testReservedEncodingRaises() -> None:
    reservedSet = isa.encode(isa.Opcode.set, 0, 5 << isa.fieldShift)
    program = Program((reservedSet,), {}, isa.SideSetConfig(), 0, 0)
    machine = Machine([(program, CoreConfig())])
    with pytest.raises(IssError, match="reserved SET destination"):
        machine.step(0)


@pytest.mark.parametrize(
    "makeConfig",
    [
        lambda: CoreConfig(clkDiv=0),
        lambda: CoreConfig(clkDiv=65536),
        lambda: CoreConfig(outBase=32),
        lambda: CoreConfig(setCount=7),
        lambda: CoreConfig(pullThreshold=0),
    ],
)
def testInvalidConfigIsRejected(makeConfig: Callable[[], CoreConfig]) -> None:
    with pytest.raises(ValueError):
        makeConfig()
