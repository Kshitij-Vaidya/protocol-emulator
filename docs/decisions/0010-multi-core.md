# ADR-0010: Multi-core interface

Status: **Accepted** (2026-11-14)

## Context
ADR-0003 and ADR-0009 select 2 cores for M5, each with its own SRAM macro, in 8x4 tiles. The
`twoCoreArea` experiment hardened 2 cores with temporary rules: 1 shared set of configuration
registers, a `CORE_SEL` register, ORed pin outputs, and 1 flag bank in each core.

The ISS already models more than 1 core (`sw/iss/README.md`):
- Rule 8: the cores execute in index order on each tick. A flag change by core n is visible to
  cores with a higher index on the same tick.
- Rule 9: the outputs from the cores are combined with OR.
- All cores share 1 `FlagBank`.

The interface between the cores and the host must be final at the feature freeze (2026-12-20).

## Options
1. Host select: a `CORE_SEL` register, or core number bits in the SPI command byte.
2. Pin outputs: OR, or a priority for each pin (as in PIO).
3. Flags: 1 shared bank, or 1 bank in each core.
4. Flag timing: a change is visible to higher cores on the same tick (ISS rule 8), or to all
   cores on the next cycle.

## Decision
1. **Host select: `CORE_SEL` (0x12).** Bits [1:0] hold the core number. A core number with no
   core reads and writes as 0. These registers go to the selected core: `CTRL`, `STATUS` bits
   [7:0], `MEM_ADDR`, `MEM_DATA`, `START_PC`, `EXEC`, `CLK_DIV`, `PIN_OUT`, `PIN_SET`,
   `PIN_SIDE`, `PIN_IN`, `SHIFT`, `WRAP`, `TX_FIFO`, and `RX_FIFO`. `SYNC_BYPASS_LO`,
   `SYNC_BYPASS_HI`, `ID`, and `STATUS` bits [15:8] (the flags) are shared.
2. **Start of all cores on the same cycle: `RUN_ALL` (0x13).** Bits [3:0] set `run` for cores
   0–3, and bits [7:4] request `restart` for cores 0–3. With 2 cores, bits [1:0] and [5:4]
   have an effect. 1 write starts all cores on the same cycle. A read gives the `run` bits.
3. **Pin outputs: OR.** The output levels and the output enables of the cores are ORed. All
   cores read the same synchronized inputs.
4. **Flags: 1 shared bank** in the top level, outside the cores.
5. **Flag timing: next cycle.** A flag change by any core is visible to all cores on the next
   cycle. If 2 cores set and clear 1 flag on the same cycle, the set wins. This replaces ISS
   rule 8, because a same-tick chain from core 0 to core 1 puts 2 decode paths in series. Each
   decode path already starts at the SRAM output (ADR-0008).
6. Data transfer between cores stays postponed (`docs/isa.md`, decision 3).
7. A restart of any core sets the shared flags to 0. A restart of 1 core can thus release a
   `FLAG wait` in another core.

## Consequences
- The ISS must change rule 8 before the 2-core lockstep test: flag changes take effect after
  all cores execute on a tick.
- With rule 5, 2 cores that wait on 1 flag (`WAIT 1 FLAG n`) both continue on the same cycle,
  and both clear the flag. With ISS rule 8, only core 0 continued.
- A change of the selected core costs 1 SPI transfer. Host software must set `CORE_SEL` before
  a burst to a per-core register.
- The host interface tests must cover each per-core register for each core, and the shared
  registers.
- `RUN_ALL` and `CORE_SEL` keep the single-core register map. Single-core host software works
  without a change, because `CORE_SEL` resets to 0.
