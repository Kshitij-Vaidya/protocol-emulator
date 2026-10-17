# ADR-0001: HDL choice

Status: **Proposed** (decide by the end of week 1)

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

## Proposal
Use option 1. It has the lowest tool risk for a 13-week schedule. It also has
the most learning material. Consider Hardcaml again after M5 only if time is
available.

## Consequences
- The testbenches are in Python (cocotb). Thus, the HDL choice does not limit
  the verification methods.
