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

## Answers from Jane Street

Jane Street replied to our question by email in 2 parts. The replies were received before
2026-11-07. The answers replace the post where they are different.

| Item | Answer |
|---|---|
| Tile size | "8x4 is confirmed for the March shuttle." |
| Tile rules | "The macro doesn't change the tile rules, and there's no separate cell count limit. Everything just needs to fit in your tiles and pass precheck." |
| SRAM macro | "Tiny Tapeout says the macro should be OK for the March shuttle, with Magic DRC waived and the macro as a black box for LVS." |
| Reference config | Tiny Tapeout published an example CMOS5L project with an SRAM macro: [`TinyTapeout/ttihp-cmos5l-sram-example`](https://github.com/TinyTapeout/ttihp-cmos5l-sram-example). |
| Silicon status | "It isn't silicon proven yet, so keep an eye on the repo for updates." |
| Other reference | Ken Pettit's walkthrough for an IHP SRAM macro in a CMOS5L tile, with the LibreLane config and the Metal4 power: [`ihp_sram_macro.html`](https://kdp1965.github.io/ihp-um-janestreet-prism/ihp_sram_macro.html). |

## Area budget

The maximum tile size is now **8x4 (32 tiles)**.

| Item | 6x4 | 8x4 |
|---|---|---|
| Die (tt-support-tools `tile_sizes.yaml`) | 1289.28 µm × 710.64 µm = 0.916 mm² | 1724.16 µm × 710.64 µm = 1.225 mm² |
| Nominal tile area | 0.7 mm² (post) | 0.93 mm² (0.7 mm² × 32 / 24) |
| Approximate logic cells | 24K | 32K |

- Use the 8x4 nominal tile area (0.93 mm²) for the budget. It is more conservative than the die
  area.
- No cell count limit applies. The design must fit in the tiles and pass the precheck.
- Select the tile size at the end of week 5 from the hardened area. Use the smallest size that
  meets the target utilization (60–70% or less).
- The roadmap (`../../../asic_design_roadmap.md`) also uses 8×4. Thus, the roadmap budget is
  correct again.

## Area budget check from the M0 result

The M0 UART transmitter (run 39120908387) has 246 standard cells in 3470.95 µm². This is
14.1 µm² for each cell on average. At this average, 32K cells use approximately 0.45 mm², which
is approximately 48% of 0.93 mm². This agrees with the default placement density
(`PL_TARGET_DENSITY_PCT` = 60).

## Program memory: area estimates

Program memory is probably the largest block. These estimates use cell areas from
`sg13cmos5l_stdcell.lef` at PDK version `2bbec755`. They include only cell area, not routing.

| Cell | Area (µm²) |
|---|---|
| `sg13cmos5l_dfrbpq_1` (flip-flop) | 48.99 |
| `sg13cmos5l_dlhq_1` (latch) | 30.84 |
| `sg13cmos5l_mux2_1` | 18.14 |

| Memory | Storage | Read multiplexer | Total (µm²) | Part of 0.93 mm² |
|---|---|---|---|---|
| 32 × 16 bit, flip-flops (PIO size) | 512 × 48.99 = 25,083 | 496 × 18.14 = 8,997 | 34,080 | 4% |
| 64 × 16 bit, flip-flops | 1,024 × 48.99 = 50,166 | 1,008 × 18.14 = 18,285 | 68,451 | 7% |
| 256 × 16 bit, flip-flops | 4,096 × 48.99 = 200,663 | 4,080 × 18.14 = 74,011 | 274,674 | 29% |
| 256 × 16 bit, latches | 4,096 × 30.84 = 126,321 | 4,080 × 18.14 = 74,011 | 200,332 | 21% |
| 256 × 16 bit, SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist` | 236.8 µm × 118.78 µm | included | 28,127 | 3% |

NOTE: A read multiplexer for N words of W bits needs (N − 1) × W `mux2` cells.

Conclusions:

1. A flip-flop memory of 256 words uses approximately 30% of the area before routing. This is
   probably too large.
2. The PIO limit of 32 instructions is probably an area decision. Examine this in `pio.md`.
3. An SRAM macro is 7–10 times smaller than flip-flops or latches for the same size.

## SRAM macro in the CMOS5L flow

Answer: **yes**. Tiny Tapeout accepts the macro for the March 2027 shuttle, with Magic DRC waived
and the macro as a black box for LVS (refer to *Answers from Jane Street*). No CMOS5L chip with
an SRAM macro is fabricated yet.

### Evidence

| Finding | Source |
|---|---|
| Tiny Tapeout accepts the macro for the March shuttle. | Jane Street email |
| The Tiny Tapeout example uses `RM_IHPSG13_1P_256x16_c2_bm_bist` in a 2x2 CMOS5L tile. Its `gds`, `test`, and `docs` workflows pass at commit `15ac9bc` (2026-11-05). | [ttihp-cmos5l-sram-example](https://github.com/TinyTapeout/ttihp-cmos5l-sram-example) |
| `ahan17x/keyer` is a 6x4 CMOS5L design with the same macro. Its `gds`, `precheck`, `gl_test`, and `viewer` jobs pass. | [ahan17x/keyer](https://github.com/ahan17x/keyer) |
| Other CMOS5L projects with a macro also pass all CI jobs: 512 × 16, 1024 × 8, and 256 × 16 (2x2 tiles). | [tt_um_loom](https://github.com/thomasgilbert481/tt_um_loom), [WilliamZhang20/protocol-emulator](https://github.com/WilliamZhang20/protocol-emulator), [2AMLogic/sg13cmos5l-protocol-emulator](https://github.com/2AMLogic/sg13cmos5l-protocol-emulator) |
| The CMOS5L precheck allows the `SRAM.drawing` and `DigiBnd.drawing` layers. It forbids TopMetal1. | [tt-support-tools PR #187](https://github.com/TinyTapeout/tt-support-tools/pull/187) |
| The SG13G2 1024 × 8 macro works in silicon (shuttle ttihp0p2). | [Chip page](https://www.tinytapeout.com/chips/ttihp0p2/tt_um_urish_sram_test), [memory specs](https://tinytapeout.com/specs/memory/) |

NOTE: At least 4 of the projects above are other entries in this competition. The judges score
"unique functionality". Thus, SRAM program memory alone does not make this design different.

### Integration procedure

Use the Tiny Tapeout example as the reference. Its README section "Using this in your own design"
is the full procedure. This summary replaces the earlier summary from the competitor projects.

1. Copy these files from the example:
   - `librelane_plugin_sram_pdn.py` and `odb_stripes.py` to the repository root,
   - `src/pdn_cfg.tcl` and `src/sram_bb.v` to `src/`,
   - `test/sram_model/` to `test/`.
2. Add `sram_bb.v` to `source_files` in `info.yaml` and to `PROJECT_SOURCES` in `test/Makefile`.
3. Copy the "IHP SRAM macro" section of the example `src/config.json`, from `meta` to
   `ERROR_ON_ILLEGAL_OVERLAPS`. This section has these keys:
   - `meta.substituting_steps`, which adds the `Project.ExtendPowerStripes` step after
     `OpenROAD.GeneratePDN`,
   - `MACROS`, with the views from `pdk_dir::libs.ref/sg13cmos5l_sram/`,
   - `PDN_MACRO_CONNECTIONS`: `"<inst> VPWR VGND VDD! VSS!"` and
     `"<inst> VPWR VGND VDDARRAY! VSS!"`,
   - `PDN_CFG`, `EXTEND_STRIPES_SRAM_ARRAY_EVERY_OTHER`, `ERROR_ON_PDN_VIOLATIONS` 0,
     `RUN_MAGIC_DRC` 0, and `ERROR_ON_ILLEGAL_OVERLAPS` 0.
4. Copy the PDN stripe values: `FP_PDN_VPITCH` 44.96, `FP_PDN_VWIDTH` 2.1, `FP_PDN_VSPACING`
   3.52, and `FP_PDN_VOFFSET` 6.15. These values align the Metal4 stripes with the macro power
   columns.
5. Place the macro with orientation `N` or `FS`, with its pins toward the logic. Use
   x = 3.36 + n × 11.24 µm.
6. Tie `A_DLY` to 1. Tie the BIST ports to 0. Drive the macro inputs from registers.
7. For simulation, copy the `SRAM_MODEL` and `COMPILE_ARGS` lines of the example `test/Makefile`.
8. After hardening, check these 3 items:
   - The `*-project-extendpowerstripes` step log lists the stripes on the macro.
   - LVS matches.
   - The IR drop report (`runs/wokwi/*-openroad-irdropreport/irdrop.rpt`) says that all shapes
     on VPWR and VGND are connected.

NOTE: The earlier summary said "do not add the black-box file to `info.yaml`". The Tiny Tapeout
example adds it. Use the example.

CAUTION: The example uses `TinyTapeout/tt-gds-action@ttihp27a` (a tag, LibreLane 3.1.0.dev4). This
project uses `@ihp-cmos5l` (a branch, LibreLane 3.1.0.dev3). Change the CI to `@ttihp27a` before
the macro test, so that the flow is the same as the example.

Timing of the 256 × 16 macro: clock to data out is 3.02 ns (typical) and 5.06 ns (slow corner).
A read has 1 cycle of latency. This is acceptable at a 20 ns clock period.

### Risks

| Risk | Mitigation |
|---|---|
| No CMOS5L SRAM chip is fabricated yet. The power scheme of the example is experimental. | Keep a fallback memory behind the same interface (refer to *Alternatives*). Watch the example repo for updates. |
| The PDN is fragile. The macro power connection depends on the stripe alignment and on the `ExtendPowerStripes` step. | Integrate the macro with the M0 design before M2. Do the 3 checks in step 8 after each harden. |
| The flow tools can change. | Use the `ttihp27a` tag. Record the example commit that the copied files come from. |

### Alternatives

| Memory | Area (µm²) | Source |
|---|---|---|
| 64 × 16 SRAM macro | 15,240 | PDK LEF |
| 32 × 16 flip-flops | 34,080 | Calculation above |
| 64 × 16 flip-flops | 68,451 | Calculation above |
| 256 × 16 latches | 200,332 | Calculation above |
| 256 × 16 flip-flops | 312,063–378,067 | 2AMLogic measurement |
| Boot ROM for fixed code, with the macro for writable code | not measured | |

### Question sent

This question was sent to asic-competition@janestreet.com. The answers are in *Answers from Jane
Street*.

> We plan to use the IHP SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist` (from `sg13cmos5l_sram`,
> which links to `sg13g2_sram`) in a 6x4 project on the CMOS5L flow (`tt-gds-action@ihp-cmos5l`).
> The precheck allows the SRAM layers (tt-support-tools PR #187). Please confirm 3 points.
> (1) Is the macro accepted for the March 2027 CMOS5L shuttle, with Magic DRC waived and the
> macro as a black box for LVS? (2) Which `config.json` and `pdn_cfg.tcl` does the CMOS5L macro
> reference template use, and when is it public? (3) Does the competition accept 8x4, and does
> the macro change the cell count or tile rules?
