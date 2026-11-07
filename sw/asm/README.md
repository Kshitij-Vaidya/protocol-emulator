# Assembler

The assembler changes a program source (`.pasm`) into a hex file. The hex file has 1 word of
4 hex digits on each line. `$readmemh` and the ISS can read this file. The encoding is in
`docs/isa.md`.

## Use

Run the assembler from the `sw` directory:

```sh
python -m asm.assembler asm/examples/uartTx.pasm -o uartTx.hex
```

Run the tests from the repository root:

```sh
pytest
```

## Syntax

The syntax is the same as `pioasm`, with the differences in this section.

- A comment starts with `;` or `//`.
- A label is a name and a colon (`bitLoop:`). An instruction can follow the label on the same line.
- Keywords are not case sensitive. Labels are case sensitive.
- A number can be decimal, hex (`0x1f`), or binary (`0b101`).
- `side n` and `[n]` come after the operands, in this order.

### Directives

| Directive | Function |
|---|---|
| `.side_set n [opt] [pindirs]` | Sets `sideCount` to n (0–3). `opt` sets `sideEn`. `pindirs` sets `sidePinDir`. It must come before the first instruction. |
| `.wrap_target` | Sets `wrapBottom` to the address of the next instruction |
| `.wrap` | Sets `wrapTop` to the address of the previous instruction |

If a program has no `.wrap_target`, `wrapBottom` is 0. If a program has no `.wrap`, `wrapTop`
is the last address.

### Instructions

| Syntax | Notes |
|---|---|
| `jmp [condition] target` | Conditions: `!x`, `x--`, `y--`, `x!=y`, `pin`, `!osre`, `timeout`. The target is a label or an absolute address. The assembler calculates the offset (−32 to +31). |
| `wait polarity source index [timeout]` | Sources: `gpio` (absolute pin), `pin` (`inBase` + index), `flag` |
| `in source, count` | Sources: `pins`, `x`, `y`, `null`, `isr`, `osr`. Count: 1–16. |
| `out destination, count` | Destinations: `pins`, `x`, `y`, `null`, `pindirs`, `pc`, `isr`, `exec`. Count: 1–16. |
| `push [iffull] [block \| noblock]` | The default is `block` |
| `pull [ifempty] [block \| noblock]` | The default is `block` |
| `mov destination, [~ \| ! \| ::]source` | `~` and `!` invert. `::` reverses the bits. |
| `set destination, value` | Destinations: `pins`, `x`, `y`, `t`, `pindirs`. Value: 0–63. |
| `flag set \| clear \| wait index` | `wait` sets the flag, then stalls until it is clear |

### Pseudo-instructions

| Syntax | Instruction |
|---|---|
| `nop` | `mov y, y` |
| `add destination, source` | `mov` with the add operation |
| `sub destination, source` | `mov` with the subtract operation |
| `and destination, source` | `mov` with the and operation |
| `or destination, source` | `mov` with the or operation |
| `xor destination, source` | `mov` with the xor operation |

The destination of `add`, `sub`, `and`, `or`, and `xor` must be `x`, `y`, or `t`.
