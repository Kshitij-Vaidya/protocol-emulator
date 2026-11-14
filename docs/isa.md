# Instruction Set

Status: v0.1 (2026-11-07). The decisions are in ADR-0002 (16-bit instructions), ADR-0003
(1 core for M2), ADR-0004 (timing model), and ADR-0007 (clock).

## Design goals
- Deterministic timing. The programmer can calculate the exact cycle of each operation.
- Pin set, pin clear, and pin read operations. Parallel pin updates together with other operations.
- A wait-for-pin operation and a wait-for-N-cycles operation.
- A program memory that is small enough for the area budget.
- Fix the PIO limits that `docs/notes/pio.md` lists: no arithmetic, no `WAIT` timeout, and 32
  instructions.

## Terms
- **Tick**: 1 cycle of the core clock enable. The clock divider makes 1 tick for each
  `clkDiv` core clock cycles.
- **Timing field**: the 4 bits [12:9] of each instruction. They hold the side-set bits and the
  delay.

## Programmer's model

Each core has these registers. The data width is 16 bits.

| Register | Width | Use |
|---|---|---|
| `PC` | 8 | Address of the current instruction (256 words) |
| `X`, `Y` | 16 | Scratch registers, loop counters, ALU operands |
| `ISR` | 16 | Input shift register. `IN` shifts data in. `PUSH` sends it to the RX FIFO. |
| `OSR` | 16 | Output shift register. `PULL` loads it from the TX FIFO. `OUT` shifts data out. |
| `T` | 16 | Timeout value for `WAIT` |
| `STATUS` | 16 | Read-only flags (refer to *Status bits*) |

Each core also has these parts:

| Part | Description |
|---|---|
| TX FIFO, RX FIFO | 4 words of 16 bits each. The host writes the TX FIFO and reads the RX FIFO. |
| Shift counters | 0–16 bits shifted out of `OSR` and into `ISR`, for autopull and autopush |
| Clock divider | 16-bit integer `clkDiv` (1–65535). 1 means 1 tick on each core clock cycle. 0 has the same effect as 1. A new value takes effect within 1 tick. |
| Wrap registers | `wrapTop` and `wrapBottom`. After the instruction at `wrapTop`, the PC goes to `wrapBottom` with no cycle cost. |
| Pin mapping | `outBase`/`outCount`, `setBase`/`setCount`, `sideBase`/`sideCount`, `inBase`, `jmpPin`, as in PIO |
| Side-set configuration | `sideCount` (0–3 bits), `sideEn` (optional enable bit), `sidePinDir` (drive the levels or the directions) |

The cores share 8 flags (`F0`–`F7`). The host can read all 8 flags.

### Pin numbers

The pin mapping uses a 5-bit pin number. The host interface uses 4 pins (ADR-0005).

| Pin numbers | Tiny Tapeout pins | Direction |
|---|---|---|
| 0–7 | `uio[7:0]` | Bidirectional. Output enable from `PINDIRS`. Use these pins for open drain. |
| 8–14 | `uo_out[7:1]` | Output only |
| 15–19 | `ui_in[7:3]` | Input only |
| 20–31 | none | Reads as 0. Writes have no effect. |

Each input has a 2-flip-flop synchronizer. The core reads a synchronized input 2 cycles late.

The 32-bit `syncBypass` register has 1 bit for each pin number. A 1 bypasses the synchronizer of
that pin, and the core reads the pin in the same cycle. The cores share `syncBypass`. Bits for
pins that are not inputs have no effect. The host writes `syncBypass` while the cores are halted
(ADR-0006).

CAUTION: Use the bypass only for an input that changes at a known time after a core output edge,
for example MISO after SCK. An asynchronous input that is bypassed can make a flip-flop
metastable.

## Timing rules

1. Each instruction executes in 1 tick.
2. Only these instructions can stall: `WAIT`, a blocking `PUSH` or `PULL`, `FLAG WAIT`, and
   `OUT` or `IN` with autopull or autopush when the FIFO is empty or full.
3. During a stall, the PC does not change. The delay starts after the stall ends.
4. Side-set takes effect on the first tick of the instruction, also when the instruction stalls.
5. The delay adds 0–15 ticks after the instruction. The side-set bits reduce this range (refer to
   *Timing field*).

## Encoding

Each instruction is 16 bits.

| Bits | 15:13 | 12:9 | 8:0 |
|---|---|---|---|
| Field | Opcode | Timing field | Operands |

### Timing field

The core configuration sets how the 4 bits divide:

