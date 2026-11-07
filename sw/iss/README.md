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
4. With `syncStages` set to 2, the core reads on cycle c the inputs of cycle c − 2.
   With `syncStages` set to 0, the core reads the inputs of cycle c.
5. At the start, the synchronizer holds the first input value. This models a start after the
   program load (ADR-0006).
6. A `WAIT` with a timeout that ends by timeout takes `T` + 1 ticks.
7. An instruction from `OUT EXEC` or `MOV EXEC` executes on the next tick. The PC does not change,
   unless the instruction is a jump. The delay of the `OUT EXEC` or `MOV EXEC` instruction is
   ignored.
8. The cores execute in index order on each tick. A flag change by core n is visible to cores
   with an index above n on the same tick.
9. Outputs from different cores are combined with OR.

## Protocol models

`iss/models.py` has these models:

| Model | Function |
|---|---|
| `PinRecorder` | Records each level change of 1 output pin |
| `UartSource` | Makes a UART waveform, with a baud error and a bad stop bit if necessary |
| `decodeUart` | Decodes a recorded UART waveform. It samples each bit at its center. |
| `SpiTarget` | An SPI mode 0 target. It samples MOSI on the SCK rising edge and changes MISO on the falling edge. |

## Results

The tests in `iss/test/testFirmware.py` show these results for the programs in
`asm/examples`:

| Program | Result |
|---|---|
| UART TX | Each edge is on an exact bit boundary. `clkDiv` 104 gives 115200 baud (+0.16%) at 48 MHz. |
| UART RX | Back-to-back frames are received with a baud error of ±2%. At −3%, the receiver loses the frame alignment after 4 frames. |
| SPI mode 0 | With 2 synchronizer stages, `clkDiv` must be 2 or more (SCK 6 MHz at 48 MHz). At `clkDiv` 1 (12 MHz), the core must bypass the MISO synchronizer. |
| WS2812B | T0H, T0L, T1H, and T1L are inside the datasheet limits at 48 MHz with `clkDiv` 6 |
