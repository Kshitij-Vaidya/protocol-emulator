# Instruction set simulator

The ISS executes programs from the assembler, 1 core clock cycle at a time. It shows the exact
cycle of each pin change. The ISA is in `docs/isa.md`. This file gives the timing rules that the
ISA does not give. The core RTL must obey the same rules, because the lockstep tests in M2
compare the RTL with the ISS.

## Use

```python
from asm.assembler import assemble
from iss.core import CoreConfig
from iss.machine import Machine

machine = Machine([(assemble(source), CoreConfig(clkDiv=104, outBase=8, outCount=1))])
machine.run(cycles, environment)
```

`environment(cycle, outputs)` returns the input levels for that cycle. `outputs` holds the pin
levels during that cycle. The host interface is `Core.hostWrite()` and `Core.hostRead()`.

Run the tests from the repository root:

```sh
pytest
```

## Timing rules

1. Cycle 0 is the first cycle after the core starts.
2. The core has a tick on cycles 0, `clkDiv`, 2 × `clkDiv`, and so on.
3. An instruction that executes on cycle c changes its output pins on cycle c + 1.
4. On cycle c, the core reads the inputs of cycle c − 2. For each pin with its `syncBypass` bit
   set, the core reads the input of cycle c.
5. At the start, the synchronizer holds the first input value. This models a start after the
   program load (ADR-0006).
6. A `WAIT` with a timeout that ends by timeout takes `T` + 1 ticks.
7. An instruction from `OUT EXEC` or `MOV EXEC` executes on the next tick. The PC does not change,
   unless the instruction is a jump. The delay of the `OUT EXEC` or `MOV EXEC` instruction is
   ignored.
8. A flag change by any core is visible to all cores on the next cycle (ADR-0010). If 1 core
   sets a flag and another core clears it on the same cycle, the set wins.
9. The output levels of the cores are combined with OR, and the output enables are combined
   with OR. A core must keep the output level 0 on each pin that another core drives.
10. A host write or read of a FIFO on cycle c takes effect at the end of cycle c. The core sees
    the FIFO state from before the host access on cycle c.

## Protocol models

`iss/models.py` has these models:

| Model | Function |
|---|---|
| `PinRecorder` | Records each level change of 1 output pin |
| `UartSource` | Makes a UART waveform, with a baud error and a bad stop bit if necessary |
| `decodeUart` | Decodes a recorded UART waveform. It samples each bit at its center. |
| `SpiTarget` | An SPI mode 0 target. It samples MOSI on the SCK rising edge and changes MISO on the falling edge. |
| `I2cTarget` | An I2C target with a 7-bit address. It acknowledges its address and each written byte, sends read bytes, and can stretch SCL after each ACK. |
| `i2cWrite`, `i2cRead`, `i2cResult` | Make the host words for `i2cController.pasm`, and decode its RX FIFO words |
| `Ps2Device` | A PS/2 device. It sends frames, receives host commands with an ACK, and can reply to a command. It can send a frame with a bad parity. |
| `ps2HostWord`, `ps2Result` | Make the host words for `ps2Host.pasm`, and decode and check its RX FIFO words |
| `JtagTap` | A JTAG TAP with the 16-state controller, a 4-bit IR, IDCODE, and BYPASS |
| `jtagWords`, `jtagShift`, `jtagTdoBits` | Make the host words for `jtag.pasm` from (TMS, TDI) pairs, and get the TDO bits |

## Results

The tests in `iss/test/testFirmware.py` show these results for the programs in
`asm/examples`:

| Program | Result |
|---|---|
| UART TX | Each edge is on an exact bit boundary. `clkDiv` 104 gives 115200 baud (+0.16%) at 48 MHz. |
| UART RX | Back-to-back frames are received with a bit-time error from −3.5% (a fast sender) to +4.0% (a slow sender). The tests check ±3%. |
| SPI mode 0 | Without the bypass, `clkDiv` must be 2 or more (SCK 6 MHz at 48 MHz). With the `syncBypass` bit set for MISO, `clkDiv` 1 (SCK 12 MHz) operates. |
| WS2812B | T0H, T0L, T1H, and T1L are inside the datasheet limits at 48 MHz with `clkDiv` 6 |
| SPI mode 0 with CS | CS is low on each SCK rising edge, and high between bytes |
| I2C controller | Write, read, a wrong address, a repeated START, and clock stretch operate. A stretch above 63 ticks sets flag 1. At 48 MHz with `clkDiv` 9, SCL is 1.5 µs low and 1.125 µs high (381 kHz). The START and STOP setup and hold times are 0.75 µs or more. |
| PS/2 host | Receives frames and reports a parity error. Sends a command, gets the ACK, and receives the reply. At 48 MHz with `clkDiv` 48, CLK is low for 128 µs before a command. |
| JTAG controller | Reads the IDCODE after a TAP reset. With BYPASS in the IR, a DR shift delays the data by 1 bit. `clkDiv` 1 needs the `syncBypass` bit for TDO. |
