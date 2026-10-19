# Architecture

Status: not started (milestone M1, weeks 2–3).

## Requirements summary
<!-- Source: docs/notes/protocols.md. Record the required clock, timing resolution, and pin types. -->

## Tiny Tapeout pin allocation
- `ui_in[7:0]`: dedicated inputs
- `uo_out[7:0]`: dedicated outputs
- `uio_in/out/oe[7:0]`: bidirectional pins (necessary for open-drain protocols, for example I2C)
- `clk`, `rst_n`, `ena`

## Block diagram

## Blocks
- Program memory and program-load path
- Fetch and decode
- Execute
- Pin I/O unit
- Delay counter and cycle counter
- Host interface

## Area budget
| Block | Estimated cells | Hardened cells |
|---|---|---|
| Total budget (6x4 tiles, 0.7 mm²) | 24K (approximate) | |

## Timing budget
