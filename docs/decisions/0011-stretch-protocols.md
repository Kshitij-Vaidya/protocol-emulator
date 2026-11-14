# ADR-0011: Stretch protocols

Status: **Accepted** (2026-11-14)

## Context
The plan selects 1–3 stretch protocols in week 7, from the area and timing margin. M4 is done.
The 2-core design meets 20 ns with +2.963 ns of setup slack at 22.97% utilization in 8x4 tiles
(`docs/area_log.md`). UART, SPI, I2C, and WS2812B firmware already operates on the RTL.

`docs/notes/protocols.md` lists the candidates:

| Protocol | Rate | Pins | Main operation |
|---|---|---|---|
| PS/2 | 10–16.7 kHz, clock from the device | CLK and DATA, open-drain | Wait for a CLK edge, sample DATA, odd parity |
| JTAG | Set by the target | TCK, TMS, TDI outputs; TDO input | As SPI, with TMS |
| SWD | Set by the target | SWCLK output; SWDIO bidirectional | As SPI, with a turn-around and parity |
| Low-speed USB | 1.5 Mbit/s ± 1.5% | D+ and D−, differential | NRZI, bit stuffing, SE0, a fast response |

## Options
1. PS/2 and JTAG.
2. PS/2, JTAG, and SWD.
3. Low-speed USB, with or without the others.
4. More cores (ADR-0009 allows 3 or 4) in place of more protocols.

## Decision
Use option 1.

1. Write PS/2 host firmware for both directions: receive from the device, and send a command
   to the device. Use the open-drain method of the I2C firmware.
2. Write JTAG controller firmware that shifts TMS and TDI and captures TDO, with a TAP model in
   the tests.
3. Each protocol needs an ISS test with a protocol model, a lockstep test, and a full-chip test.
4. Make no ISA or RTL change for these protocols. If one needs a change, write a new ADR before
   the freeze on 2026-12-20.
5. Keep 2 cores (ADR-0009).

## Consequences
- The design stays at 2 cores and 23% utilization. The area and timing margin stay for bug
  fixes after the freeze.
- SWD and low-speed USB are not supported. SWD can come later as firmware only, because it
  needs no new instruction.
- The demo set is UART, SPI, I2C, WS2812B, PS/2, and JTAG.
