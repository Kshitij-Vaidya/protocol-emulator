# Area Log

This file records the area and timing of each hardened design. Add 1 row after each harden.

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

## Budget

| Item | Value |
|---|---|
| Tile size limit | 6x4 |
| Nominal tile area | 0.7 mm² (use this value for the budget) |
| 6x4 die area | 1289.28 µm × 710.64 µm = 0.916 mm² |
| Cell budget | 24K cells (approximate) |
| Target utilization | 60–70% or less |
