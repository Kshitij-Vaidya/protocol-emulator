# RP2040 PIO: Reading Notes

Status: complete (2026-11-07). The sections refer to the RP2040 datasheet, chapter 3, unless the
text names a different source.

## Sources

1. [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf), chapter 3
   (PIO). Read the overview, the programmer's model, the instruction set, the functional details,
   and the examples. Read the register list only when a question needs it.
2. [Raspberry Pi Pico C/C++ SDK](https://datasheets.raspberrypi.com/pico/raspberry-pi-pico-c-sdk.pdf),
   the PIO chapter. It explains the examples with `pioasm` source code. Not read yet.
3. [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf), chapter 11
   (PIO). Section 11.1.1 lists the changes from RP2040.

## Facts to confirm

| Fact | Confirmed | Section |
|---|---|---|
| The RP2040 has 2 PIO blocks. Each block has 4 state machines. | Yes | 3.1 |
| The 4 state machines of a block share 1 instruction memory of 32 instructions. | Yes. The memory is "a 1-write 4-read register file", so all 4 state machines read on the same cycle. | 3.2.2, 3.2.7 |
| Each instruction is 16 bits. | Yes | 3.4.1 |
| There are 9 instructions: `JMP`, `WAIT`, `IN`, `OUT`, `PUSH`, `PULL`, `MOV`, `IRQ`, `SET`. | Yes | 3.2.1 |
| Each instruction executes in 1 cycle. A delay field adds 0–31 cycles after the instruction. | Yes. Delay cycles start only after a stall clears. | 3.2.2, 3.2.4 |
| The delay field and the side-set field share 5 bits of each instruction. | Yes. `SIDESET_COUNT` MSBs are side-set, and the remaining LSBs are delay. | 3.4.1 |
| Each state machine has a fractional clock divider (16 integer bits, 8 fraction bits). | Yes. It uses first-order delta-sigma for the fraction. | 3.5.5 |
| Each state machine has a TX FIFO and an RX FIFO of 4 × 32-bit words. They can join into 1 FIFO of 8 words. | Yes (`SHIFTCTRL_FJOIN`) | 3.2.3.5 |
| Each state machine has a 32-bit OSR and ISR, with autopull and autopush. | Yes | 3.2.3.1, 3.2.3.2, 3.5.4 |
| Each state machine has 2 scratch registers, X and Y. `JMP X--` makes a counted loop. | Yes. The branch uses the value before the decrement. | 3.2.3.4, 3.4.2 |
| `.wrap_target` and `.wrap` make a loop with no cycle cost. | Yes. The datasheet calls it "a free (0-cycle) unconditional jump". | 3.5.2 |
| Each block has 8 IRQ flags, which the state machines use to synchronize. | Yes. Only the lower 4 go to the system interrupts on RP2040. | 3.2.6 |

## Questions to answer

### Timing model (ADR: timing model)

1. **Exact cycles.** Each state machine fetches, decodes, and executes 1 instruction on each cycle.
   An instruction takes 1 cycle, unless it stalls (3.2.2). These 5 conditions cause a stall
   (3.2.4):
   - a `WAIT` condition that is not met,
   - a blocking `PULL` on an empty TX FIFO,
   - a blocking `PUSH` on a full RX FIFO,
   - `IRQ WAIT` until the flag clears,
   - autopull or autopush at the threshold, when the FIFO cannot supply or accept data.

   During a stall, the PC does not change, and the delay cycles do not start (3.2.4).
2. **Cost of the delay field.** The delay and side-set field uses 5 of the 16 bits. Without it, a
   wait of N cycles needs N `nop` instructions or a loop. Example: `uart_tx` is 4 instructions. Its
   `[7]` and `[6]` delays make each bit exactly 8 cycles (3.6.3).
3. **Side-set.** Side-set changes up to 5 pins at the same time as the main instruction (3.5.1).
   An SPI clock edge and a data bit change in 1 instruction. Thus, `spi_tx_fast` is 2 instructions
   and sends 1 bit each 2 cycles. Side-set happens on the first cycle of the instruction, also when
   the instruction stalls. An optional enable bit (`.side_set n opt`) uses 1 more bit of the field.
   Side-set can drive the pin directions instead of the levels (`EXECCTRL_SIDE_PINDIR`).
4. **Jitter.** The divider is a clock enable, not a new clock (3.5.5). With a fraction, some
   periods are n cycles and some are n + 1 cycles. Thus, an edge can move by 1 system clock. The
   datasheet says: "For small n, the jitter introduced by a fractional divider may be
   unacceptable." It recommends even divisions for fast asynchronous serial.

### Program memory (ADR: program memory)

1. **Why 32 instructions.** The datasheet does not give the reason. It states that each state
   machine "occupies approximately the same silicon area as a standard serial interface block"
   (3.1). The memory is a register file with 4 read ports (3.2.7). Each read port needs a full read
   multiplexer, so a larger memory costs area 4 times. This is our conclusion, not a datasheet
   statement.
2. **Size of the examples** (instructions, counted from the listings in 3.6):

   | Program | Instructions | Section |
   |---|---|---|
   | `spi_cpha0` (duplex SPI, CPHA 0) | 2 | 3.6.1 |
   | `spi_cpha1` (duplex SPI, CPHA 1) | 3 | 3.6.1 |
   | `ws2812` | 4 | 3.6.2 |
   | `uart_tx` (8N1) | 4 | 3.6.3 |
   | `uart_rx_mini` (8N1, no error check) | 4 | 3.6.4 |
   | `uart_rx` (with framing-error check) | 9 | 3.6.4 |
   | `i2c` (master, clock stretch, NAK check) | 18 | 3.6.7 |

   The I2C program uses 18 of 32 instructions. It also needs the CPU to send `START`, `STOP`, and
   `RESTART` as instructions in the TX FIFO (`OUT EXEC`).
3. **Program load.** The system has write-only access to the instruction memory (3.2.2). The CPU
   can also write 1 instruction to `SMx_INSTR`, which executes immediately (3.2.2, 3.5.7). The
   datasheet does not say if a write to the memory while the state machines run is safe.

### Number of cores (ADR: number of cores)

1. **4 small state machines.** One interface often needs 2 parallel tasks, for example TX and RX
   of a UART, or the timing and the pixel data of DPI (3.1, 3.2.7). The 4-read memory lets 4
   state machines run at full speed with no stall (3.2.7).
2. **Shared and separate resources.**
   - Shared in 1 block: the instruction memory, the 8 IRQ flags, and the pin output registers.
     For each pin, the highest-numbered state machine wins (3.5.6.1).
   - Separate for each state machine: the PC, X, Y, OSR, ISR, the shift counters, the FIFOs, the
     clock divider, and the pin mapping (3.1, 3.2.3).
3. **Cooperation.** State machines cannot send data to each other. They synchronize only with the
   IRQ flags, through `IRQ` and `WAIT IRQ` (3.2.7). The `rel` option adds the state machine number
   to the flag index, so copies of 1 program can use different flags (3.4.3).

### Host interface (ADR: host interface)

1. **FIFOs.** The CPU or the DMA writes the TX FIFO and reads the RX FIFO. The FIFOs make DREQ
   signals, so the DMA can transfer data with no CPU work (3.2.3.5).
2. **Empty and full.**
   - A blocking `PULL` on an empty TX FIFO stalls.
   - A non-blocking `PULL` on an empty TX FIFO copies X to OSR (3.4.7).
   - A blocking `PUSH` on a full RX FIFO stalls.
   - A non-blocking `PUSH` on a full RX FIFO clears the ISR, and the data is lost. The flag
     `FDEBUG_RXSTALL` is set (3.4.6).
   - `JMP !OSRE` and `MOV x, STATUS` let a program branch on the FIFO state (3.4.2, 3.4.8).
3. **Replacement on Tiny Tapeout.** Our chip has no CPU, no DMA, and no bus. These PIO features
   need a replacement on the pins:
   - the instruction memory write (program load),
   - the TX and RX FIFO access,
   - the `CTRL` register (start, stop, restart),
   - `SMx_INSTR` (forced instructions),
   - the system interrupts from the IRQ flags,
   - the configuration registers: `CLKDIV`, `PINCTRL`, `EXECCTRL`, and `SHIFTCTRL`.

### Pins

1. **Pin mappings.** `PINCTRL` has 4 ranges: `OUT` (up to 32 pins), `SET` (up to 5 pins),
   side-set (up to 5 pins), and `IN`. Each range is a base and a count of contiguous pins, and the
   ranges can overlap (3.2.5, 3.5.6). `IN` reads the GPIO inputs rotated right by `IN_BASE`
   (3.5.6.2). `JMP PIN` uses 1 more pin, `EXECCTRL_JMP_PIN` (3.4.2).
2. **Open drain for I2C.** The program drives the pin direction, not the level. The `i2c` program
   uses `.side_set 1 opt pindirs` for SCL and `OUT pindirs` for SDA (3.6.7). Output enable high
   means "drive low", so the sense is inverted. The RP2040 GPIO controls invert the output enable,
   which saves 1 instruction (3.6.7).
3. **WAIT.** `WAIT` waits for a 0 or a 1 on 1 of 3 sources: an absolute GPIO, an input-mapped
   pin, or an IRQ flag (3.4.3). Each GPIO input has a 2-flip-flop synchronizer
   (`INPUT_SYNC_BYPASS`, 3.7). A state machine sees its own output change after 4 cycles. With the
   synchronizer bypassed, it sees the change after 2 cycles (3.5.6.1). Bypass is safe only for
   synchronous inputs, such as SPI (3.5.6).

## RP2350 changes (RP2350 datasheet, 11.1.1)

| Change | Problem it solves |
|---|---|
| 3 PIO blocks (12 state machines), not 2 | More interfaces at the same time |
| `GPIOBASE` selects which 32 of 48 GPIOs a block uses | More than 32 GPIOs |
| `FJOIN_RX_GET` and `FJOIN_RX_PUT`: random access to the 4 RX FIFO entries | Control and status registers between the CPU and a state machine |
| `MOV PINDIRS`: set the direction of all `OUT` pins in 1 instruction | Bus turn-around |
| `WAIT` on `JMP_PIN` with an offset 0–3 | `WAIT` pins that are independent of the `IN` mapping |
| `MOV x, STATUS` can read the IRQ flags | Branch on an IRQ flag, not only stall on it |
| `IRQ` across PIO blocks, with no delay penalty | Synchronization of more than 4 state machines |
| `SHIFTCTRL.IN_COUNT` masks unused `IN` pins to 0 | `MOV x, PINS` returned a full rotated 32-bit value |
| All 8 IRQ flags can go to the system interrupts | Only the lower 4 could on RP2040 |

These changes show the problems that the RP2040 PIO users found. Our design can solve the same
problems.

## Limits of PIO

| Limit | Reason | Possible solution in our design |
|---|---|---|
| A program has a maximum of 32 instructions for 4 state machines. I2C uses 18 of them. | Instruction memory size (3.2.2) | The SRAM macro gives 256 words for approximately 3% of the area. |
| No arithmetic except decrement, `X!=Y`, invert, and bit-reverse. The datasheet shows addition as a curiosity (3.6.9). | The ALU is a decrementer and a comparator (3.4.2, 3.4.8). | Add `ADD`, `SUB`, and compare with an immediate. Add a CRC or parity unit. |
| No timeout on `WAIT`. A missing edge stops the state machine. | `WAIT` has no count field (3.4.3). This is our conclusion from the encoding. | `WAIT` with a cycle limit and a branch on timeout |
| The delay field has a maximum of 31 cycles, and side-set uses the same bits. | 5-bit shared field (3.4.1) | A separate delay counter, or a longer delay field |
| State machines cannot send data to each other. | Only IRQ flags are shared (3.2.7). | A shared register or a small mailbox |
| The fractional divider adds 1 cycle of jitter. | Clock-enable divider (3.5.5) | An integer divider, and the delay field for fine timing |
| Each pin mapping is 1 contiguous range. | Base and count in `PINCTRL` (3.5.6) | A pin mask or a pin-select table |
| No random access to the FIFOs on RP2040. RP2350 adds it. | FIFO-only host interface (3.2.3.5) | Memory-mapped registers in the host interface |
| The program needs a CPU for configuration, program load, and data. | The PIO is a peripheral (3.2) | A host interface on the Tiny Tapeout pins, for example an SPI target |

## Summary for the architecture

1. Copy the deterministic timing: 1 instruction for each cycle, with stalls only on explicit
   conditions.
2. Copy side-set and the delay field. They make the protocol programs short and cycle-exact.
3. Copy the 2-flip-flop input synchronizer, with a bypass for synchronous inputs.
4. Copy the open-drain output through the pin direction.
5. Change the program memory: use the SRAM macro with 256 words.
6. Change the ALU: add `ADD`, `SUB`, and compare. Many protocols need a checksum or a counter.
7. Change `WAIT`: add a timeout, so that a missing edge does not stop the core.
8. Change the host interface: replace the CPU bus with a pin interface, because the chip has no
   CPU.
9. Do not copy 4 state machines yet. The number of cores ADR must use the area of 1 core from
   the M2 harden.
