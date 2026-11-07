import argparse
import logging
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from asm import isa

logger = logging.getLogger(__name__)

commentPattern = re.compile(r"(;|//).*$")
labelPattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:")
delayPattern = re.compile(r"\[\s*([^\]]*?)\s*\]\s*$")
sidePattern = re.compile(r"(?:^|\s)side\s+(\S+)\s*$", re.IGNORECASE)


class AsmError(Exception):
    def __init__(self, lineNumber: int, message: str) -> None:
        super().__init__(f"line {lineNumber}: {message}")
        self.lineNumber = lineNumber


@dataclass(frozen=True)
class Program:
    words: tuple[int, ...]
    labels: Mapping[str, int]
    sideSet: isa.SideSetConfig
    wrapBottom: int
    wrapTop: int


@dataclass(frozen=True)
class _Statement:
    lineNumber: int
    address: int
    mnemonic: str
    operands: list[str]
    side: int | None
    delay: int


_Encoder = Callable[[_Statement, Mapping[str, int]], tuple[isa.Opcode, int]]


def _parseNumber(text: str, lineNumber: int) -> int:
    try:
        return int(text, 0)
    except ValueError:
        raise AsmError(lineNumber, f"invalid number '{text}'") from None


def _checkRange(value: int, low: int, high: int, what: str, lineNumber: int) -> int:
    if not low <= value <= high:
        raise AsmError(lineNumber, f"{what} must be {low} to {high}, not {value}")
    return value


def _parseInRange(text: str, low: int, high: int, what: str, lineNumber: int) -> int:
    return _checkRange(_parseNumber(text, lineNumber), low, high, what, lineNumber)


def _lookup(table: Mapping[str, int], name: str, what: str, lineNumber: int) -> int:
    code = table.get(name.lower())
    if code is None:
        raise AsmError(lineNumber, f"unknown {what} '{name}'")
    return code


def _expectOperands(statement: _Statement, count: int) -> list[str]:
    if len(statement.operands) != count:
        raise AsmError(
            statement.lineNumber,
            f"'{statement.mnemonic}' needs {count} operands, "
            f"not {len(statement.operands)}",
        )
    return statement.operands


