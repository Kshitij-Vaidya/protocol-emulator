# Competition Rules

Source: [Jane Street, "Protocol emulator ASIC competition"](https://blog.janestreet.com/protocol-emulator-asic-competition/).
Date of check: 2026-10-18. The post has no separate rules page or FAQ. Check the post again
before each milestone, because Jane Street can change the rules.

## Rules

| Item | Rule (quoted from the post) |
|---|---|
| Area | "The current maximum area is 6x4 tiles per design." |
| Possible area increase | "We are working on the possibility of scaling up to 8x4 tiles (~30% more area)." |
| Area estimate | 24 tiles is approximately 0.7 mm² of nominal tile area, with about 1K logic cells for each tile. |
| `info.yaml` | "Set the tile size in `info.yaml` to 6x4." |
| Process | "We're targeting IHP's 130nm CMOS5L process through our friends at Tiny Tapeout." |
| Template | "Start with the CMOS5L Verilog template" ([`ttihp-verilog-template`, branch `cmos5l`](https://github.com/TinyTapeout/ttihp-verilog-template/tree/cmos5l)) |
| Deadline | "Submit your design by January 18th, 2027." |
| Submission | "We'll add a final submission form to this page closer to the deadline!" |
| Shuttle | "We're targeting the March 2027 CMOS5L shuttle, subject to the foundry schedule." |
| Open source | "Your submission should be open source so others can use and build on it." |
| Working in public | "there's no need to keep your work hidden until the deadline" |
| Teams | "we strongly recommend working in teams." |
| Judging | Projects with "unique functionality", and "novel approaches to design and verification methodologies" |
| Prize | "We'll pay to tape out the most novel designs on a Tiny Tapeout shuttle." |
| Questions | asic-competition@janestreet.com |

## Differences from the roadmap

The roadmap (`../../../asic_design_roadmap.md`) uses 8×4 tiles (32 tiles, approximately 32K cells,
1 mm²). The current rules allow **6x4 tiles (24 tiles, approximately 24K cells, 0.7 mm²)**.

- Use 6x4 as the budget. Treat 8x4 as a possible increase, not as a plan.
- The template `info.yaml` lists 1x1 to 8x2 as valid sizes. The rules require 6x4. Thus, the
  Tiny Tapeout flow for this competition supports sizes that the template comment does not list.
- Set `tiles: "6x4"` in `info.yaml` at M2, when the core RTL replaces the M0 design.

## Area budget check from the M0 result

The M0 UART transmitter (run 39120908387) has 246 standard cells in 3470.95 µm². This is
14.1 µm² for each cell on average. At this average, 24K cells use approximately 0.34 mm², which
is approximately 50% of 0.7 mm². This agrees with the default placement density
(`PL_TARGET_DENSITY_PCT` = 60).

## Program memory: area estimates

Program memory is probably the largest block. These estimates use cell areas from
`sg13cmos5l_stdcell.lef` at PDK version `2bbec755`. They include only cell area, not routing.

| Cell | Area (µm²) |
|---|---|
| `sg13cmos5l_dfrbpq_1` (flip-flop) | 48.99 |
| `sg13cmos5l_dlhq_1` (latch) | 30.84 |
| `sg13cmos5l_mux2_1` | 18.14 |

| Memory | Storage | Read multiplexer | Total (µm²) | Part of 0.7 mm² |
|---|---|---|---|---|
| 32 × 16 bit, flip-flops (PIO size) | 512 × 48.99 = 25,083 | 496 × 18.14 = 8,997 | 34,080 | 5% |
| 256 × 16 bit, flip-flops | 4,096 × 48.99 = 200,663 | 4,080 × 18.14 = 74,011 | 274,674 | 39% |
| 256 × 16 bit, latches | 4,096 × 30.84 = 126,321 | 4,080 × 18.14 = 74,011 | 200,332 | 29% |
| 256 × 16 bit, SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist` | 236.8 µm × 118.78 µm | included | 28,127 | 4% |

NOTE: A read multiplexer for N words of W bits needs (N − 1) × W `mux2` cells.

Conclusions:

1. A flip-flop memory of 256 words uses approximately 40% of the area before routing. This is
   probably too large.
2. The PIO limit of 32 instructions is probably an area decision. Examine this in `pio.md`.
3. An SRAM macro is 7–10 times smaller than flip-flops or latches for the same size.

## SRAM macro: open questions

- The CMOS5L PDK directory `ihp-sg13cmos5l/libs.ref/sg13cmos5l_sram` is a symlink to
  `ihp-sg13g2/libs.ref/sg13g2_sram`. The CMOS5L metal stack is Metal1–Metal4 and TopMetal1. The
  SRAM macro LEF files use only Metal1–Metal4.
- The Jane Street post links the Tiny Tapeout SRAM test
  ([`tt_um_urish_sram_test`](https://www.tinytapeout.com/chips/ttihp0p2/tt_um_urish_sram_test),
  1024 × 8 bit). That project uses the `ihp-sg13g2` PDK, not CMOS5L.
- It is not known if the Tiny Tapeout CMOS5L flow allows SRAM macros in a user project.

Action: ask Tiny Tapeout (Discord) or asic-competition@janestreet.com before the program memory
ADR in week 2. Question: "Can a 6x4 CMOS5L project use an IHP SRAM macro, for example
`RM_IHPSG13_1P_256x16_c2_bm_bist`, and is there an example flow configuration?"
