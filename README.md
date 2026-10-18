# Protocol Emulator ASIC

This project is a small, programmable I/O processor. Its instruction set
controls pins, reads pins, and counts clock cycles. Firmware uses these
operations to emulate real protocols after fabrication. The target protocols
are UART, SPI, and I2C, with optional stretch protocols.

Target: the Jane Street protocol emulator ASIC competition.
Flow: the Tiny Tapeout `ttihp-verilog-template` (IHP 130 nm, 8×4 tiles).
Deadline: **2027-01-18**.

Design references: RP2040 PIO state machines and TI PRU cores.

## Layout

| Path | Contents |
|---|---|
| `docs/PLAN.md` | Implementation plan, milestones, and schedule |
| `docs/architecture.md` | Block diagram, microarchitecture, and area and timing budgets |
| `docs/isa.md` | Instruction set specification |
| `docs/verification_plan.md` | Verification strategy, coverage goals, and test list |
| `docs/decisions/` | Architecture decision records (one file for each decision) |
| `docs/notes/` | Research notes (PIO, PRU, protocol timing, tools) |
| `info.yaml` | Tiny Tapeout project metadata and pinout |
| `.github/workflows/` | Tiny Tapeout CI: tests, docs, and GDS hardening |
| `src/` | Synthesizable RTL (Tiny Tapeout convention) |
| `test/` | cocotb testbenches (Tiny Tapeout convention) |
| `formal/` | SymbiYosys properties and `.sby` jobs |
| `sw/iss/` | Python instruction-set simulator (the reference model) |
| `sw/asm/` | Assembler and example firmware programs |
| `scripts/` | Flow scripts (synthesis reports, area records) |
| `learning/` | Practice designs (HDLBits, first UART). These are not part of the chip. |

## Status

Current milestone: M0 (tools and first flow run). Refer to `docs/PLAN.md`.
