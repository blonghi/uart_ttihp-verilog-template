
# UART (Universal Asynchronous Receiver + Transmitter) : A Tiny Tapeout Project

## How it works

This project implements a simple UART (Universal Asynchronous Receiver + Transmitter). It's capable of independently transmitting and receiving 8-bit serial data (8-N-1).  

| Field | Value |
|:---:|:---:|
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |

The design is split into four modules:

- **`tt_um_uart`** - the top-level wrapepr that maps pins to signals and instantiates the 3 following modules.

- **`baud_rate_gen`** - generates two enable ticks from the system clock. 'tx_counter' is free-running, wrapping around at 5208, producing 'tx_enb' (one pulse per baud period). 'rx_counter' wraps around at 3266 (1/16th of 'tx_counter's range) This produces 'rx_enb' at 16x the rate to allow the receiver to oversample and locate the center of each incoming bit. 'rx_counter' resets every 'rx_sync' pulse (start-bit detection), keeping RX sampling aligned. 

- **`transmitter`** - FSM that on write request serializes an 8-bit byte onto the tx line as: start bit, 8 data bits (LSB first),  then a stop bit. 

- **`receiver`** - FSM that watches the rx line for a falling edge (start bit) then samples 8 data bits at the center od each bit period (16x oversampling to find bit-center), then checks for the stop bit and pulses rx_valid for one cycle with the received byte on rx_data.

### Limitations
- No parity bit. 
- If there is a bad frame, it is simply never latched with no downstream indication the error occurred. 


## How to test

Explain how to use your project

## External hardware

List external hardware used in your project (e.g. PMOD, LED display, etc), if any
