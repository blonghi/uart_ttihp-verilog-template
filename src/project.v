/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

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

  

  wire tx_enb;
  wire [7:0] tx_data;
  wire tx_valid;

  wire rx_enb;
  wire rx;
  wire [7:0] rx_data;
  wire rx_valid;

  assign tx_data = ui_in;

  // List all unused inputs to prevent warnings
  wire _unused = &{uio_in, uio_out, uio_oe, ena};

  assign uio_out = 0;
  assign uio_oe = 0;

    baud_rate_gen u_baudrate_generator (
    //inputs
    .clk(clk),
    .rst_n(rst_n),

    //outputs
    .rx_enb(rx_enb),
    .tx_enb(tx_enb)
  );

    transmitter u_transmitter (
    //inputs 
    .clk(clk), 
    .rst_n(rst_n), 
    .wr_enb(rx_valid),
    .tx_enb(tx_enb),
    .tx_data(tx_data),

    //outputs
    .tx(rx)
  ); 

  receiver u_receiver (
    // inputs
    .clk(clk), 
    .rst_n(rst_n), 
    .rx_enb(rx_enb),
    .rx(rx),

    //outputs
    .rx_data(rx_data),
    .rx_valid(rx_valid)
  );


  assign uo_out = rx_data;




endmodule
