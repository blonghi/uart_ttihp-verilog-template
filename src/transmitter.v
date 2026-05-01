`default_nettype none

module transmitter(
    input clk, 
    input rst_n,

    input wr_enb, // new byte is ready, start sending
    input tx_enb, // send bit now
    input [7:0] tx_data, // byte to send

    output reg tx
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
            tx <= 1;
            bit_index <= 0;

        end else begin

            case (state)

            IDLE : begin
                tx <= 1;

                if (wr_enb) begin
                    state <= START;
                    shift_reg <= tx_data;
                end
            end

            START : begin
                tx <= 0; 

                if (tx_enb) begin
                    state <= DATA;
                end
            end

            DATA : begin
                if (tx_enb) begin
                    tx <= shift_reg[bit_index];

                    if (bit_index == 7)
                        state <= STOP;
                    else
                        bit_index <= bit_index + 1;
                end 
            end 

            STOP : begin 
                tx <= 1;

                if (tx_enb)
                    state <= IDLE;
            end

            endcase
        end
    end

endmodule
