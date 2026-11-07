# ADR-0006: Program-load path

Status: **Accepted** (2026-11-07)

## Context
The program memory is an SRAM macro with 1 port (ADR-0002). The core fetches 1 instruction on
each cycle from this port. A host write and a fetch cannot use the port on the same cycle. The
PRU lets the host write the instruction RAM only while the core is halted (refer to
`docs/notes/pru.md`). PIO lets the host write 1 instruction that executes immediately
(`SMx_INSTR`, refer to `docs/notes/pio.md`).

## Options
1. The host writes the program memory through the host interface (ADR-0005), only while the core
   is halted.
2. The host writes the program memory while the core runs. The write stalls the core for 1 cycle.
3. The chip loads the program from an external SPI flash after reset.

## Decision
Use option 1, and add 2 debug operations.

1. A write to the program memory is accepted only when the core is halted. The status register
   shows if a write was rejected.
2. The host sets the start address of the core, as `PCTR_RST_VAL` on the PRU.
3. The host can execute 1 instruction while the core is halted, as `SMx_INSTR` on PIO.
4. The host can read the program memory while the core is halted, to check the load.

## Consequences
- The fetch and the host write never conflict, so the timing stays deterministic.
- The program cannot change itself, and the host cannot change a program while it runs. A
  firmware change needs a halt.
- The read-back operation gives a test of the SRAM after fabrication.
- Option 3 is not needed for the demo, because the demo board MCU loads the program. It stays a
  possible M5 feature.
