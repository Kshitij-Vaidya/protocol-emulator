# ADR-0004: Timing model

Status: **Accepted** (2026-11-07)

## Context
The purpose of the chip is exact pin timing. PIO executes 1 instruction on each cycle, adds a
5-bit delay field, and stalls only on explicit conditions (refer to `docs/notes/pio.md`). A PRU
programmer counts the cycles of each instruction (refer to `docs/notes/pru.md`).

`docs/notes/protocols.md` gives these requirements:
- The timing resolution must be 1 cycle (20 ns at 50 MHz).
- The longest bit time is 5208 cycles (UART at 9600 baud).
- A fractional clock divider adds 1 cycle of jitter (PIO).

## Options
1. PIO model: 1 instruction on each cycle, a delay field, and a fractional clock divider.
2. PRU model: count the cycles of each instruction, with no delay field.
3. PIO model with an integer clock divider, and a `WAIT` with a timeout.

## Decision
Use option 3.

1. Each instruction executes in exactly 1 cycle of the core clock enable.
2. Only these instructions can stall: `WAIT` on a pin or a flag, and a blocking FIFO operation.
   The ISA must list each stall condition.
3. Each instruction has a delay field. The delay cycles start after a stall ends, as in PIO.
4. Each core has a 16-bit integer clock divider. It makes a clock enable, not a new clock. A
   divider of 1 runs on each cycle.
5. `WAIT` has a timeout in cycles, and a branch target when the timeout occurs.

## Consequences
- The ISS can calculate the exact cycle of each pin change. The lockstep test can compare the RTL
  and the ISS on each cycle.
- The delay field uses bits in a 16-bit instruction (ADR-0002). `docs/isa.md` must balance the
  delay field, the side-set field, and the operand fields.
- An integer divider has no jitter. Firmware gets fine timing from the delay field.
- A `WAIT` with a timeout needs a counter and a second target. The ISA must fit this in 16 bits,
  for example with a timeout value in a register.