| `sideCount` | `sideEn` | Side-set bits | Delay bits | Maximum delay |
|---|---|---|---|---|
| 0 | 0 | 0 | 4 | 15 ticks |
| 1 | 0 | 1 | 3 | 7 ticks |
| 1 | 1 | 1 + enable | 2 | 3 ticks |
| 2 | 0 | 2 | 2 | 3 ticks |
| 3 | 0 | 3 | 1 | 1 tick |

### Opcodes

| Opcode | Mnemonic | Operands [8:0] |
|---|---|---|
| 000 | `JMP` | [8:6] condition, [5:0] signed offset (−32 to +31) from this instruction |
| 001 | `WAIT` | [8] polarity, [7:6] source, [5] timeout enable, [4:0] index |
| 010 | `IN` | [8:6] source, [5:4] reserved (0), [3:0] bit count (0 means 16) |
| 011 | `OUT` | [8:6] destination, [5:4] reserved (0), [3:0] bit count (0 means 16) |
| 100 | `PUSH` / `PULL` | [8] 0 = `PUSH`, 1 = `PULL`; [7] if-full or if-empty; [6] block; [5:0] reserved (0) |
| 101 | `MOV` | [8:6] destination, [5:3] operation, [2:0] source |
| 110 | `SET` | [8:6] destination, [5:0] unsigned data (0–63) |
| 111 | `FLAG` | [8:7] operation, [6:3] reserved (0), [2:0] flag index |

### JMP conditions

| Code | Condition | Description |
|---|---|---|
| 000 | (always) | Always jump |
| 001 | `!X` | Jump if X = 0 |
| 010 | `X--` | Jump if X ≠ 0, then decrement X |
| 011 | `Y--` | Jump if Y ≠ 0, then decrement Y |
| 100 | `X!=Y` | Jump if X ≠ Y |
| 101 | `PIN` | Jump if the `jmpPin` input is 1 |
| 110 | `!OSRE` | Jump if `OSR` is not empty (shift count below the pull threshold) |
| 111 | `TIMEOUT` | Jump if the last `WAIT` ended by timeout |

The decrement in `X--` and `Y--` always occurs, as in PIO.

### WAIT

| Field | Values |
|---|---|
| Polarity | 1: wait for 1. 0: wait for 0. |
| Source | 00: pin number (absolute). 01: input-mapped pin (`inBase` + index). 10: flag (index 0–7). 11: reserved. |
| Timeout enable | 1: the wait ends after `T` stalled ticks if the condition is not met. The `WAIT` then takes `T` + 1 ticks. The `TIMEOUT` status bit is set. |

Each `WAIT` clears the `TIMEOUT` status bit when it starts. Thus, `JMP TIMEOUT` directly after a
`WAIT` tests that `WAIT` only.

A `WAIT` on a flag with polarity 1 clears the flag when the condition is met, as in PIO.

### IN sources and OUT destinations

| Code | `IN` source | `OUT` destination |
|---|---|---|
| 000 | `PINS` | `PINS` |
| 001 | `X` | `X` |
| 010 | `Y` | `Y` |
| 011 | `NULL` (zeros) | `NULL` (discard) |
| 100 | reserved | `PINDIRS` |
| 101 | reserved | `PC` |
| 110 | `ISR` | `ISR` |
| 111 | `OSR` | `EXEC` (execute the data as an instruction on the next tick) |

### MOV

`MOV` copies or combines the source into the destination.

| Code | Destination | Operation | Source |
|---|---|---|---|
| 000 | `PINS` | copy: dst = src | `PINS` |
| 001 | `X` | invert: dst = ~src | `X` |
| 010 | `Y` | bit-reverse: dst = reverse(src) | `Y` |
| 011 | `T` | add: dst = dst + src | `NULL` |
| 100 | `EXEC` | subtract: dst = dst − src | `STATUS` |
| 101 | `PC` | and: dst = dst & src | `ISR` |
| 110 | `ISR` | or: dst = dst \| src | `OSR` |
| 111 | `OSR` | xor: dst = dst ^ src | `T` |

`NOP` is `MOV Y, Y` with the copy operation.

The operations add to xor use the destination as the first operand. They are valid only for the
destinations `X`, `Y`, and `T`. The assembler rejects other combinations.

### SET destinations

| Code | Destination |
|---|---|
| 000 | `PINS` |
| 001 | `X` |
| 010 | `Y` |
| 011 | `T` |
| 100 | `PINDIRS` |
| 101–111 | reserved |

### FLAG operations

