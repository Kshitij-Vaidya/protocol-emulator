# Implementation Plan

Date of plan: 2026-10-17. Deadline: 2027-01-18. Time available: **13 weeks**.
Internal submission target: **2027-01-11**. This target gives 1 week of buffer.

The roadmap (`../asic_design_roadmap.md`) gives phases 0–6 a duration of
4–5 months. This plan has 3 months. Thus, each learning exercise also makes
a part of the project:

- The first UART transmitter is the design for the first flow run.
- The protocol RTL from the learning exercises becomes reference models for
  the testbenches.

Terms:

- **Harden**: run the Tiny Tapeout flow from RTL to GDS.
- **ISS**: the cycle-accurate Python instruction-set simulator in `sw/iss/`.
- **Lockstep test**: a test that runs one program on the RTL and on the ISS,
  and compares the two results on each clock cycle.

---

## Guiding principles

1. **Make the model before the RTL.** Write real UART, SPI, and I2C firmware
   for the ISS before the core RTL exists. This firmware checks the ISA. The
   ISS then becomes the reference model for verification.
2. **Run the full flow early and frequently.** A design must reach GDS in
   week 1. From week 5, harden the real design each week. This schedule finds
   area and timing problems in November, not in January.
3. **Verification is a deliverable.** The judges score it. Each RTL block
   must have tests when it goes into `src/`. Formal checks, constrained-random
   tests, and coverage grow together with the RTL.
4. **Record each decision.** Write a short ADR in `docs/decisions/` for each
   important decision. These records also become part of the competition
   report.
5. **The feature freeze is mandatory.** After 2026-12-20, make only bug fixes
   and timing fixes.

---

## Milestones

| # | Milestone | Target date | Exit criteria |
|---|---|---|---|
| M0 | Tools and first flow run | 2026-10-25 | The UART transmitter in `src/` passes a self-checking cocotb test. It hardens to GDS with the ttihp template workflows in GitHub Actions. |
| M1 | Architecture and ISA v0.1 | 2026-11-08 | First versions of `architecture.md` and `isa.md` exist. The ISS and assembler run UART TX, UART RX, and SPI master firmware against Python protocol models. |
| M2 | Core RTL v1 | 2026-11-22 | The RTL core executes ISA v0.1. Lockstep tests pass on directed programs. The real design hardens, and an area report exists. |
| M3 | Verification infrastructure | 2026-11-29 | A constrained-random program generator, lockstep tests, functional coverage, and first formal proofs exist. UART and SPI firmware pass against cocotbext models. |
| M4 | I2C and physical-design check | 2026-12-06 | I2C operates (open-drain, clock stretch). The design meets the target clock in STA. It fits in 6x4 tiles with routing margin. |
| M5 | Feature complete (**freeze**) | 2026-12-20 | The selected stretch protocols operate. The host interface and program-load interface are final. ISA v1.0 is frozen. |
| M6 | Verification closure | 2027-01-03 | Coverage goals are met. Formal properties are proven. Gate-level simulations pass. All bugs are fixed or have a triage decision. |
| M7 | Ready for tapeout | 2027-01-10 | The official flow makes a clean GDS. `info.yaml` and the documentation are complete. Demo firmware and a README exist. |
| M8 | Submit | 2027-01-11 → 18 | The design is submitted with buffer time. The report is published. |

---

## Week-by-week schedule

### Week 1 (Oct 19–25): M0, tools and first flow run
- Install the missing tools:
  - `cocotb`, `cocotbext-uart`, and `cocotbext-spi`.
  - SymbiYosys (`sby`) and a solver (`yices` or `boolector`).
  - Surfer, or use GTKWave (already installed).
- Record the tool versions in `requirements.txt`.
- Clone `ttihp-verilog-template`. Read its `info.yaml`, `src/`, `test/`, and
  GitHub Actions files.
