## How it works

This is a programmable I/O processor. A core with deterministic timing executes a program from
a 256 × 16-bit program memory (the IHP SRAM macro). The program drives and samples pins with
exact timing, so firmware can emulate protocols such as UART, SPI, and WS2812B.

Each instruction executes in 1 tick. A 16-bit clock divider sets the tick. Each instruction can
also set up to 3 pins (side-set) and add a delay of up to 15 ticks.

A host loads the program and controls the core through an SPI target interface (mode 0). The
host also sends data to the core and receives data from it through 2 FIFOs of 4 words each.

The protocol pins have pin numbers:

| Pin numbers | Tiny Tapeout pins | Direction |
|---|---|---|
| 0–7 | `uio[7:0]` | Bidirectional |
| 8–14 | `uo[7:1]` | Output |
| 15–19 | `ui[7:3]` | Input |

The instruction set is in `docs/isa.md`. The register map is in `docs/architecture.md`.

## How to test

CAUTION: Keep SCK at the clock frequency divided by 16 or less (3 MHz at 48 MHz).

1. Connect an SPI controller (mode 0) to `ui[0]` (SCK), `ui[1]` (CS), `ui[2]` (MOSI), and
   `uo[0]` (MISO).
2. Read register 0x11. The value must be 0x5045.
3. Assemble a program with `sw/asm/assembler.py`. For example, use `sw/asm/examples/uartTx.pasm`.
4. Write 0 to register 0x02 (`MEM_ADDR`). Write the program words to register 0x03 (`MEM_DATA`).
5. Write the configuration registers 0x06 to 0x0C. For the UART TX example at 115200 baud and
   48 MHz, use `CLK_DIV` 104, and set pin 8 as the OUT pin and the side-set pin.
6. Write 0b11 to register 0x00 (`CTRL`) to start the core.
7. Write bytes to register 0x0D (`TX_FIFO`). The core sends them on `uo[1]`.

## External hardware

- An SPI controller at 3.3 V, for example the demo board microcontroller.
- For the UART examples: a USB-to-UART adapter at 3.3 V.
