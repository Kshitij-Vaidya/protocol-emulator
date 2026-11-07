# ADR-0003: Number of cores

Status: **Accepted** (2026-11-07)

## Context
PIO uses 4 state machines that share a 4-read register file (refer to `docs/notes/pio.md`). A
protocol often needs 2 parallel tasks, for example UART TX and UART RX. PRU uses 2 large cores
(refer to `docs/notes/pru.md`).

The program memory is a 1-port SRAM macro (ADR-0002). 1 macro gives 1 instruction fetch on each
cycle. The 8x4 die is 1724.16 µm wide, and 1 macro is 236.8 µm wide. The Tiny Tapeout SRAM
example supports more than 1 macro instance.

## Options
1. 1 core with 1 macro.
2. N cores that share 1 macro. Each core runs at the clock divided by N.
3. N cores, each with its own macro.
4. 1 core with fixed-function helper units (for example a UART shifter).

## Decision
1. Use option 1 for M2. Write the RTL so that the core is 1 module with its own `progMem`
   instance.
2. Plan option 3 for M5. Select N (2 to 4) in week 5, from the area of 1 core in the first
   real harden. 4 macros use 112,508 µm² (12% of 0.93 mm²).
3. Do not use option 2. It divides the speed of each core, and this conflicts with the cycle
   timing in `docs/notes/protocols.md`.

## Consequences
- The cores need a synchronization method, as the PIO IRQ flags. Define it in `docs/isa.md`.
- The cores need a method to share data. PIO has none, and this is a PIO limit. A small shared
  register is a possible "unique functionality".
- The host interface (ADR-0005) must address each core and each program memory.
- Each additional macro needs its own entry in `MACROS` and `PDN_MACRO_CONNECTIONS`. Macros side
  by side get their own power stripes. Stacked macros must have the same x.