| Code | Operation |
|---|---|
| 00 | Set the flag |
| 01 | Clear the flag |
| 10 | Set the flag, then stall until it is clear |
| 11 | reserved |

### Status bits

| Bit | Name | Meaning |
|---|---|---|
| 0 | `txEmpty` | The TX FIFO is empty |
| 1 | `rxFull` | The RX FIFO is full |
| 2 | `timeout` | The last `WAIT` ended by timeout |
| 7:3 | reserved | 0 |
| 15:8 | `flags` | `F7`–`F0` |

## Example programs

The examples use the assembler syntax in `sw/asm/README.md`. `side n` sets the side-set bits,
and `[n]` sets the delay.
The ISS must run each example against a Python protocol model in week 3.
The programs in `sw/asm/examples` must be the same as these programs.

### UART TX (8N1), 4 instructions

Configuration: `sideCount` 1, `sideEn` 1, side-set pin and OUT pin = TX. 4 ticks for each bit:
`clkDiv` = f / (4 × baud). At 48 MHz and 115200 baud, `clkDiv` = 104 (+0.16%).

```
.side_set 1 opt
    pull        side 1 [3]  ; stop bit, or idle while the TX FIFO is empty
    set x, 7    side 0 [3]  ; start bit, 4 ticks
bitLoop:
    out pins, 1             ; 1 data bit
    jmp x-- bitLoop    [2]  ; 4 ticks for each bit
```

### UART RX (8N1) with framing check, 9 instructions

Configuration: `sideCount` 0, IN pin and `jmpPin` = RX. 8 ticks for each bit.

```
start:
    wait 0 pin 0            ; start bit
    set x, 7           [10] ; 12 ticks from the edge: the center of data bit 0
bitLoop:
    in pins, 1
    jmp x-- bitLoop    [6]  ; 8 ticks for each bit
    jmp pin goodStop
    flag set 0              ; framing error or break
    wait 1 pin 0            ; wait for the idle line
    jmp start
goodStop:
    push
```

### SPI controller, mode 0 (CPHA 0), 2 instructions

Configuration: `sideCount` 1, side-set pin = SCK, OUT pin = MOSI, IN pin = MISO, autopull and
autopush at 8 bits.

```
.wrap_target
    out pins, 1   side 0 [1]
    in pins, 1    side 1 [1]
.wrap
```

### WS2812B, 4 instructions

Configuration: `sideCount` 1, side-set pin = DIN, OUT shift left, autopull at 8 bits. Each FIFO
word holds 1 byte in bits 15:8 (refer to open question 1). 10 ticks for each bit: `clkDiv` = 6
at 48 MHz (125 ns tick, 1.25 µs bit).

```
.side_set 1
.wrap_target
bitLoop:
    out x, 1        side 0 [2]  ; low for 3 ticks
    jmp !x doZero   side 1 [2]  ; high for 3 ticks
    jmp bitLoop     side 1 [3]  ; 1 bit: high for 4 more ticks
doZero:
    nop             side 0 [3]  ; 0 bit: low for 4 more ticks
.wrap
```

| Time | Ticks | Value | Datasheet range |
|---|---|---|---|
| T0H | 3 | 375 ns | 250–550 ns |
| T0L | 4 + 3 | 875 ns | 700–1000 ns |
| T1H | 3 + 4 | 875 ns | 650–950 ns |
| T1L | 3 | 375 ns | 300–600 ns |
| Bit | 10 | 1.25 µs | 0.65–1.85 µs |

### SPI controller with chip select, mode 0, 9 instructions

Configuration: `sideCount` 1, side-set pin = SCK, OUT pin = MOSI, `SET` pin = CS, IN pin =
MISO. OUT and IN shift left. Autopull and autopush are off. Each FIFO word holds 1 byte in bits
15:8. CS is low for each byte. The RX FIFO gets the received byte in bits 7:0.

```
.side_set 1
    set pins, 1        side 0
.wrap_target
    pull               side 0
    set pins, 0        side 0
    set x, 7           side 0
bitLoop:
    out pins, 1        side 0 [1]
    in pins, 1         side 1
    jmp x-- bitLoop    side 1
    push               side 0
    set pins, 1        side 0
.wrap
```

### I2C controller, 32 instructions

Configuration: SDA and SCL are 2 adjacent pins from 0 to 7, each with an external pull-up.

