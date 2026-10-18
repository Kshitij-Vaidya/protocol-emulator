## How it works

This is the milestone M0 design for the protocol emulator project. It is a UART transmitter (8N1, 115200 baud, 50 MHz clock).

The design synchronizes the `send` input with 3 flip-flops. A rising edge on `send` loads the byte on `ui[7:0]` into the transmitter. The transmitter sends 1 start bit, 8 data bits (LSB first), and 1 stop bit on `uo[0]`. `uo[1]` (`txReady`) is low while a frame is in transmission.

## How to test

1. Set the clock to 50 MHz.
2. Connect a UART receiver (115200 baud, 8N1) to `uo[0]`.
3. Wait until `uo[1]` is high.
4. Set the byte on `ui[7:0]`.
5. Set `uio[0]` high, then set it low.

NOTE: The transmitter ignores a `send` edge while `uo[1]` is low.

The receiver shows the byte.

## External hardware

A USB-to-UART adapter at 3.3 V on `uo[0]`.
