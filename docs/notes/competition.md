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
- The 6x4 die is 1289.28 µm × 710.64 µm = 0.916 mm² (tt-support-tools, branch
  `ihp-sg13cmos5l`, `tech/ihp-sg13cmos5l/tile_sizes.yaml`). The 0.7 mm² value in the post is
  the nominal tile area. Use 0.7 mm² for the budget, because it is the more conservative value.
- The Tiny Tapeout tools already have an 8x4 size (commit `d66cf17`). The rules still allow only
  6x4.

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

## SRAM macro in the CMOS5L flow

Date of research: 2026-10-25. Answer: **yes, with high confidence (approximately 90%)**. A CMOS5L
project can use an IHP SRAM macro. Public CMOS5L projects pass all CI jobs with a macro. No
CMOS5L chip with an SRAM macro is fabricated yet.

### Evidence

| Finding | Source |
|---|---|
| `ahan17x/keyer` is a 6x4 CMOS5L design with `RM_IHPSG13_1P_256x16_c2_bm_bist`. Its `gds`, `precheck`, `gl_test`, and `viewer` jobs pass. | [ahan17x/keyer](https://github.com/ahan17x/keyer) |
| Other CMOS5L projects with a macro also pass all CI jobs: 512 × 16, 1024 × 8, and 256 × 16 (2x2 tiles). | [tt_um_loom](https://github.com/thomasgilbert481/tt_um_loom), [WilliamZhang20/protocol-emulator](https://github.com/WilliamZhang20/protocol-emulator), [2AMLogic/sg13cmos5l-protocol-emulator](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator) |
| The CMOS5L precheck allows the `SRAM.drawing` and `DigiBnd.drawing` layers. It forbids TopMetal1. The change was merged on 2026-09-17. | [tt-support-tools PR #187](https://github.com/TinyTapeout/tt-support-tools/pull/187) |
| The CMOS5L KLayout DRC deck reports 0 violations on a macro GDS. This is a user report. | [tt-support-tools issue #190](https://github.com/TinyTapeout/tt-support-tools/issues/190) |
| The Tiny Tapeout flow merges `src/config.json` and does not overwrite `MACROS`, `PDN_MACRO_CONNECTIONS`, or `PDN_CFG`. | tt-support-tools, branch `ihp-sg13cmos5l`, `project.py` |
| The SG13G2 1024 × 8 macro works in silicon (shuttle ttihp0p2). | [Chip page](https://www.tinytapeout.com/chips/ttihp0p2/tt_um_urish_sram_test), [memory specs](https://tinytapeout.com/specs/memory/) |
| The Jane Street post recommends SRAM for instruction memory. | [Jane Street post](https://blog.janestreet.com/protocol-emulator-asic-competition/) |

NOTE: At least 4 of the projects above are other entries in this competition. The judges score
"unique functionality". Thus, SRAM program memory alone does not make this design different.

### Integration summary

1. Copy the macro files (`.gds`, `.lef`, `.cdl`, and the 3 `.lib` corners) into
   `macro/RM_IHPSG13_1P_256x16_c2_bm_bist/`. The PDK path is
   `ihp-sg13cmos5l/libs.ref/sg13cmos5l_sram/`, which is a symlink to the SG13G2 macros.
2. Add a Verilog module with only the macro ports as the `nl` entry. Do not add this file to
   `info.yaml`.
3. Add these keys to `src/config.json`:
   - `MACROS`, with a fixed instance location (x on a 0.48 µm grid, y on a 3.78 µm grid, and
     approximately 9 µm or more from the core edge),
   - `PDN_MACRO_CONNECTIONS`: `"<inst> VPWR VGND VDD! VSS!"` and
     `"<inst> VPWR VGND VDDARRAY! VSS!"`,
   - `PDN_CFG` (or `FP_PDN_CFG`) for a custom `pdn_cfg.tcl`,
   - `MAGIC_MACRO_STD_CELL_SOURCE`, `ERROR_ON_MAGIC_DRC` set to false, and
     `MAGIC_EXT_ABSTRACT_CELLS`.
4. Copy a working `pdn_cfg.tcl` from keyer or 2AMLogic. The macro power pins are on Metal4 only,
   and user designs cannot use TopMetal1. Thus, the default PDN does not connect the macro.
5. Simulate with the PDK behavioral model and `-DFUNCTIONAL`.
6. Tie the BIST ports to 0. Tie `A_DLY` to 1. Set `A_BM` to all ones for full-word writes.

Timing of the 256 × 16 macro: clock to data out is 3.02 ns (typical) and 5.06 ns (slow corner).
A read has 1 cycle of latency. This is acceptable at a 20 ns clock period.

### Risks

| Risk | Mitigation |
|---|---|
| No CMOS5L SRAM chip is fabricated yet. IHP gives no written guarantee for the SG13G2 macro in CMOS5L. | Keep a fallback: a smaller flip-flop memory (32–64 words), as in PIO. |
| The statement "macros are allowed" is second-hand. Only 2 competitor repos report it, from a Tiny Tapeout email on 2026-09-28. | Send the question below. |
| Magic DRC reports thousands of violations inside the foundry GDS. Projects disable the Magic DRC check. The KLayout precheck passes. | Get Tiny Tapeout approval for this waiver. |
| The LVS setup is different in each project. | Use the setup of a project that passes CI. |
| The PDN is fragile. With the default 50 µm stripe pitch, Metal4 stripes can short opposite nets. 2AMLogic uses `FP_PDN_VPITCH` 44.96 and `FP_PDN_VOFFSET` 93.985. | Integrate the macro with the M0 design before M2. |
| The flow tools use branch refs, and the branches can change. | Pin `tt-gds-action` to a commit. |

### Alternatives

| Memory | Area (µm²) | Source |
|---|---|---|
| 64 × 16 SRAM macro | 15,240 | PDK LEF |
| 256 × 16 flip-flops | 312,063–378,067 | 2AMLogic measurement |
| Latch array | not measured | |
| Boot ROM for fixed code, with the macro for writable code | not measured | |

### Question to send

Send this question to Tiny Tapeout (Discord) or asic-competition@janestreet.com before the
program memory ADR in week 2:

> We plan to use the IHP SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist` (from `sg13cmos5l_sram`,
> which links to `sg13g2_sram`) in a 6x4 project on the CMOS5L flow (`tt-gds-action@ihp-cmos5l`).
> The precheck allows the SRAM layers (tt-support-tools PR #187). Please confirm 3 points.
> (1) Is the macro accepted for the March 2027 CMOS5L shuttle, with Magic DRC waived and the
> macro as a black box for LVS? (2) Which `config.json` and `pdn_cfg.tcl` does the CMOS5L macro
> reference template use, and when is it public? (3) Does the competition accept 8x4, and does
> the macro change the cell count or tile rules?