def _encodeJmp(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    operands = statement.operands
    if len(operands) not in (1, 2):
        raise AsmError(statement.lineNumber, "'jmp' needs [condition] target")
    condition = operands[0] if len(operands) == 2 else ""
    conditionCode = _lookup(isa.jmpConditions, condition, "jmp condition", statement.lineNumber)
    targetText = operands[-1]
    target = labels.get(targetText)
    if target is None:
        target = _parseNumber(targetText, statement.lineNumber)
    offset = _checkRange(
        target - statement.address,
        isa.jmpOffsetMin,
        isa.jmpOffsetMax,
        f"jump offset to '{targetText}'",
        statement.lineNumber,
    )
    return isa.Opcode.jmp, (conditionCode << isa.fieldShift) | (offset & 0x3F)


def _encodeWait(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    operands = list(statement.operands)
    timeoutEn = len(operands) == 4 and operands[-1].lower() == "timeout"
    if timeoutEn:
        operands.pop()
    if len(operands) != 3:
        raise AsmError(statement.lineNumber, "'wait' needs polarity source index [timeout]")
    lineNumber = statement.lineNumber
    polarity = _parseInRange(operands[0], 0, 1, "polarity", lineNumber)
    source = _lookup(isa.waitSources, operands[1], "wait source", lineNumber)
    indexLimit = isa.flagCount if source == isa.waitSources["flag"] else isa.pinCount
    index = _parseInRange(operands[2], 0, indexLimit - 1, "index", lineNumber)
    return isa.Opcode.wait, (polarity << 8) | (source << 6) | (int(timeoutEn) << 5) | index


def _encodeShift(
    statement: _Statement, table: Mapping[str, int], what: str
) -> int:
    name, countText = _expectOperands(statement, 2)
    lineNumber = statement.lineNumber
    code = _lookup(table, name, what, lineNumber)
    count = _parseInRange(countText, 1, isa.maxBitCount, "bit count", lineNumber)
    return (code << isa.fieldShift) | (count % isa.maxBitCount)


def _encodeIn(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    return isa.Opcode.shiftIn, _encodeShift(statement, isa.inSources, "in source")


def _encodeOut(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    return isa.Opcode.shiftOut, _encodeShift(statement, isa.outDestinations, "out destination")


def _encodePushPull(statement: _Statement, isPull: bool) -> int:
    conditionWord = "ifempty" if isPull else "iffull"
    allowed = {conditionWord, "block", "noblock"}
    options = [operand.lower() for operand in statement.operands]
    for option in options:
        if option not in allowed:
            message = f"unknown '{statement.mnemonic}' option '{option}'"
            raise AsmError(statement.lineNumber, message)
    if "block" in options and "noblock" in options:
        raise AsmError(statement.lineNumber, "use 'block' or 'noblock', not both")
    isConditional = conditionWord in options
    isBlocking = "noblock" not in options
    return (int(isPull) << 8) | (int(isConditional) << 7) | (int(isBlocking) << 6)


def _encodePush(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    return isa.Opcode.pushPull, _encodePushPull(statement, isPull=False)


def _encodePull(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    return isa.Opcode.pushPull, _encodePushPull(statement, isPull=True)


def _movFields(destination: int, operation: isa.MovOperation, source: int) -> int:
    return (destination << isa.fieldShift) | (operation << 3) | source


def _encodeMov(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    destinationName, sourceText = _expectOperands(statement, 2)
    lineNumber = statement.lineNumber
    operation = isa.MovOperation.copy
    if sourceText.startswith("::"):
        operation, sourceText = isa.MovOperation.reverse, sourceText[2:]
    elif sourceText[:1] in ("~", "!"):
        operation, sourceText = isa.MovOperation.invert, sourceText[1:]
    destination = _lookup(isa.movDestinations, destinationName, "mov destination", lineNumber)
    source = _lookup(isa.movSources, sourceText, "mov source", lineNumber)
    return isa.Opcode.mov, _movFields(destination, operation, source)


def _aluEncoder(operation: isa.MovOperation) -> _Encoder:
    def encodeAlu(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
        destinationName, sourceName = _expectOperands(statement, 2)
        lineNumber = statement.lineNumber
        if destinationName.lower() not in isa.aluDestinations:
            raise AsmError(lineNumber, f"'{statement.mnemonic}' destination must be x, y, or t")
        destination = isa.movDestinations[destinationName.lower()]
        source = _lookup(isa.movSources, sourceName, "mov source", lineNumber)
        return isa.Opcode.mov, _movFields(destination, operation, source)

    return encodeAlu


def _encodeNop(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    _expectOperands(statement, 0)
    y = isa.movDestinations["y"]
    return isa.Opcode.mov, _movFields(y, isa.MovOperation.copy, isa.movSources["y"])


def _encodeSet(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    destinationName, valueText = _expectOperands(statement, 2)
    lineNumber = statement.lineNumber
    destination = _lookup(isa.setDestinations, destinationName, "set destination", lineNumber)
    value = _parseInRange(valueText, 0, isa.setDataMax, "set data", lineNumber)
    return isa.Opcode.set, (destination << isa.fieldShift) | value


def _encodeFlag(statement: _Statement, labels: Mapping[str, int]) -> tuple[isa.Opcode, int]:
    operationName, indexText = _expectOperands(statement, 2)
    lineNumber = statement.lineNumber
    operation = _lookup(isa.flagOperations, operationName, "flag operation", lineNumber)
    index = _parseInRange(indexText, 0, isa.flagCount - 1, "flag index", lineNumber)
    return isa.Opcode.flag, (operation << 7) | index


encoders: Mapping[str, _Encoder] = {
    "jmp": _encodeJmp,
    "wait": _encodeWait,
    "in": _encodeIn,
    "out": _encodeOut,
    "push": _encodePush,
    "pull": _encodePull,
    "mov": _encodeMov,
    "add": _aluEncoder(isa.MovOperation.add),
    "sub": _aluEncoder(isa.MovOperation.subtract),
    "and": _aluEncoder(isa.MovOperation.bitAnd),
    "or": _aluEncoder(isa.MovOperation.bitOr),
    "xor": _aluEncoder(isa.MovOperation.bitXor),
    "nop": _encodeNop,
    "set": _encodeSet,
    "flag": _encodeFlag,
}


def _parseSideSet(arguments: list[str], lineNumber: int) -> isa.SideSetConfig:
    if not arguments:
        raise AsmError(lineNumber, "'.side_set' needs a bit count")
    sideCount = _parseNumber(arguments[0], lineNumber)
    options = {argument.lower() for argument in arguments[1:]}
    unknown = options - {"opt", "pindirs"}
    if unknown:
        raise AsmError(lineNumber, f"unknown '.side_set' option '{sorted(unknown)[0]}'")
    try:
        return isa.SideSetConfig(sideCount, "opt" in options, "pindirs" in options)
    except ValueError as error:
        raise AsmError(lineNumber, str(error)) from None


def _timing(statement: _Statement, sideSet: isa.SideSetConfig) -> int:
    lineNumber = statement.lineNumber
    if statement.side is None and sideSet.sideCount > 0 and not sideSet.sideEn:
        raise AsmError(lineNumber, "side-set is not optional: add 'side n'")
    if statement.side is not None:
        if sideSet.sideCount == 0:
            raise AsmError(lineNumber, "'side' needs a '.side_set' directive")
        _checkRange(statement.side, 0, sideSet.maxSide, "side-set value", lineNumber)
    _checkRange(statement.delay, 0, sideSet.maxDelay, "delay", lineNumber)
    return sideSet.packTiming(statement.side, statement.delay)


def _splitTiming(text: str, lineNumber: int) -> tuple[str, int | None, int]:
    delay = 0
    delayMatch = delayPattern.search(text)
    if delayMatch:
        delay = _parseNumber(delayMatch.group(1), lineNumber)
        text = text[: delayMatch.start()]
    side = None
    sideMatch = sidePattern.search(text)
    if sideMatch:
        side = _parseNumber(sideMatch.group(1), lineNumber)
        text = text[: sideMatch.start()]
    return text, side, delay


class _Parser:
    def __init__(self) -> None:
        self.statements: list[_Statement] = []
        self.labels: dict[str, int] = {}
        self.sideSet = isa.SideSetConfig()
        self.wrapBottom: int | None = None
        self.wrapTop: int | None = None

    def parseLine(self, lineNumber: int, rawLine: str) -> None:
        text = commentPattern.sub("", rawLine).strip()
        labelMatch = labelPattern.match(text)
        if labelMatch:
            self._addLabel(labelMatch.group(1), lineNumber)
            text = text[labelMatch.end() :].strip()
        if not text:
            return
        if text.startswith("."):
            self._parseDirective(text, lineNumber)
            return
        self._parseInstruction(text, lineNumber)

    def _addLabel(self, name: str, lineNumber: int) -> None:
        if name in self.labels:
            raise AsmError(lineNumber, f"duplicate label '{name}'")
        self.labels[name] = len(self.statements)

    def _parseDirective(self, text: str, lineNumber: int) -> None:
        name, *arguments = text.split()
        directive = name.lower()
        if directive == ".side_set":
            if self.statements:
                raise AsmError(lineNumber, "'.side_set' must come before the first instruction")
            self.sideSet = _parseSideSet(arguments, lineNumber)
        elif directive == ".wrap_target":
            self.wrapBottom = len(self.statements)
        elif directive == ".wrap":
            if not self.statements:
                raise AsmError(lineNumber, "'.wrap' must come after an instruction")
            self.wrapTop = len(self.statements) - 1
        else:
            raise AsmError(lineNumber, f"unknown directive '{name}'")
        if arguments and directive != ".side_set":
            raise AsmError(lineNumber, f"'{name}' does not take arguments")

    def _parseInstruction(self, text: str, lineNumber: int) -> None:
        body, side, delay = _splitTiming(text, lineNumber)
        mnemonic, *operands = body.replace(",", " ").split()
        self.statements.append(
            _Statement(lineNumber, len(self.statements), mnemonic.lower(), operands, side, delay)
        )

    def finish(self) -> Program:
        count = len(self.statements)
        if count == 0:
            raise AsmError(0, "the program has no instructions")
        if count > isa.programWords:
            raise AsmError(
                self.statements[isa.programWords].lineNumber,
                f"the program has {count} instructions, the limit is {isa.programWords}",
            )
        wrapBottom = 0 if self.wrapBottom is None else self.wrapBottom
        if wrapBottom >= count:
            raise AsmError(0, "'.wrap_target' must come before an instruction")
        words = tuple(self._encodeStatement(statement) for statement in self.statements)
        wrapTop = count - 1 if self.wrapTop is None else self.wrapTop
        return Program(words, dict(self.labels), self.sideSet, wrapBottom, wrapTop)

    def _encodeStatement(self, statement: _Statement) -> int:
        encoder = encoders.get(statement.mnemonic)
        if encoder is None:
            raise AsmError(statement.lineNumber, f"unknown instruction '{statement.mnemonic}'")
        opcode, operands = encoder(statement, self.labels)
        return isa.encode(opcode, _timing(statement, self.sideSet), operands)


def assemble(source: str) -> Program:
    parser = _Parser()
    for lineNumber, rawLine in enumerate(source.splitlines(), start=1):
        parser.parseLine(lineNumber, rawLine)
    return parser.finish()


def toHex(program: Program) -> str:
    return "".join(f"{word:04x}\n" for word in program.words)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
    argumentParser = argparse.ArgumentParser(description="Assemble a program to a hex file.")
    argumentParser.add_argument("source", type=Path)
    argumentParser.add_argument("-o", "--output", type=Path, required=True)
    arguments = argumentParser.parse_args(argv)
    try:
        program = assemble(arguments.source.read_text())
    except AsmError as error:
        logger.error("%s: %s", arguments.source, error)
        return 1
    arguments.output.write_text(toHex(program))
    logger.info("%s: %d words", arguments.output, len(program.words))
    return 0


if __name__ == "__main__":
    sys.exit(main())
