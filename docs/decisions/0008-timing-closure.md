# ADR-0008: Timing closure

Status: **Accepted** (2026-11-10)

## Context
The first harden of the M2 design (`e4bd186`) had a setup worst slack of +0.123 ns at the slow
corner. The clock period is 20 ns (ADR-0007). All of the worst setup paths start at the SRAM
data output. The SRAM clock-to-data-out delay is 5.3 ns at the slow corner in the routed design.

The resizer after global routing saw more setup slack than the final STA after detailed routing.
The difference was approximately 3 ns.

`docs/area_log.md` has the results of each harden. `docs/architecture.md` has the slack of each
register group.

## Options
1. Increase `CLOCK_PERIOD`.
2. Add a pipeline stage between the SRAM output and the execute logic.
3. Make the RTL paths shorter, and increase the resizer setup margin after global routing.

## Decision
Use option 3.

1. Make these RTL changes in `src/core.v` and `src/fifo.v`:
   - OUT, MOV, and SET use 1 shared pin write rotator.
   - ADD and SUB use 1 parallel-prefix adder (`prefixAdd`).
   - The FIFO write enable of the entries comes from `full` only, not from the push decision.
2. Set these values in `src/config.json`:
   - `PL_TIMING_DRIVEN`: 1.
   - `RUN_POST_GRT_RESIZER_TIMING` and `RUN_POST_GRT_DESIGN_REPAIR`: 1.
   - `PL_RESIZER_SETUP_SLACK_MARGIN`: 3 ns. `GRT_RESIZER_SETUP_SLACK_MARGIN`: 6 ns.
   - `PL_RESIZER_HOLD_SLACK_MARGIN`: 0.1 ns. `GRT_RESIZER_HOLD_SLACK_MARGIN`: 0.15 ns.
3. Do not use option 1. It conflicts with the 50 MHz target in ADR-0007.
4. Do not use option 2. It breaks the 1-instruction-per-cycle timing model (ADR-0004).

| Commit | Change | Setup WS, slow (ns) | Hold WS, fast (ns) |
|---|---|---|---|
| `e4bd186` | First M2 harden | +0.123 | +0.117 |
| `ae5afdc` | RTL changes | +0.384 | +0.132 |
| `d95f488` | Setup margin after global routing: 6 ns | +3.345 | +0.072 |
| `da32192` | Hold margin after global routing: 0.15 ns | +3.167 | +0.146 |

A Yosys equivalence check proved the RTL changes against the earlier RTL (988 of 988 points).

## Consequences
- The design meets 20 ns with +3.167 ns of setup slack at the slow corner.
- The resizer adds cells. The area increased from 113,193 µm² to 118,361 µm² (approximately 5%).
- The hold slack at the fast corner is small (+0.146 ns). Check it in each harden.
- A change to the core count (ADR-0003) or to the tile size changes the routes. Check the slack
  again after each of these changes.

CAUTION: Do not set `GRT_RESIZER_SETUP_SLACK_MARGIN` below 6 ns. The final setup slack can become
less than 1 ns.
