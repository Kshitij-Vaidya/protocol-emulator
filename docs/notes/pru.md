# TI PRU: Reading Notes

Status: outline. Complete it during week 1 (M0).

## Sources

1. TI SPRUIJ2, [*PRU Assembly Instruction User Guide*](https://www.ti.com/lit/ug/spruij2/spruij2.pdf)
   (April 2018). It describes the instruction set.
2. TI SPRUH73, *AM335x Technical Reference Manual*, the PRU-ICSS chapter. It describes the
   subsystem: memories, pins, interrupts, and the connection to the ARM CPU.
3. [*PRU Cookbook*](https://docs.beagleboard.org/books/pru-cookbook/) (BeagleBoard). It has
   examples with real protocols and timing measurements.

## Facts to confirm

These facts are from memory, and they apply to the AM335x. Other TI devices have different PRU
versions. Confirm each fact, and add the source and section.

| Fact | Confirmed | Source and section |
|---|---|---|
| The AM335x PRU-ICSS has 2 PRU cores. Each core is a 32-bit RISC processor at 200 MHz. | | |
| Most instructions execute in 1 cycle (5 ns). | | |
| Each core has 8 KB of instruction RAM (2048 instructions of 32 bits) and 8 KB of data RAM. The 2 cores share 12 KB of RAM. | | |
| The core has 32 registers, R0–R31. A write to R30 sets the output pins. A read of R31 gets the input pins and the event flags. | Partly: SPRUIJ2 describes the R31 event flags. | SPRUIJ2 (`SET` instruction note) |
| The core has no cache and no branch prediction, so the timing of local operations is deterministic. | | |
| An access to memory outside the PRU subsystem has a variable latency. | | |
| The `LOOP` instruction makes a hardware loop with no cycle cost for each iteration. | | |
| The input pins have modes: direct, 16-bit parallel capture, and 28-bit shift. | | |
| The broadside (`XIN`, `XOUT`) instructions move many registers to or from the scratchpad or the other core in 1 cycle. | | |

## Questions to answer

Each question connects to a decision in `docs/PLAN.md`. Write the answer, and add the source and
section.

### Timing model (ADR: timing model)
1. How does a PRU program get exact timing without a delay field like PIO? (Count the cycles of
   each instruction.)
2. Which instructions do not take 1 cycle? How does the programmer know their duration?
3. What causes timing jitter on a PRU? How do PRU programs prevent it?

### Program memory (ADR: program memory)
1. PRU has 2048 instructions. PIO has 32. What does the PRU program do with the additional
   instructions?
2. How long are the PRU UART, SPI, and I2C examples in the PRU Cookbook?
3. A general-purpose core needs more instructions than a PIO state machine for the same protocol.
   Find an example, and count the instructions for both.

### Number of cores (ADR: number of cores)
1. Why does the PRU-ICSS have 2 cores?
2. How do the 2 cores communicate (shared RAM, scratchpad, events)?

### Host interface (ADR: host interface)
1. How does the ARM CPU load a PRU program and start the core?
2. How does the PRU send data to the ARM CPU, and how does the ARM CPU send data to the PRU?
3. Which of these methods can operate on the Tiny Tapeout pins, with no on-chip CPU?

### Pins
1. How does a PRU program set 1 output pin without a change to the other pins?
2. How does the parallel-capture input mode operate? Which protocols use it?
3. How does the shift mode operate? Is it like a PIO shift register?

## PRU compared with PIO

Complete this table after the notes in `pio.md` and in this file are complete.

| Property | PIO | PRU | Better for a 6x4 tile budget |
|---|---|---|---|
| Instruction width | | | |
| Instructions in memory | | | |
| Registers | | | |
| Cycle timing | | | |
| Delay mechanism | | | |
| Pin access | | | |
| Host data path | | | |
| Approximate area | | | |

## Summary for the architecture

Write 5–10 lines after the questions are answered. State what to copy from PRU, what to change,
and why.
