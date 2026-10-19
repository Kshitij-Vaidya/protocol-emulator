# RP2040 PIO: Reading Notes

Status: outline. Complete it during week 1 (M0).

## Sources

1. [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf), chapter 3
   (PIO). Read the overview, the programmer's model, the instruction set, the functional details,
   and the examples. Read the register list only when a question needs it.
2. [Raspberry Pi Pico C/C++ SDK](https://datasheets.raspberrypi.com/pico/raspberry-pi-pico-c-sdk.pdf),
   the PIO chapter. It explains the examples with `pioasm` source code.
3. RP2350 datasheet, the PIO chapter. The RP2350 has a newer PIO version. Compare the changes, and
   find out which problems they solve.

## Facts to confirm

These facts are from memory. Confirm each fact in the datasheet, and add the section number.

| Fact | Confirmed | Section |
|---|---|---|
| The RP2040 has 2 PIO blocks. Each block has 4 state machines. | | |
| The 4 state machines of a block share 1 instruction memory of 32 instructions. | | |
| Each instruction is 16 bits. | | |
| There are 9 instructions: `JMP`, `WAIT`, `IN`, `OUT`, `PUSH`, `PULL`, `MOV`, `IRQ`, `SET`. | | |
| Each instruction executes in 1 cycle. A delay field adds 0–31 cycles after the instruction. | | |
| The delay field and the side-set field share 5 bits of each instruction. | | |
| Each state machine has a fractional clock divider (16 integer bits, 8 fraction bits). | | |
| Each state machine has a TX FIFO and an RX FIFO of 4 × 32-bit words. They can join into 1 FIFO of 8 words. | | |
| Each state machine has a 32-bit output shift register (OSR) and input shift register (ISR), with autopull and autopush. | | |
| Each state machine has 2 scratch registers, X and Y. `JMP X--` makes a counted loop. | | |
| `.wrap_target` and `.wrap` make a loop with no cycle cost. | | |
| Each block has 8 IRQ flags, which the state machines use to synchronize. | | |

## Questions to answer

Each question connects to a decision in `docs/PLAN.md`. Write the answer, and add the section
number of the source.

### Timing model (ADR: timing model)
1. How does PIO make sure that each instruction takes an exact number of cycles?
2. What does the delay field cost in instruction bits, and what does it save in instruction count?
3. What does side-set do? Why does it make bit-banging shorter?
4. How does the fractional clock divider make jitter? When is the jitter not acceptable?

### Program memory (ADR: program memory)
1. Why does PIO have only 32 instructions? Use `competition.md`: 32 × 16 bit in flip-flops is
   approximately 5% of the area budget.
2. How many instructions do the UART TX, UART RX, SPI, and I2C examples use?
3. How does the host load a program? Can it change a program while a state machine runs?

### Number of cores (ADR: number of cores)
1. Why does PIO use 4 small state machines and not 1 larger core?
2. What do the state machines share, and what does each state machine have separately?
3. How do 2 state machines cooperate on 1 protocol (for example, I2C or duplex SPI)?

### Host interface (ADR: host interface)
1. How do the FIFOs connect the state machines to the CPU?
2. What occurs when the TX FIFO is empty or the RX FIFO is full? Does the state machine stop?
3. Our chip has no on-chip CPU. Which PIO host features need a replacement on the Tiny Tapeout
   pins (8 inputs, 8 outputs, 8 bidirectional)?

### Pins
1. How do the `OUT`, `SET`, `IN`, and side-set pin mappings operate?
2. How does PIO make an open-drain output for I2C? (Hint: the pin direction.)
3. What does `WAIT` wait for? How many cycles after the pin change does the state machine continue?

## Limits of PIO

List the protocols or features that PIO cannot do, or does with difficulty. For each one, write
the reason. These limits are where our design can be different, and different designs score
higher with the judges ("unique functionality").

| Limit | Reason | Possible solution in our design |
|---|---|---|
| | | |

## Summary for the architecture

Write 5–10 lines after the questions are answered. State what to copy from PIO, what to change,
and why.
