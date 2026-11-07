## How it works

This is the SRAM macro test for the protocol emulator project. It has a program memory (the IHP SRAM macro `RM_IHPSG13_1P_256x16_c2_bm_bist`, 256 words of 16 bits) and a UART transmitter (8N1, 115200 baud, 50 MHz clock).

The host writes words into the memory with the command pins. A rising edge on `send` transmits 1 byte of the addressed word on the UART.

| `uio[2:1]` (command) | Operation |
|---|---|
| `00` | Idle. The memory reads the word at the address register. |
| `01` | The address register gets the byte on `ui[7:0]`. |
| `10` | The low-byte register gets the byte on `ui[7:0]`. |
| `11` | The memory writes the word {`ui[7:0]`, low-byte register} at the address register. |

`uio[3]` (`byteSelect`) selects the byte that `send` transmits: 0 for the low byte, 1 for the high byte.

The design synchronizes all inputs with flip-flops. Each input must stay stable for 4 clock cycles or more.

## How to test

CAUTION: Change `ui[7:0]` only while the command is `00`. A change during another command can write a wrong value.

To write a word:

1. Set the command to `00`.
2. Set the address on `ui[7:0]`. Set the command to `01`. Set the command to `00`.
3. Set the low byte on `ui[7:0]`. Set the command to `10`. Set the command to `00`.
4. Set the high byte on `ui[7:0]`. Set the command to `11`. Set the command to `00`.

To read a word:

1. Connect a UART receiver (115200 baud, 8N1) to `uo[0]`.
2. Set the address with the command `01`. Set the command to `00`.
3. Set `uio[3]` low. Set `uio[0]` high, then set it low. The receiver shows the low byte.
4. Wait until `uo[1]` is high.
5. Set `uio[3]` high. Set `uio[0]` high, then set it low. The receiver shows the high byte.

NOTE: The transmitter ignores a `send` edge while `uo[1]` is low.

## External hardware

A USB-to-UART adapter at 3.3 V on `uo[0]`.
