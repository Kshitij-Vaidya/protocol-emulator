# Protocol Requirements

Status: draft v0.1 (2026-11-07). This table gives the clock target and the timing resolution for
the architecture.

Terms:

- **Core clock**: the `clk` input of the design. The current value is 50 MHz (20 ns).
- **Cycles per bit**: the number of core clock cycles for 1 bit time.
- **Confirmed**: the value comes from the primary source in the *Sources* list.
- **To check**: the value is from memory or from a secondary source. Check it before the
  decision that uses it.

## Sources

1. NXP UM10204, *I2C-bus specification and user manual*, rev. 7.0 (1 October 2021), Table 11 and
   section 3.1.9. The NXP link returned HTTP 404 on 2026-11-07. The copy read was
   <https://www.pololu.com/file/0J435/UM10204.pdf>.
2. Worldsemi, [*WS2812B datasheet*](https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf), the
   "Data transfer time" table.
3. Tiny Tapeout specifications: [GPIO](https://tinytapeout.com/specs/gpio/) and
   [clock](https://tinytapeout.com/specs/clock/).
4. RP2040 datasheet, chapter 3 (refer to `pio.md`).

## Tiny Tapeout pin limits

| Item | Value | Source |
|---|---|---|
| Pins | 8 inputs (`ui_in`), 8 outputs (`uo_out`), 8 bidirectional (`uio`) | Confirmed (3) |
| Maximum output frequency | 33 MHz | Confirmed (3), for the SKY130 pad |
| Maximum input frequency | 66 MHz | Confirmed (3), for the SKY130 pad |
| Round-trip latency through the mux | 20 ns (worst case, TT3.5 silicon) | Confirmed (3) |
| Delay difference between pins | less than 2 ns | Confirmed (3) |
| Clock insertion delay | up to 10 ns | Confirmed (3) |
| Demo board clock | 1 Hz to 66.5 MHz, from the RP2040 | Confirmed (3). The TT04–TT08 board page says 50 MHz. |
| I/O voltage on the demo board | 3.3 V. The inputs are not 5 V tolerant. | Confirmed (3) |
| Drive strength | 4 mA | Confirmed (3), for the SKY130 pad |

CAUTION: The pad values are for SKY130. The IHP CMOS5L pads can be different. Ask Tiny Tapeout for
the IHP pad and mux values before the week 7 decision on the stretch protocols.

NOTE: An open-drain output is possible on `uio`. Set `uio_out` to 0, and drive `uio_oe` with the
inverted data. This is the same method as the PIO `pindirs` (refer to `pio.md`). The pull-up
resistors must be external.

## Protocol table

| Protocol | Bit rate | Tolerance | Pins | Cycles per bit at 50 MHz | Status |
|---|---|---|---|---|---|
| UART 8N1 | 9600 to 1 Mbaud (115200 typical) | ±5.2% total mismatch, both ends together (calculation 1) | TX push-pull, RX input | 5208 (9600), 434 (115200), 50 (1 Mbaud) | Calculated |
| SPI controller, modes 0–3 | No standard. Device limit, typically 1–20 MHz. | Set by the device setup and hold times | SCK, MOSI, CS push-pull; MISO input | 2 or more instructions for each bit | Calculated (calculation 2) |
| I2C Standard-mode | 0–100 kHz | tLOW ≥ 4.7 µs, tHIGH ≥ 4.0 µs, tSU;DAT ≥ 250 ns | SDA, SCL open-drain | tLOW ≥ 235, tHIGH ≥ 200 | Confirmed (1) |
| I2C Fast-mode | 0–400 kHz | tLOW ≥ 1.3 µs, tHIGH ≥ 0.6 µs, tSU;DAT ≥ 100 ns | SDA, SCL open-drain | tLOW ≥ 65, tHIGH ≥ 30 | Confirmed (1) |
| I2C Fast-mode Plus | 0–1 MHz | tLOW ≥ 0.5 µs, tHIGH ≥ 0.26 µs, tSU;DAT ≥ 50 ns | SDA, SCL open-drain | tLOW ≥ 25, tHIGH ≥ 13 | Confirmed (1) |
| WS2812B | 800 kbit/s (TH + TL = 1.25 µs ± 600 ns) | T0H 0.4 µs, T1H 0.8 µs, T0L 0.85 µs, T1L 0.45 µs, each ±150 ns; reset > 50 µs | DIN push-pull | 62.5 (T0H 20, T1H 40, each ±7.5) | Confirmed (2) |
| PS/2 (device or host) | 10–16.7 kHz, clock from the device | 11-bit frame: start, 8 data, odd parity, stop | CLK, DATA open-drain | approximately 3000–5000 | To check |
| JTAG | No fixed rate. The target sets the maximum. | TDI and TMS change on the falling edge of TCK. TDO is sampled on the rising edge. | TCK, TMS, TDI push-pull; TDO input | Same as SPI | To check |
| SWD | No fixed rate. The target sets the maximum. | Turn-around cycles between host drive and target drive | SWCLK push-pull; SWDIO bidirectional | Same as SPI | To check |
| USB low-speed | 1.5 Mbit/s ± 1.5% | NRZI coding, bit stuff after 6 ones, differential D+ and D−, SE0 for end of packet | D+, D− bidirectional | 33.3 (use 33: +1.0%) | To check |
| 10BASE-T | 10 Mbit/s, Manchester (20 MHz half-bit rate) | ±0.01% | Differential pair, with link pulses | 2.5 for each half bit | To check |

## Calculations

### Calculation 1: UART tolerance

The receiver finds the start edge and samples each bit at its center. The last sample is the stop
bit, at 9.5 bit times after the start edge. A sample stays inside the stop bit if the total timing
error at that point is less than 0.5 bit time:

    9.5 × error < 0.5   →   error < 5.26%

This is the total mismatch of the transmitter and the receiver together. Thus, each end must be
within approximately ±2.5%.

The core clock divides to an integer number of cycles for each bit:

| Baud rate | Cycles per bit at 50 MHz | Error | Cycles per bit at 48 MHz | Error |
|---|---|---|---|---|
| 9600 | 5208 | +0.01% | 5000 | 0.00% |
| 115200 | 434 | +0.01% | 417 | −0.08% |
| 1 000 000 | 50 | 0.00% | 48 | 0.00% |
| 3 000 000 | 17 | −1.96% | 16 | 0.00% |

### Calculation 2: SPI controller speed

1. Output only (MOSI and SCK): with side-set, 1 bit takes 2 instructions (PIO `spi_tx_fast`).
   The maximum SCK is the core clock divided by 2: 25 MHz at 50 MHz. The SKY130 pad limit is
   33 MHz.
2. Duplex (MISO sampled): the MISO data returns after the round-trip delay through the mux
   (20 ns), the device clock-to-output delay, and the input synchronizer. The synchronizer adds
   2 cycles (40 ns at 50 MHz), unless the design bypasses it. Thus, SCK must be approximately
   5–10 MHz or less with the synchronizer, and approximately 10–15 MHz without it.

Conclusion: an SPI controller up to approximately 10 MHz is realistic. The core must allow an
input synchronizer bypass for synchronous inputs, as PIO does.

### Calculation 3: I2C

At 50 MHz, Fast-mode Plus needs tLOW ≥ 25 cycles and tHIGH ≥ 13 cycles. The PIO delay field
(31 cycles maximum) is sufficient. Standard-mode needs 235 cycles, so it needs a delay loop or a
clock divider.

Clock stretch: the controller must read SCL after it releases SCL, and wait while SCL stays low
(UM10204 section 3.1.9). The 20 ns round trip and the 2-cycle synchronizer delay the read of SCL
by approximately 3 cycles. The program must wait at least 3 cycles after the release before the
first read of SCL.

## Operations for each bit

| Protocol | Operations that the core must do for each bit |
|---|---|
| UART TX | Shift 1 bit to the pin. Wait 1 bit time. Count 8 bits. Add the start and stop bits. |
| UART RX | Wait for the falling edge. Wait 1.5 bit times. Sample and shift 1 bit. Wait 1 bit time. Count 8 bits. Check the stop bit. |
| SPI | Set the data bit and the clock edge at the same time (side-set). Sample MISO on the other clock edge. Count the bits. |
| I2C | Drive the direction of SDA (open drain). Release SCL. Wait while SCL is low (clock stretch). Sample SDA. Drive SCL low. Read the ACK bit. Make START and STOP conditions. |
| WS2812B | Set the pin high. Wait T0H or T1H, as the data bit selects. Set the pin low. Wait T0L or T1L. |
| PS/2 | Wait for the falling edge of CLK (from the device). Sample DATA. Shift 1 bit. Calculate the parity. |
| JTAG and SWD | As SPI. SWD also changes the direction of SWDIO for the turn-around cycles and checks the parity. |
| USB low-speed | NRZI decode, remove the stuffed bits, find SE0. Respond within the bus turn-around time. |

## Results

1. **Clock target.** 50 MHz is sufficient for UART, SPI (to approximately 10 MHz), I2C (all 3
   modes), WS2812B, PS/2, JTAG, and SWD. The M0 and SRAM test designs meet 50 MHz with more than
   12 ns of setup slack.
2. **48 MHz is a possible alternative.** It gives exact bit times for 1 Mbaud and 3 Mbaud UART,
   and 32 cycles for each USB low-speed bit. The demo board can make 48 MHz. Decide this in the
   clock target ADR.
3. **Timing resolution.** 1 core clock cycle (20 ns) is sufficient. The smallest tolerance in the
   table is ±150 ns (WS2812B), which is ±7 cycles.
4. **Delay range.** The longest bit time is UART at 9600 baud: 5208 cycles. A 5-bit delay field
   (31 cycles) is not sufficient. The core needs a clock divider, a delay loop, or a longer delay
   counter.
5. **Pin features.** The core must have these 4 pin features:
   - output enable control for open drain (I2C, PS/2),
   - input synchronizers with a bypass for synchronous inputs (SPI),
   - a wait on a pin level or edge (UART RX, I2C clock stretch, PS/2),
   - a change of pin direction during a transfer (SWD).
6. **10BASE-T is not possible at 50 MHz.** It needs 2.5 cycles for each half bit, and it needs a
   differential analog interface. Remove it from the stretch list.
7. **USB low-speed is possible only with care.** It needs differential pins and a fast response
   time. Decide this in week 7.