| Setting | Value |
|---|---|
| `sideCount` | 1, with `sideEn` and `sidePinDir`. The side-set pin is SCL. |
| `outBase`, `outCount` | SDA, 1 |
| `setBase`, `setCount` | SDA, 2. Bit 0 is SDA, bit 1 is SCL. |
| `inBase`, `jmpPin` | SDA, SCL |
| Shift direction | OUT and IN shift left. Autopull and autopush are off. |

The program drives a pin low with a pin direction of 1, and releases the pin with a direction
of 0. The pin output register stays 0.

| Host word bits | Function |
|---|---|
| 15 | 1: send a START (or a repeated START) before the byte |
| 14 | 1: send a STOP after the byte |
| 13:6 | Data byte. For a read, use 0xFF. |
| 5 | Level of SDA from the controller on the ACK clock. 1 for a write or for the last read byte. 0 to acknowledge a read byte. |

For each byte, the RX FIFO gets 1 word: bits 8:1 hold SDA during the 8 data clocks, and bit 0
holds SDA during the ACK clock (0 is ACK).

Each bit takes 14 ticks: SCL is low for 8 ticks and high for 6 ticks. At 48 MHz, `clkDiv` 9 gives
381 kHz (Fast-mode), and `clkDiv` 36 gives 95 kHz (Standard-mode). A target can stretch SCL for
up to 63 ticks. A longer stretch sets flag 1, and the program stops until a restart.

```
.side_set 1 opt pindirs
    set t, 63
    set pindirs, 0
.wrap_target
nextWord:
    pull
    mov osr, ~osr
    out x, 1
    jmp x-- byteStart
    jmp pin startHigh
    set pindirs, 2     [3]
    set pindirs, 0     [3]
startHigh:
    wait 1 gpio 1 timeout
    jmp timeout busError [2]
    set pindirs, 1     [3]
    set pindirs, 3     [3]
byteStart:
    out y, 1
    set x, 8
bitLoop:
    out pindirs, 1     side 1 [3]
    nop                side 1 [3]
    nop                side 0
    wait 1 gpio 1 timeout
    jmp timeout busError
    in pins, 1         [1]
    jmp x-- bitLoop
    push               side 1 [3]
    jmp y-- nextWord
    set pindirs, 3     [3]
    set pindirs, 1     [3]
    wait 1 gpio 1 timeout
    jmp timeout busError [2]
    set pindirs, 0     [3]
    nop                [3]
.wrap
busError:
    flag set 1
errorLoop:
    jmp errorLoop
```

### Use of the WAIT timeout (I2C clock stretch)

```
    set t, 50               ; timeout: 50 ticks
    wait 1 pin 1 timeout    ; wait for SCL high (clock stretch)
    jmp timeout busError    ; the target held SCL low too long
```

## Decisions for v0.1

1. **Timing field width: 4 bits.** The delay is 0–15 ticks. The jump offset is −32 to +31, and
   the `SET` data is 0–63. PIO uses 5 bits. The integer clock divider gives long delays, and a
   256-word program memory needs longer jumps.
2. **Data width: 16 bits.** This is the same as the SRAM word and the FIFO word. PIO uses 32
   bits. With 16 bits, a 24-bit WS2812B pixel needs more than 1 FIFO word (open question 1).
3. **Data between cores: postponed to v0.2.** The flags synchronize the cores, but they do not
   move data (PIO limit). Decide a shared register together with the number of cores (ADR-0003,
   week 5).
4. **Input synchronizer bypass: in v0.1.** The ISS shows that the SPI controller program fails
   at `clkDiv` 1 (SCK 12 MHz at 48 MHz) with the synchronizer on MISO. With the bypass on MISO, it
   operates. The synchronizer limits SCK to 6 MHz at 48 MHz. Add `syncBypass` to the host
   register map. The MISO data must arrive within 2 cycles (41.7 ns at 48 MHz) after the SCK
   falling edge. This time includes the mux round trip (20 ns) and the target clock-to-output
   delay. Check it against the IHP pad values before week 7.

## Open questions

1. **Autopull of more than 16 bits.** WS2812B needs 24 bits for each pixel. The ISS shows that
   autopull at 8 bits, with 3 FIFO words for each pixel, keeps the exact bit timing. The cost is
   3 host writes for each pixel. Decide in week 5 if a 32-bit pull threshold is necessary.
2. **I2C program.** Closed. The I2C controller above has 32 instructions. It does not need
   `OUT EXEC`, because the host word holds the START and STOP requests.
3. **UART RX tolerance.** The UART RX program receives back-to-back frames with a baud error of
   ±2%. At −3%, it loses the frame alignment, because it uses 2 ticks after the stop-bit sample.
