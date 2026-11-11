# ADR-0009: Tile size

Status: **Accepted** (2026-11-11)

## Context
ADR-0003 plans N cores (2 to 4) for M5, each with its own SRAM macro. The plan selects the tile
size in week 5, from real hardens. `docs/area_log.md` has these results:

| Design | Tiles | Util (%) | Setup WS, slow (ns) | Hold WS, fast (ns) | Result |
|---|---|---|---|---|---|
| 1 core (`da32192`) | 4x2 | 56.38 | +3.167 | +0.146 | Passes all checks |
| 2 cores (`186ddbb`) | 8x2 | 44.86 | n/a | n/a | Detailed routing does not converge |
| 2 cores (`813c297`) | 8x4 | 20.85 | +3.994 | +0.147 | Passes all checks |

The 8x2 die is 313.74 µm tall. In the 8x2 harden, Metal3 (horizontal) had 81.6% usage and an
overflow of 7117 after global routing. Metal4 carries the vertical PDN stripes. Thus the
horizontal routing capacity, not the cell area, limits the design.

The 2-core design adds 77,269 µm² of cell area to the 1-core design. The 8x4 core area is
approximately 938,000 µm².

## Options
1. 4x2 tiles with 1 core.
2. 8x2 tiles with 2 cores.
3. 8x4 tiles with 2 to 4 cores.

## Decision
Use option 3.

1. Set `tiles` to `"8x4"` when the multi-core RTL merges into `main`. Until then, `main` keeps
   `"4x2"` for its 1 core.
2. Use 2 cores in M5. Each core has its own SRAM macro. Put each macro in a different part of
   the die.
3. Use 3 or 4 cores only if an experiment harden of that design passes all checks with a
   setup slack of +2 ns or more.

## Consequences
- 8x4 is the maximum size for the competition. No larger size is available if the design grows.
- Estimated utilization is 29% for 3 cores and 37% for 4 cores. Routing is the risk, not area.
- Keep `DRT_OPT_ITERS` at 20 for experiment hardens, so a run that cannot route fails early.
- Check the slack again after each change to the core count or to the macro locations
  (ADR-0008).
