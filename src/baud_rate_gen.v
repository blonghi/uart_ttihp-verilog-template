`default_nettype none

 module baud_rate_gen (
    input clk, 
    input rst_n,
    input rx_sync,
    output wire tx_enb,
    output wire rx_enb);

    reg [12:0] tx_counter;
    reg [12:0] rx_counter;

    always@(posedge clk)
        begin 
            if (!rst_n || rx_sync)
                rx_counter <= 0;
            else if (rx_counter == 326)
                rx_counter <= 0;
            else 
                rx_counter <= rx_counter + 1'b1;
        end

    always@(posedge clk)
        begin 
            if (!rst_n)
                tx_counter <= 0; 
            else if (tx_counter == 5208)
                tx_counter <= 0;
            else 
                tx_counter <= tx_counter + 1'b1;
        end
    
    assign tx_enb = (tx_counter == 0) ? 1'b1 : 1'b0;
    assign rx_enb = (rx_counter == 163) ? 1'b1 : 1'b0;

 endmodule
