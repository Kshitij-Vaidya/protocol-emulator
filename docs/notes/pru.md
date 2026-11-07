# TI PRU: Reading Notes

Status: complete (2026-11-07). "TRM" means TI SPRUH73Q, chapter 4 (PRU-ICSS). "SPRUIJ2" means
the PRU Assembly Instruction User Guide. "Cookbook" means the BeagleBoard PRU Cookbook.

## Sources

1. TI SPRUIJ2, [*PRU Assembly Instruction User Guide*](https://www.ti.com/lit/ug/spruij2/spruij2.pdf)
   (April 2018). It describes the instruction set.
2. TI SPRUH73Q, [*AM335x Technical Reference Manual*](https://www.ti.com/lit/ug/spruh73q/spruh73q.pdf)
   (revised December 2019), chapter 4 (PRU-ICSS). It describes the subsystem: memories, pins,
   interrupts, and the connection to the ARM CPU.
3. [*PRU Cookbook*](https://docs.beagleboard.org/books/pru-cookbook/) (BeagleBoard), chapters 5, 6,
   and 7. It has examples and timing measurements.
4. TI Processor SDK Linux, the
   [RemoteProc and RPMsg](https://software-dl.ti.com/processor-sdk-linux/esd/docs/latest/linux/Foundational_Components/PRU-ICSS/Linux_Drivers/RemoteProc_and_RPMsg.html)
   page. It describes how Linux loads and starts a PRU.

## Facts to confirm

| Fact | Confirmed | Source and section |
|---|---|---|
| The AM335x PRU-ICSS has 2 PRU cores. Each core is a 32-bit RISC processor at 200 MHz. | Partly. 2 cores of 32-bit RISC: yes. The TRM PRU chapter does not state 200 MHz. The cookbook says "Each cycle is 5ns". | TRM 4.1; Cookbook ch. 5 |
| Most instructions execute in 1 cycle (5 ns). | Partly. No source states "most instructions". The cookbook measured 1 cycle for a write to R30. The TRM says "Pipelining: None (Purposefully)". | TRM 4.4.1; Cookbook ch. 5 |
| Each core has 8 KB of instruction RAM (2048 instructions of 32 bits) and 8 KB of data RAM. The 2 cores share 12 KB of RAM. | Yes. The instruction width is 32 bits. | TRM 4.1.1, 4.4.1 |
| The core has 32 registers, R0–R31. A write to R30 sets the output pins. A read of R31 gets the input pins and the event flags. | Yes. R1–R30 are general purpose, R0 is also an index register, and R31 is status. R31 bits 30–31 are the 2 host interrupts. A write to R31 makes a system event. | TRM 4.4.1, 4.4.1.2 |
| The core has no cache and no branch prediction, so the timing of local operations is deterministic. | Partly. The TRM says "a small, deterministic instruction set" and "Pipelining: None". It does not mention a cache. | TRM 4.1, 4.4.1 |
| An access to memory outside the PRU subsystem has a variable latency. | Partly. The cookbook shows that a GPIO access through the system bus takes 80 ns, not 15 ns, because the bus "is shared with other parts of the system". | Cookbook ch. 6 |
| The `LOOP` instruction makes a hardware loop with no cycle cost for each iteration. | Partly. `LOOP` is "hardware-assisted" and "non-interruptible". The count comes from the 16 LSBs of a register. The guide does not state the cycle cost. Only core revision 3 has `LOOP`. | SPRUIJ2 2.3 (`LOOP`), Appendix A |
| The input pins have modes: direct, 16-bit parallel capture, and 28-bit shift. | Yes, and a fourth mode, MII_RT. A core can use only 1 mode at a time. | TRM 4.4.1.2.3, Table 4-12 |
| The broadside (`XIN`, `XOUT`) instructions move many registers to or from the scratchpad or the other core in 1 cycle. | Yes: "XFR instructions operate in one clock cycle". There are 3 scratchpad banks of 30 registers. With a direct connection, a core can stall for up to 1024 cycles until the other core executes the matching instruction. | TRM 4.4.1.4.1, Table 4-21 |

## Questions to answer

### Timing model (ADR: timing model)

1. **Exact timing without a delay field.** The programmer counts the cycles of each instruction.
   The core has no pipeline (TRM 4.4.1). The programmer measures the code with the `CYCLE` and
   `STALL` counters in the PRU control registers (Cookbook ch. 7).
2. **Instructions that are not 1 cycle.** The sources that we read do not have a cycle table.
   Loads and stores (`LBBO`, `SBBO`, `LBCO`, `SBCO`) go through a memory interface. The cookbook
   measured 2 cycles to read the `CYCLE` register. `WBS`, `WBC`, and `SLP` wait for an event, so
   their duration is not fixed (SPRUIJ2 2.3).
3. **Jitter.** An access through the system bus (OCP) waits for other bus masters (Cookbook ch. 6).
   The C compiler can also make code with a different timing than the programmer expects
   (Cookbook ch. 7). To prevent jitter, use R30 and R31 for the pins, use assembly for the
   time-critical loops, and unroll loops (Cookbook ch. 5, 6, and 7).

### Program memory (ADR: program memory)

1. **Use of 2048 instructions.** The PRU runs C programs, packet handling for industrial Ethernet
   (MII_RT), and memory-mapped data structures (TRM 4.1, 4.4.1). These tasks need more
   instructions than a pin protocol.
2. **Size of the cookbook examples.** The chapters that we read have no UART, SPI, or I2C example.
   The assembly delay loop is 3 instructions (`sub`, `qbne`, `jmp`, Cookbook ch. 7).
3. **PRU compared with PIO for 1 protocol.** Not answered: we found no PRU UART example. Write one
   UART TX program for our ISS in week 3, and count its instructions against the PIO `uart_tx`
   (4 instructions).

### Number of cores (ADR: number of cores)

1. **Why 2 cores.** The TRM does not give the reason. It says that "each PRU can operate
   independently or in coordination with each other" (TRM 4.1).
2. **Communication between the 2 cores.** The cores communicate in 4 ways:
   - the 12 KB shared RAM,
   - the scratchpad, with `XIN` and `XOUT` in 1 cycle (TRM 4.4.1.4),
   - a direct register transfer from 1 core to the other (device ID 14),
   - system events: a write to R31 makes events 16–31 in the interrupt controller, and the other
     core reads them in R31 bits 30–31 (TRM 4.4.1.2.2).

### Host interface (ADR: host interface)

1. **Program load and start.** The host can write the instruction RAM only while the core is
   halted. `CTRL.RUNSTATE` = 0 means "PRU is halted and host has access to the instruction RAM".
   `CTRL.PCTR_RST_VAL` sets the start address (TRM 4.5, Table 4-41). Linux uses remoteproc: the
   driver writes the firmware into the instruction RAM, and then sets the state to "Run" (TI SDK).
2. **Data between the PRU and the ARM.** The data goes through the shared RAM and the data RAM. The
   ARM writes these memories while the PRU runs (Cookbook ch. 5). The interrupt controller sends
   events in both directions. Linux rpmsg uses vrings in DDR and mailboxes (TI SDK).
3. **Methods that can operate on the Tiny Tapeout pins.** A small pin interface can do these 4
   operations:
   - halt and start the core,
   - write the program memory while the core is halted,
   - read and write a small shared data memory,
   - send events in both directions.

### Pins

1. **Set 1 output pin.** Use `SET` or `CLR` on 1 bit of R30 (SPRUIJ2 2.1). In C, write
   `__R30 |= gpio` (Cookbook ch. 5). R31 cannot be the source of `SET`. The result is NULL, not the
   input flags (SPRUIJ2 2.1).
2. **Parallel capture.** `DATAIN[0:15]` is captured on the rising or falling edge of `CLOCKIN`
   (pin 16). The `CFG_GPCFGn` register selects the edge (TRM Table 4-12). This mode is for
   parallel buses with a clock.
3. **Shift modes.** In 28-bit shift-in mode, the hardware samples `DATAIN` and shifts it into a
   28-bit register. It has a shift counter (`Cnt_16`) and start-bit detection (TRM Table 4-12). In
   shift-out mode, R30 bit 0 shifts out on a free-running clock from 2 16-bit shadow registers
   (TRM 4.4.1.2.4.2). These are fixed-function shifters. PIO shift registers are more flexible:
   they shift any count from 1 to 32, in each direction, under program control.

## PRU compared with PIO

| Property | PIO | PRU | Better for an 8x4 tile budget |
|---|---|---|---|
| Instruction width | 16 bits | 32 bits | PIO |
| Instructions in memory | 32, shared by 4 state machines | 2048 for each core | PIO for area. The SRAM macro makes a large memory possible. |
| Registers | X, Y, OSR, ISR (32 bits) | 32 × 32 bits, with bit, byte, and halfword access | PIO for area |
| Cycle timing | 1 cycle; stalls only on explicit conditions | No pipeline; most local instructions are 1 cycle | Both |
| Delay mechanism | 5-bit delay field in each instruction | Count instructions; `LOOP`; `WBS` and `WBC` | PIO |
| Pin access | `OUT`, `SET`, `IN`, and side-set ranges; direction control | R30 and R31 bits; capture and shift modes | PIO (side-set) |
| Host data path | FIFOs and DMA | Shared RAM, interrupt events, rpmsg | PIO for area |
| Approximate area | 1 state machine is approximately 1 SPI or I2C block (PIO 3.1) | Not stated; 16 KB of RAM for each core | PIO |

## Summary for the architecture

1. Copy the PRU arithmetic: `ADD`, `SUB`, the logic operations, and the compare-and-branch
   instructions (`QBxx`, `QBBS`, `QBBC`).
2. Copy `WBS` and `WBC` (wait until bit set or clear). They are equal to the PIO `WAIT` on a pin.
3. Copy the program load rule: the host writes the program memory only while the core is halted.
   This rule prevents a conflict between a host write and an instruction fetch.
4. Copy the start address register (`PCTR_RST_VAL`).
5. Do not copy 32 × 32-bit registers or the 32-bit instructions. They use too much area.
6. Do not copy the timing model "count every instruction". The PIO delay field is easier for the
   programmer and for the ISS.
7. Our design can combine the 2: PIO timing, side-set, and size, with some PRU arithmetic and the
   PRU wait instructions. This combination is a possible "unique functionality".