- Harden in GitHub Actions with the template workflows. Add local hardening
  (LibreLane in Docker) as a second path before M2. Docker is already
  installed.
- Write a UART transmitter in `src/uartTx.v` with a self-checking cocotb test
  in `test/testUartTx.py`. The Tiny Tapeout flow reads RTL only from `src/`.
  The core RTL replaces this design in M2.
- Harden the UART transmitter with the template flow. Record the cell count
  and the timing results.
- Read chapter 3 (PIO) of the RP2040 datasheet. Read the TI PRU reference
  guide. Write the notes in `docs/notes/pio.md` and `docs/notes/pru.md`.
- Additional practice: complete 30 HDLBits problems.

### Week 2 (Oct 26–Nov 1): requirements and architecture study
- Write `docs/notes/protocols.md`. For each target protocol, record:
  - the bit rates and the timing tolerances,
  - the pin types (push-pull or open-drain),
  - the operations that the core must perform for each bit.
- Use this table to calculate the required clock frequency and timing
  resolution. Do not estimate these values without the table.
- Compare PIO and PRU. Record the strong and weak points of each for a
  1 mm² budget.
- Make the main architecture decisions (refer to *Open decisions*). Write an
  ADR for each decision.
- Make area budget v0. Estimate the cells for each block against the total
  of 24K cells (6x4 tiles, refer to `docs/notes/competition.md`). Keep a
  margin: the target utilization is 60–70% or less.
- Write UART RX and SPI master as plain RTL in `learning/`. These designs are
  HDL practice. They also become reference models.

### Week 3 (Nov 2–8): M1, ISA v0.1, ISS, and assembler
- Write the first version of `docs/isa.md`. Include these items:
  - instruction encoding and registers,
  - pin operations and parallel pin updates (as in PIO side-set),
  - wait and delay rules,
  - branches,
  - FIFO and host-interface operations.
- Write the cycle-accurate ISS in `sw/iss/`. The ISS must show the exact clock
  cycle of each pin change, because timing is the purpose of the design.
- Write a small assembler in `sw/asm/` (Python) with labels and pseudo-ops.
- Write firmware for UART TX, UART RX, and SPI master (mode 0). Run the
  firmware in the ISS against Python protocol models.
- Change the ISA until these programs are short and have exact timing.
  Then freeze ISA v0.1.

### Weeks 4–5 (Nov 9–22): M2, core RTL v1
- Write these blocks:
  - program memory and program-load path,
  - fetch and decode,
  - execute, with a minimal ALU,
  - pin I/O unit (output, output enable, input synchronizers),
  - delay counter and cycle counter,
  - host interface (FIFO or register window on the Tiny Tapeout pins).
- Write a cocotb unit test for each block together with the block.
- Write the lockstep test harness. It compares pin traces and architectural
  state on each cycle.
- At the end of week 5, set `tiles: "6x4"` in `info.yaml`, and harden the real
  design. From this point, record the cell count each week in
  `docs/area_log.md`.

### Week 6 (Nov 23–29): M3, verification infrastructure
- Write a constrained-random program generator. Run its programs in the
  lockstep test.
- Add functional coverage for these items:
  - opcodes and operand corner values,
  - branches taken and not taken,
  - FIFO full and FIFO empty,
  - pin-direction changes.
- Write SymbiYosys properties for the decoder, the FIFO, the delay counter,
  and the PC and control invariants. Start with BMC. Use k-induction where
  possible.
- Run the UART and SPI firmware on the RTL against `cocotbext-uart` and
  `cocotbext-spi`.

### Week 7 (Nov 30–Dec 6): M4, I2C and physical check
- Write I2C master firmware. Use output enable for open-drain operation.
  Support clock stretch, ACK, and NACK.
- Test the I2C firmware against an I2C target model.
- Run STA at the target clock. Fix the critical paths.
- Check that the placement density and routing density have margin. A fit
  after synthesis is not sufficient.

