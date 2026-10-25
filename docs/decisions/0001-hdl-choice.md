# ADR-0001: HDL choice

Status: **Accepted** (2026-10-25)

## Context
The Tiny Tapeout `ttihp-verilog-template` and its CI expect Verilog. The
simulators (Icarus, Verilator) read Verilog directly. Synthesis (Yosys) and
the formal tool (SymbiYosys) also read Verilog directly. Jane Street uses
Hardcaml internally. The competition allows all HDLs.

## Options
1. Synthesizable Verilog-2005, with SystemVerilog assertions for formal only
2. The synthesizable subset of SystemVerilog (Yosys and Icarus support only
   part of it)
3. Hardcaml, which generates Verilog
4. Amaranth, which generates Verilog

## Decision
Use option 1. It has the lowest tool risk for a 13-week schedule. It also has
the most learning material. Consider Hardcaml again after M5 only if time is
available.

The M0 design checks this decision. The `uartTx` RTL in Verilog-2005 passes
the cocotb tests in Icarus and Verilator. It also passes all Tiny Tapeout CI
jobs: `gds`, `precheck`, `gl_test`, and `viewer`.

## Consequences
- The testbenches are in Python (cocotb). Thus, the HDL choice does not limit
  the verification methods.
- The design files in `src/` must use only Verilog-2005.
- SystemVerilog assertions must be in `formal/`, not in `src/`.
