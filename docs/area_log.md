# Area Log

This file records the area and timing of each hardened design.

Procedure:

1. Find the run ID of the `gds` workflow run in GitHub Actions.
2. Run `python scripts/gdsMetrics.py <run ID>`. If you do not give a run ID, the script uses the
   newest successful `gds` run.
3. Copy the row from the "Area log row" section of the output into the table.
4. Write the tile size and the design in the Notes column.

NOTE: The setup worst slack (Setup WS) is at the slow corner. The hold worst slack (Hold WS) is at
the fast corner. The clock period is 20 ns (50 MHz).

| Date | Commit | Run | Cells | Area (µm²) | Util (%) | Setup WS (ns) | Hold WS (ns) | DRC | LVS | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-18 | 6e2caaf | 39120908387 | 246 | 3470.95 | 11.99 | 13.231 | 0.121 | 0 | 0 | M0. 1x1 tile. `uartTx` only. |
| 2026-11-07 | b6a84cd | 42352888754 | 597 | 9057.48 | 29.35 | 12.990 | 0.126 | n/a | 0 | SRAM macro test. 2x2 tile. `uartTx` and `progMem` (256 × 16 SRAM). Magic DRC off; precheck KLayout DRC passes. Power checks pass. |
| 2026-11-09 | e4bd186 | 42650467327 | 8811 | 113193.00 | 54.39 | 0.123 | 0.117 | n/a | 0 | M2. 4x2 tile. Core, `hostSpi`, and `progMem`. Timing-driven placement, post-GRT repair, and a 3 ns resizer setup margin. Magic DRC off; precheck and GL test pass. |
| 2026-11-10 | ae5afdc | 42762426143 | 8782 | 114140.00 | 54.75 | 0.384 | 0.132 | n/a | 0 | M2. 4x2 tile. One shared pin write rotator, a prefix adder for ADD and SUB, and a FIFO write enable from `full` only. Magic DRC off; precheck and GL test pass. |

## Budget

| Item | Value |
|---|---|
| Tile size limit | 8x4 |
| Nominal tile area | 0.93 mm² (use this value for the budget) |
| 8x4 die area | 1724.16 µm × 710.64 µm = 1.225 mm² |
| Cell budget | 32K cells (approximate). The rules have no cell count limit. |
| Target utilization | 60–70% or less |
