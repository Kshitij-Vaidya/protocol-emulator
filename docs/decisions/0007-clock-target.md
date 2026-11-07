# ADR-0007: Clock target

Status: **Accepted** (2026-11-07)

## Context
`docs/notes/protocols.md` shows these results:
- 50 MHz is sufficient for UART, SPI (approximately 10 MHz), I2C (all 3 modes), WS2812B, PS/2,
  JTAG, and SWD.
- 48 MHz gives exact bit times for 1 Mbaud and 3 Mbaud UART, and 32 cycles for each USB
  low-speed bit.
- The demo board can make each of these clocks.

The M0 design and the SRAM macro test meet a 20 ns clock period with more than 12 ns of setup
slack. The core is not hardened yet.

## Options
1. Constrain STA at 20 ns (50 MHz), and operate at 50 MHz.
2. Constrain STA at 20 ns (50 MHz), and operate at 48 MHz or less.
3. Constrain STA at a shorter period, for example 15 ns (66.7 MHz).

## Decision
Use option 2.

1. Keep `CLOCK_PERIOD` at 20 ns in `src/config.json`.
2. The chip operates at any clock of 50 MHz or less. A design that meets 20 ns also meets
   20.83 ns (48 MHz).
3. The assembler and the ISS take the clock frequency as a parameter. Firmware calculates its
   delays from this value.
4. The demo uses 48 MHz. Check the setup slack in the week 5 harden. If the core does not meet
   20 ns, change `CLOCK_PERIOD` and this ADR.

## Consequences
- The firmware is not fixed to 1 clock frequency.
- A clock above 50 MHz is not tested in STA, so the documentation must not claim it.
- The SKY130 output pad limit (33 MHz) is above the fastest protocol signal (SPI at
  approximately 10 MHz). Check the IHP pad values before week 7.
