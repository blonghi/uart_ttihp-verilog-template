/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

/* 
Rename file to match the module name. 
Some tools implity expect the module name and the file name to match exactly 
so for portability and to match your future colleges expectations it is a 
good practice to adopte. 
*/ 
module tt_um_uart (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // X IOs: Input path
    output wire [7:0] uio_out,  // X IOs: Output path
    output wire [7:0] uio_oe,   // X IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // X always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // All output pins must be assigned. If not used, assign to 0.

  

  wire wr_enb = uio_in[0];
  wire tx_enb;
  wire [7:0] tx_data = ui_in;

  wire rx_enb;
  wire rx_sync;
  wire [7:0] rx_data;
  wire rx_valid;

  reg [7:0] temp;

  // List all unused inputs to prevent warnings
  wire _unused = &{uio_in[7:1], uio_out, uio_oe, ena};

  assign uio_out = 0; // good, not tieing the outputs can issues, see tie cells in the implem if you want to learn more
  assign uio_oe = 0;

  baud_rate_gen u_baudrate_generator (
    //inputs
    .clk(clk),
    .rst_n(rst_n),
    .rx_sync(rx_sync),

    //outputs
    .rx_enb(rx_enb),
    .tx_enb(tx_enb)
  );

	/* Setting uart in loopback mode */ 
    transmitter u_transmitter (
    //inputs 
    .clk(clk), 
    .rst_n(rst_n), 
    .wr_enb(wr_enb),
    .tx_enb(tx_enb),
    .tx_data(tx_data),

    //outputs
    .tx(uo_out[0])
  ); 

  receiver u_receiver (
    // inputs
    .clk(clk), 
    .rst_n(rst_n), 
    .rx_enb(rx_enb),
    .rx(ui_in[0]),

    //outputs
    .rx_sync(rx_sync),
    .rx_data(rx_data),
    .rx_valid(rx_valid)
  );


  assign uo_out[7:1] = 0;



endmodule
