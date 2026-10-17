# Verification Plan

Status: first outline. The infrastructure is due at M3 (2026-11-29). Closure is due at M6.

## Strategy
| Method | Scope | Tool |
|---|---|---|
| Directed unit tests | Each RTL block | cocotb with Icarus or Verilator |
| Lockstep tests against the reference model | The full core against the Python ISS, on each cycle | cocotb and `sw/iss` |
| Constrained-random tests | Random programs and random host traffic | cocotb |
| Functional coverage | Opcodes, operand corner values, FIFO states, pin-direction changes | cocotb-coverage, or a custom tool |
| Formal (BMC and k-induction) | Decoder, FIFO, delay counter, control invariants | SymbiYosys |
| Protocol compliance | UART, SPI, and I2C firmware against bus models | cocotbext-uart, cocotbext-spi, an I2C model |
| Gate-level simulation | The cocotb suite on the hardened netlist | Icarus with the IHP cell models |

## Coverage goals
<!-- Complete at M3. -->

## Test list
| Test | Block | Status |
|---|---|---|
