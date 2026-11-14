# Architecture

Status: v0.2 (2026-11-14). The design has 2 cores (ADR-0009, ADR-0010). The ISA is in
`docs/isa.md`.

## Requirements summary
The source is `docs/notes/protocols.md`.

- Core clock: 50 MHz or less. STA uses 20 ns. The demo uses 48 MHz (ADR-0007).
- Timing resolution: 1 core clock cycle. The 16-bit clock divider sets the tick (ADR-0004).
- Pin types: 8 bidirectional pins for open-drain protocols (I2C), 7 outputs, and 5 inputs.

## Tiny Tapeout pin allocation

| Tiny Tapeout pins | Function |
|---|---|
| `ui_in[0]` | Host SCK |
| `ui_in[1]` | Host CS, active low |
| `ui_in[2]` | Host MOSI |
| `ui_in[7:3]` | Protocol inputs, pin numbers 15–19 |
| `uo_out[0]` | Host MISO |
| `uo_out[7:1]` | Protocol outputs, pin numbers 8–14 |
| `uio[7:0]` | Protocol bidirectional pins, pin numbers 0–7. `uio_oe` comes from `PINDIRS`. |
| `clk`, `rst_n` | Core clock and synchronous active-low reset |

## Block diagram

```
          ui_in[2:0]                         ui_in[7:3], uio_in
              |                                     |
        +-----v-----+   config, control    +--------v--------+
        |  hostSpi  |--------------------->|     pinSync     |
        | registers |                      | 2 flops, bypass |
        +--+-----+--+                      +--------+--------+
   memAddr |     | TX/RX FIFO, execute              | pinsIn
   write   |     |                         +--------v--------+
        +--v-----+--+   fetchAddr          |      core       |--> uo_out[7:1]
        |  progMem  |<---------------------| fetch, decode,  |--> uio_out, uio_oe
        | SRAM 256  |--------------------->| execute, FIFOs  |
        +-----------+   fetchData          +-----------------+
```

## Blocks

