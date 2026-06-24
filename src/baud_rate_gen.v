`default_nettype none

/* Adding a comment to indicate some of the 
not imediatly trivial assumptions about your  
design helps external readers grasp the code 
much faster, leaving them more focus to catch 
issues. An example of where a small comment could
be usefull would be in this module indicating 
the desired target baud rate and the assumed 
opterating clock frequency.

Eg:
UART baud rate genertor, rx_enb and tx_enb
are the baud tick and pulse high for one cycle 
for each UART transition. 
clk - 50MHz
rx - ? baud (50000000/326 ~ 153374.2)
tx - 9600 baud (50000000/5209 ~ 9598.7)


Are you certain you can have different baud rates on 
RX/TX? This seems none standard but I am not sure this
isn't what you are going for. 
Else, your RX baud rate doesn't seem to match any of the
standard spec baud rates unlike the TX baud. 
Lastly, you will have an issue where you will be dropping received
packets since RX is faster than TX. Is this expected behavior ? 

If you wish to fix this: RX baud <= TX baud
*/ 
 module baud_rate_gen (
    input clk, 
    input rst_n,
    input rx_sync,
    output wire tx_enb,
    output wire rx_enb);

    reg [12:0] tx_counter;
    reg [9:0] rx_counter;

    always@(posedge clk)
        begin 
            if (!rst_n || rx_sync)
                rx_counter <= 0;
            else if (rx_counter == 325)
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