### Weeks 8–9 (Dec 7–20): M5, stretch features and **feature freeze**
- Select 1–3 stretch protocols. Use the area and timing margin from week 7
  to make this selection.
- The probable order of difficulty is:
  1. PS/2
  2. WS2812
  3. JTAG and SWD
  4. low-speed USB
  5. 10 Mbit Ethernet
- Low-speed USB and 10 Mbit Ethernet probably need a higher clock frequency
  than the process and tile budget allow. Use the week 7 data to decide.
- Add a second core or state machine if the area budget allows it.
- On 2026-12-20, freeze ISA v1.0 and the pinout.

### Weeks 10–11 (Dec 21–Jan 3): M6, verification closure
- Meet the coverage goals. Complete the formal proofs. Fix the bugs.
- Run the cocotb test suite on the hardened gate-level netlist.
- Test on an FPGA if a board is available. This step is optional but has
  high value.

### Week 12 (Jan 4–10): M7, ready for tapeout
- Harden the final design from a clean checkout. All template CI checks must
  pass.
- Complete `info.yaml` and `docs/info.md` (the Tiny Tapeout datasheet page).
- Write the pinout, the demo programs, and a programming guide.

### Week 13 (Jan 11–18): M8, submission and buffer
- Submit at the start of the week.
- Use the remaining time for the report and for cleanup.

---

## Open decisions

Write an ADR for each decision.

| Decision | Options | Decide by | Notes |
|---|---|---|---|
| HDL | Verilog-2005, SystemVerilog subset, Hardcaml, Amaranth | Week 1 | Proposal: synthesizable Verilog with SV assertions for formal. The template and the tools expect Verilog. Refer to ADR-0001. |
| Program memory | Flip-flops, latches, or an SRAM macro (if IHP has one for Tiny Tapeout) | Week 2 | This is probably the largest area cost. Calculate the size from the firmware requirements. |
| Program-load path | Serial load on the Tiny Tapeout inputs, SPI flash, or host writes on `uio` | Week 2 | The path must be simple and reliable. It must be possible to test it after fabrication. |
| Number of cores | 1 core, N small state machines (as in PIO), or 1 core with helper units | Week 2 | The area budget controls this decision. Start with 1 core. Keep the design compatible with N cores. |
| Clock target | Calculated from the protocol table and the STA results on IHP | Week 2; check again in week 7 | |
| Timing model | 1 cycle for each instruction (as in PIO), or variable timing with a delay field | Week 3 | Deterministic single-cycle execution makes firmware timing easy to analyze. |
| Host interface | TX and RX FIFOs (as in PIO), register window, or mailbox | Week 3 | An external MCU or the Tiny Tapeout demo board uses this interface. |
| Stretch protocols | Refer to week 8 | Week 7 | Decide from the STA data. |

---

## Risks

| Risk | Mitigation |
|---|---|
| The learning curve uses too much of the schedule. | Each learning exercise is also a deliverable. M0 requires a full flow run in week 1. |
| The program memory is too large for 24 tiles (6x4). | Ask about SRAM macros before week 2. Calculate its size in week 2 from real ISS firmware. Record the hardened area each week from week 5. |
| Timing closure occurs too late. | Harden each week from week 5. Keep the fetch → decode → pin path short. |
| The flow or a tool fails near the deadline. | Record exact tool versions. Keep two independent flow paths: GitHub Actions and local Docker. |
| ISA changes cause RTL rework. | Use the ISS first. Freeze the ISA at v0.1 (week 3) and at v1.0 (2026-12-20). |
| The judges score the verification as weak. | Formal checks, constrained-random tests, and coverage are milestones in the schedule. |

---

## Weekly routine

- Monday: read the plan. Update the status in the milestone table.
- Each day: make small commits. Add tests together with each block.
- Friday: harden the design (from week 5). Record the area and timing in
  `docs/area_log.md`. Write new information in `docs/notes/`.
