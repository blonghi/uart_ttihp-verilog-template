`default_nettype none

module receiver (
    input clk,
    input rst_n,

    input rx_enb, // rx baud tick 
    input rx, 

    output reg rx_sync,
    output reg [7:0] rx_data,
    output reg rx_valid
);

    reg [2:0] bit_index; // track bit w each baud tick
    reg [7:0] shift_reg; // temp storage of byte

    typedef enum reg [1:0] {
        IDLE  = 2'b00,
        START = 2'b01,
        DATA  = 2'b10,
        STOP  = 2'b11
    } state_t;

    state_t state;

    always@(posedge clk or negedge rst_n) begin // why are you using an async rst ? 
        if (!rst_n) begin
            state <= IDLE;
            rx_valid <= 0;// Not an issue here but default behavior when the type is unspecified is to infer a 32 bit wide value. If you data is say 33 bits wide this means your 33rd bit might not be reset so it is good practice to take the habit of explicitly specifying the types.
            rx_data <= 0;
            shift_reg <= 0;
            rx_sync <= 0;

        end else begin

            case (state)

            IDLE : begin
                rx_valid <= 0;

                if (rx == 0) begin
                    rx_sync <= 1;
                    state <= START;
                end
            end

            START : begin
                bit_index <= 0;
                rx_sync <= 0;

                if (rx_enb) 
                    state <= DATA;
            end

            DATA : begin
                if  (rx_enb) begin
                    shift_reg[bit_index] <= rx;// shifting data in would be cheaper, with this syntax you are infering a mux, which is more expensive in logic. This isn't an issue for this design since it is small but if you start building bigger designs and start running out of area it is a good thing to keep in mind. 
                    
                    if (bit_index == 7) // technically speaking UART allows 5,6,7 or 8 data bits, here you are chosing to hard code it at 7, not a bug but a design assumption to keep in mind when setting up your uart interface and should be specified in the doc 
                        state <= STOP; 
                    else
                        bit_index <= bit_index + 1;
                end
            end
			// same comment for the partiy bit, it's optional so it's fine but do mention it in the doc as an assumption

            STOP : begin 
                if (rx_enb) begin
                    if (rx == 1'b1) begin
                        rx_data <= shift_reg;
                        rx_valid <= 1;
                    end
                    state <= IDLE;
                end
            end

            endcase
        end
    end

endmodule
