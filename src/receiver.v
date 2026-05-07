`default_nettype none

module receiver (
    input clk,
    input rst_n,

    input rx_enb, // rx baud tick 
    input rx, 

    output reg [7:0] rx_data,
    output reg rx_valid
);

    reg [2:0] bit_index; // track bit w each baud tick
    reg [7:0] shift_reg; // temp storage of byte

    typedef enum reg [1:0] {
        IDLE = 2'b00,
        START = 2'b01,
        DATA = 2'b10,
        STOP = 2'b11
    } state_t;

    state_t state;

    always@(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            rx_valid <= 0;
            rx_data <= 0;

        end else begin

            case (state)

            IDLE : begin

                if (rx == 0)
                    state <= START;
            end

            START : begin
                bit_index <= 0;

                if (rx_enb) 
                    state <= DATA;
            end

            DATA : begin
                if  (rx_enb) begin
                    shift_reg[bit_index] <= rx;
                    
                    if (bit_index == 7) 
                        state <= STOP; 
                    else
                        bit_index <= bit_index + 1;
                end
            end

            STOP : begin 
                rx_data <= shift_reg;
                rx_valid <= 1; 

                if (rx_enb)
                    state <= IDLE;
                    rx_valid <= 0;
            end

            endcase
        end
    end

endmodule