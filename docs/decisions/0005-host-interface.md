# ADR-0005: Host interface

Status: **Accepted** (2026-11-07)

## Context
The chip has no CPU. An external controller uses the host interface, for example the RP2040 or
RP2350 on the Tiny Tapeout demo board. PIO uses FIFOs, DMA, and configuration registers on the
system bus (refer to `docs/notes/pio.md`). The host interface must do these operations:
- halt and start each core, and set its start address,
- write the program memory,
- write and read the configuration (clock divider, pin mapping),
- send data to a core and get data from a core,
- read the status (halted, FIFO levels, flags).

The pins are 8 inputs, 8 outputs, and 8 bidirectional. The protocol pins need as many pins as
possible.

## Options
| Option | Host pins | Notes |
|---|---|---|
| 1. SPI target (mode 0) with a register map | 4 (SCK, CS, MOSI in; MISO out) | `cocotbext-spi` can test it. The demo board MCU has SPI. |
| 2. 8-bit parallel bus with a strobe | 11 or more | Fast, but it uses most of the pins. |
| 3. UART with a command protocol | 2 | Slow, and it needs a baud rate agreement. |

## Decision
Use option 1: an SPI target, mode 0, with a register map.

1. Pins: SCK, CS, and MOSI on `ui_in`; MISO on `uo_out`. Thus, 5 inputs, 7 outputs, and 8
   bidirectional pins remain for the protocols.
2. Synchronize SCK, CS, and MOSI to the core clock with 2 flip-flops, and detect the SCK edges.
   Thus, the design has 1 clock domain. SCK must be 1/4 of the core clock or less (12.5 MHz at
   50 MHz).
3. Each SPI transfer is a command byte, an address, and data. `docs/architecture.md` defines the
   register map.

## Consequences
- The design has only 1 clock domain, so the formal checks and STA stay simple.
- A program load of 256 × 16 bits takes approximately 0.4 ms at 10 MHz SCK.
- The host interface is a separate block with its own tests. The demo board firmware is part of
  M7.
- A protocol test needs 2 interfaces at the same time: the SPI host and the protocol pins. The
  cocotb tests must drive both.
