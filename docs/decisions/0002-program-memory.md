# ADR-0002: Program memory

Status: **Accepted** (2026-11-07)

## Context
The program memory is the largest block (refer to `docs/notes/competition.md`). PIO has 32
instructions for 4 state machines, and the PIO I2C program uses 18 of them (refer to
`docs/notes/pio.md`). The budget is 8x4 tiles (0.93 mm² nominal).

Tiny Tapeout accepts the IHP SRAM macro for the March 2027 shuttle. The SRAM macro test (run
42352888754) passes all CI checks with `RM_IHPSG13_1P_256x16_c2_bm_bist`. No CMOS5L chip with an
SRAM macro is fabricated yet.

## Options
| Option | Words × bits | Area (µm²) | Part of 0.93 mm² |
|---|---|---|---|
| 1. Flip-flops | 32 × 16 | 34,080 | 4% |
| 2. Flip-flops | 64 × 16 | 68,451 | 7% |
| 3. SRAM macro, 1 port | 256 × 16 | 28,127 | 3% |
| 4. SRAM macro, 2 ports | 256 × 16 | 57,520 | 6% |
| 5. Latches | 256 × 16 | 200,332 | 21% |

## Decision
Use option 3: `RM_IHPSG13_1P_256x16_c2_bm_bist`, with 16-bit instructions.

1. The `progMem` module is the only interface to the memory: `addr`, `writeData`, `writeEn`,
   `readData`, with a read latency of 1 cycle. The macro test already uses this interface.
2. Keep option 1 or option 2 as the fallback behind the same interface. The fallback must pass
   the same tests.
3. Do not use option 4. It is 2 times larger, and no CMOS5L design uses it.

## Consequences
- An instruction is 16 bits. ADR-0004 and `docs/isa.md` must fit the encoding in 16 bits.
- The read latency is 1 cycle. To execute 1 instruction on each cycle, the core must give the
  address of the next instruction 1 cycle early. Thus, the next PC is an input to the SRAM, and
  the branch decision is on the path to the SRAM address. Check this path in STA in M2.
- 1 port gives 1 read on each cycle. Thus, 1 macro can supply only 1 core at full speed (refer
  to ADR-0003).
- If the macro fails in silicon, the chip has no program memory. The fallback is a different
  chip design, not a configuration bit. Decide in week 5 if a small flip-flop memory must also
  be on the chip as a backup.
