from pathlib import Path

import pytest

from asm import isa
from asm.assembler import AsmError, assemble, main, toHex

examplesDir = Path(__file__).resolve().parent.parent / "examples"


def assembleExample(name: str) -> tuple[int, ...]:
    return assemble((examplesDir / f"{name}.pasm").read_text()).words


def assembleOne(line: str, header: str = "") -> int:
    words = assemble(f"{header}\n{line}\n").words
    assert len(words) == 1
    return words[0]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("uartTx", (0x9F40, 0xD647, 0x6001, 0x04BF)),
        ("uartRx", (0x2040, 0xD447, 0x4001, 0x0CBF, 0x0144, 0xE000, 0x2140, 0x0039, 0x8040)),
        ("spiMode0", (0x6201, 0x5201)),
        ("ws2812b", (0x6441, 0x1442, 0x163E, 0xA682)),
    ],
)
def testExamplesMatchHandEncoding(name: str, expected: tuple[int, ...]) -> None:
    assert assembleExample(name) == expected


def testWrapDirectivesSetBounds() -> None:
    lines = [".side_set 1", "nop side 0", ".wrap_target", "nop side 1", "nop side 0", ".wrap"]
    program = assemble("\n".join([*lines, "nop side 0"]))
    assert (program.wrapBottom, program.wrapTop) == (1, 2)


def testWrapDefaultsToWholeProgram() -> None:
    program = assemble("nop\nnop\nnop\n")
    assert (program.wrapBottom, program.wrapTop) == (0, 2)


def testSideSetDirectiveSetsConfig() -> None:
    program = assemble(".side_set 2 opt pindirs\nnop\n")
    assert program.sideSet == isa.SideSetConfig(2, True, True)
    assert program.sideSet.maxDelay == 1


def testLabelOnInstructionLine() -> None:
    program = assemble("top: nop\njmp top\n")
    assert program.labels == {"top": 0}
    assert program.words[1] == 0x003F


def testNumericJumpTargetIsAbsolute() -> None:
    assert assemble("nop\nnop\njmp 0\n").words[2] == 0x003E


def testForwardJumpAtMaximumOffset() -> None:
    source = "jmp end\n" + "nop\n" * 30 + "end: nop\n"
    assert assemble(source).words[0] == 0x001F


def testJumpOffsetOutOfRangeIsRejected() -> None:
    source = "jmp end\n" + "nop\n" * 31 + "end: nop\n"
    with pytest.raises(AsmError, match="jump offset"):
        assemble(source)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("add x, y", 0xA05A),
        ("sub t, x", 0xA0E1),
        ("and y, osr", 0xA0AE),
        ("or x, status", 0xA074),
        ("xor t, t", 0xA0FF),
        ("mov pins, ~x", 0xA009),
        ("mov isr, ::osr", 0xA196),
        ("mov exec, !t", 0xA10F),
    ],
)
def testMovOperations(line: str, expected: int) -> None:
    assert assembleOne(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("in null, 16", 0x40C0),
        ("out exec, 16", 0x61C0),
        ("out pc, 8", 0x6148),
        ("push iffull noblock", 0x8080),
        ("pull ifempty", 0x81C0),
        ("pull noblock", 0x8100),
        ("set pindirs, 63", 0xC13F),
        ("set t, 50", 0xC0F2),
        ("wait 1 gpio 31", 0x211F),
        ("wait 1 flag 7 timeout", 0x21A7),
        ("flag clear 3", 0xE083),
        ("flag wait 7", 0xE107),
        ("nop [15]", 0xBE82),
    ],
)
def testOperandEncoding(line: str, expected: int) -> None:
    assert assembleOne(line) == expected


def testKeywordsAreCaseInsensitive() -> None:
    assert assembleOne("SET X, 7") == assembleOne("set x, 7")


def testCommentsAreIgnored() -> None:
    assert assemble("; header\nnop // trailing\n").words == (0xA082,)


def testOptionalSideSetOmitted() -> None:
    assert assembleOne("nop [3]", ".side_set 1 opt") == 0xA682


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("", "no instructions"),
        ("bogus x\n", "unknown instruction"),
        (".bogus\nnop\n", "unknown directive"),
        ("nop\n.side_set 1\n", "before the first instruction"),
        (".side_set 1\nnop\n", "not optional"),
        ("nop side 1\n", "needs a '.side_set'"),
        (".side_set 1\nnop side 2\n", "side-set value"),
        (".side_set 1 opt\nnop [4]\n", "delay"),
        ("nop [16]\n", "delay"),
        (".side_set 4\nnop\n", "sideCount"),
        ("a: nop\na: nop\n", "duplicate label"),
        ("jmp nowhere\n", "invalid number"),
        ("jmp sometimes 0\n", "jmp condition"),
        ("set x, 64\n", "set data"),
        ("set osr, 1\n", "set destination"),
        ("in pins, 0\n", "bit count"),
        ("in pindirs, 1\n", "in source"),
        ("add pins, x\n", "destination must be"),
        ("mov x\n", "needs 2 operands"),
        ("wait 2 pin 0\n", "polarity"),
        ("wait 1 flag 8\n", "index"),
        ("push ifempty\n", "option"),
        ("pull block noblock\n", "not both"),
        ("flag toggle 0\n", "flag operation"),
        (".wrap\nnop\n", "after an instruction"),
        ("nop\n.wrap_target\n", "before an instruction"),
    ],
)
def testInvalidSourceIsRejected(source: str, message: str) -> None:
    with pytest.raises(AsmError, match=message):
        assemble(source)


def testErrorReportsLineNumber() -> None:
    with pytest.raises(AsmError) as errorInfo:
        assemble("nop\nnop\nset x, 99\n")
    assert errorInfo.value.lineNumber == 3


def testProgramLimitIsEnforced() -> None:
    assert len(assemble("nop\n" * isa.programWords).words) == isa.programWords
    with pytest.raises(AsmError, match="limit"):
        assemble("nop\n" * (isa.programWords + 1))


def testMainWritesReadmemhFile(tmp_path: Path) -> None:
    output = tmp_path / "uartTx.hex"
    assert main([str(examplesDir / "uartTx.pasm"), "-o", str(output)]) == 0
    assert output.read_text() == "9f40\nd647\n6001\n04bf\n"


def testMainReportsErrors(tmp_path: Path) -> None:
    source = tmp_path / "bad.pasm"
    source.write_text("bogus\n")
    assert main([str(source), "-o", str(tmp_path / "bad.hex")]) == 1


def testToHexHasOneWordPerLine() -> None:
    assert toHex(assemble("nop\njmp 0\n")) == "a082\n003f\n"