| Block | File | Function |
|---|---|---|
| Top level | `src/tt_um_protocolEmulator.v` | Connects the blocks, ORs the pin outputs of the cores, and maps the pins |
| Host interface | `src/hostSpi.v` | SPI target, mode 0, and the register map, with 1 register set for each core |
| Core slice | `src/coreSlice.v` | 1 core and its program memory |
| Flag bank | `src/flagBank.v` | The 8 flags that all cores share |
| Program memory | `src/progMem.v` | The SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist`, with a 1-cycle read latency |
| Input synchronizer | `src/pinSync.v` | 2 flip-flops on each input, and the `syncBypass` mask |
| Core | `src/core.v` | Fetch, decode, execute, side-set, delay, clock divider, and the TX and RX FIFOs |
| FIFO | `src/fifo.v` | 4 words of 16 bits |

### Program memory owner
Each core has its own program memory. A core owns its program memory while its `CTRL.run` is 1
or the core is active. Otherwise the host owns it. The host interface rejects a `MEM_DATA` write or an `EXEC` write while the core owns
the memory (ADR-0006).

### Fetch
The SRAM address is the next PC. The core calculates the next PC from the current instruction in
the same cycle. Thus, the core executes 1 instruction in each cycle, with the 1-cycle read
latency of the SRAM.

All of the worst setup paths start at the SRAM data output, because the decode and the execute
logic use the instruction in the same cycle. The SRAM clock-to-data-out delay is 5.3 ns at the
slow corner in the routed design. The path to the SRAM address has a setup slack of +3.988 ns.
The "Timing budget" section has the slack of each register group.

### Start
1. The host writes `CTRL` with `run` set to 1.
2. On the next cycle, the core reads the instruction at the PC.
3. On the cycle after that, the core is active, and it executes the first instruction. This is
   cycle 0 of the ISS (`sw/iss/README.md`).

A write of 1 to `CTRL.restart` resets the state of the selected core. The PC gets `START_PC`. The
FIFOs and the pin registers get 0. A restart of any core also sets the shared flags to 0.

### Cores
- `CORE_SEL` selects the core for the per-core registers (ADR-0010). Its reset value is 0, so
  single-core host software operates core 0 without a change.
- `RUN_ALL` sets `run` and requests `restart` for all cores in 1 write. The cores then start on
  the same cycle.
- The output levels and the output enables of the cores are ORed. All cores read the same
  synchronized inputs.
- A flag change by any core is visible to all cores on the next cycle. If 1 core sets a flag
  and another core clears it on the same cycle, the set wins.

### Halt
1. The host writes `CTRL` with `run` set to 0.
2. On the next cycle, the core can complete 1 more instruction.
3. The core then clears the stall, the remaining delay, and the pending `EXEC` instruction.
   The PC, the registers, the FIFOs, and the pins keep their values.

A later write of 1 to `run` starts a new instruction at the PC. Thus a `WAIT` or a delay
that the halt stopped starts again from the beginning.

### Pin levels at reset
Reset and `CTRL.restart` set the pin output and direction registers to 0. An output-only pin
(8–14) drives 0 until the firmware sets it.

CAUTION: Do not put an active-low select, for example SPI CS, on pins 8–14 if the target
must stay deselected while the host loads the program. Use a pin from 0 to 7 with an
external pull-up. The pin is an input until the firmware sets its direction.

### Timing rules
The core RTL obeys the timing rules in `sw/iss/README.md`. The lockstep test
(`test/testCoreLockstep.py`) compares the RTL with the ISS after each cycle.

## Host interface

### SPI transfer
The host interface is an SPI target in mode 0 (CPOL 0, CPHA 0), MSB first (ADR-0005).

1. The host sets CS low.
2. The host sends 1 command byte. Bit 7 is 1 for a write and 0 for a read. Bits 6:0 are the
   register address.
3. The host sends or receives 1 or more 16-bit words. All words in 1 transfer use the same
   register.
4. The host sets CS high.

A burst of words to `MEM_DATA` writes or reads consecutive addresses. A burst to `TX_FIFO` or
`RX_FIFO` writes or reads consecutive FIFO words.

CAUTION: SCK must be the core clock divided by 16 or less: 3 MHz at 48 MHz. SCK, CS, and MOSI go
through 2-flop synchronizers, and MISO changes up to 6 cycles after the SCK rising edge.

### Register map

| Address | Name | Access | Bits |
|---|---|---|---|
| 0x00 | `CTRL` | R/W | [0] `run`. [1] `restart` (write 1, reads 0). A write clears `STATUS.rejected`. |
| 0x01 | `STATUS` | R | [0] `active`. [1] `rejected`. [4:2] TX FIFO level. [7:5] RX FIFO level. [15:8] flags `F7`–`F0`. |
| 0x02 | `MEM_ADDR` | R/W | [7:0] program memory address |
| 0x03 | `MEM_DATA` | R/W | Program memory word at `MEM_ADDR`. Each access increments `MEM_ADDR`. |
| 0x04 | `START_PC` | R/W | [7:0] PC after `restart` |
| 0x05 | `EXEC` | W | The core executes this instruction 1 time. The core must be halted. |
| 0x06 | `CLK_DIV` | R/W | [15:0] `clkDiv`. Reset value: 1. A write takes effect within 1 tick, also while the core runs. 0 has the same effect as 1. |
| 0x07 | `PIN_OUT` | R/W | [4:0] `outBase`. [12:8] `outCount`. |
| 0x08 | `PIN_SET` | R/W | [4:0] `setBase`. [10:8] `setCount`. |
| 0x09 | `PIN_SIDE` | R/W | [4:0] `sideBase`. [9:8] `sideCount`. [10] `sideEn`. [11] `sidePinDir`. |
| 0x0A | `PIN_IN` | R/W | [4:0] `inBase`. [12:8] `jmpPin`. |
| 0x0B | `SHIFT` | R/W | [0] `outShiftRight`. [1] `inShiftRight`. [2] `autoPull`. [3] `autoPush`. [8:4] `pullThreshold`. [13:9] `pushThreshold`. Reset value: 0x2103. |
| 0x0C | `WRAP` | R/W | [7:0] `wrapBottom`. [15:8] `wrapTop`. Reset value: 0xFF00. |
| 0x0D | `TX_FIFO` | W | Writes 1 word to the TX FIFO. A write to a full FIFO sets `STATUS.rejected`. |
| 0x0E | `RX_FIFO` | R | Reads 1 word from the RX FIFO. An empty FIFO reads as 0. |
| 0x0F | `SYNC_BYPASS_LO` | R/W | `syncBypass` bits 15:0 |
| 0x10 | `SYNC_BYPASS_HI` | R/W | `syncBypass` bits 31:16 |
| 0x11 | `ID` | R | 0x5045 |
| 0x12 | `CORE_SEL` | R/W | [1:0] core for the per-core registers. A value with no core makes the per-core registers read as 0 and ignore writes. |
| 0x13 | `RUN_ALL` | R/W | [1:0] `run` of cores 0 and 1. [5:4] `restart` of cores 0 and 1 (write 1, not stored). A read gives the `run` bits. |

Other addresses read as 0. A write to another address has no effect.

These registers are the same for all cores: `SYNC_BYPASS_LO`, `SYNC_BYPASS_HI`, `ID`,
`CORE_SEL`, `RUN_ALL`, and `STATUS` bits [15:8] (the flags). All other registers go to the core
that `CORE_SEL` selects.

### Host execute
A write to `EXEC` executes the instruction 1 time, while the core is halted.

- The PC does not change, unless the instruction is a jump.
- The delay field has no effect.
- If the instruction stalls, it has only its side-set effect. Examples: a `PULL` with an empty TX
  FIFO, or a `WAIT` that is not met.

### Start procedure
1. Write `MEM_ADDR` with 0. Write the program to `MEM_DATA` in 1 burst.
2. Write `CLK_DIV`, `PIN_OUT`, `PIN_SET`, `PIN_SIDE`, `PIN_IN`, `SHIFT`, and `WRAP`.
3. Write `SYNC_BYPASS_LO` and `SYNC_BYPASS_HI`.
4. Write `CTRL` with 0b11 (`run` and `restart`).

`test/hostInterface.py` (`startProgram`) does these steps.

## Area budget

| Block | Estimated cells | Hardened cells |
|---|---|---|
| Core (Yosys, typical corner) | 5435 (69,647 µm²) | |
| Full design without the SRAM macro (Yosys, typical corner) | 5595 (76,927 µm²) | |
| SRAM macro | 1 (28,127 µm²) | |
| Total budget (8x4 tiles, 0.93 mm²) | 32K (approximate) | |

The current harden uses 4x2 tiles. In 2x2 tiles (131,620 µm²) the design uses approximately 80%
of the area, which is above the target of 60–70%. Select the final tile size in week 5.

## Timing budget
- Clock period: 20 ns (ADR-0007).
- Setup corner: slow, 1.08 V, 125 °C. Hold corner: fast, 1.32 V, −40 °C.
- The SDC clock uncertainty is 0.25 ns. STA uses it for setup and for hold.
- Critical paths: all of the worst setup paths start at the SRAM data output. The SRAM
  clock-to-data-out delay is 5.3 ns at the slow corner in the routed design.
- SPI MISO at 12 MHz with `syncBypass`: the MISO data must arrive within 2 cycles (41.7 ns at
  48 MHz) after the SCK falling edge (`docs/isa.md`, decision 4).

### Routed results
The source is the harden of `da32192` (run 42773958557). `docs/area_log.md` has the history.

| Item | Value |
|---|---|
| Setup worst slack, slow corner | +3.167 ns |
| Setup worst slack, typical corner | +8.77 ns |
| Hold worst slack, fast corner | +0.146 ns |
| Slow-corner frequency limit | Approximately 59 MHz |

| Register group | Setup slack, slow corner |
|---|---|
| `uio_oe` (`pinDir` 0–7) | +3.167 ns |
| `uio_out` (`pinOut` 0–7) | +3.193 ns |
| `rxFifo.entries` | +3.265 ns |
| `uo_out` (`pinOut` 8–14) | +3.684 ns |
| `y` | +3.868 ns |
| SRAM `A_ADDR` | +3.988 ns |
| `pc` | +4.024 ns |

### Configuration for timing
`src/config.json` sets these values (ADR-0008):

- Timing-driven placement (`PL_TIMING_DRIVEN`).
- Timing repair and design repair after global routing.
- Resizer setup margin: 3 ns at placement, 6 ns after global routing.
- Resizer hold margin: 0.1 ns at placement, 0.15 ns after global routing.

CAUTION: Do not set `GRT_RESIZER_SETUP_SLACK_MARGIN` below 6 ns. Detailed routing removes
approximately 3 ns of the setup slack that the resizer sees after global routing.

### RTL rules for timing
- OUT, MOV, and SET use 1 shared pin write rotator in `src/core.v`.
- ADD and SUB use 1 parallel-prefix adder (`prefixAdd`).
- The FIFO write enable of the entries comes from `full` only, not from the push decision.

NOTE: The FIFO write enable rule makes the path from `writePtr` to the entries short. This path
was the worst hold path before the hold margin increased to 0.15 ns.
