module programmable_pwm_timer (
    input  logic       clk_i,
    input  logic       rst_ni,
    input  logic       start_i,
    input  logic [7:0] period_i,
    input  logic [7:0] duty_i,
    output logic       pwm_out,
    output logic       done_o
);

    typedef enum logic [1:0] {
        IDLE = 2'b00,
        RUN  = 2'b01,
        DONE = 2'b10
    } state_t;

    state_t     state_q;
    state_t     state_d;
    logic [7:0] period_q;
    logic [7:0] duty_q;
    logic [7:0] count_q;

    always_comb begin
        state_d = state_q;

        case (state_q)
            IDLE: begin
                if (start_i) begin
                    state_d = RUN;
                end
            end

            RUN: begin
                if (count_q == (period_q - 8'd1)) begin
                    state_d = DONE;
                end
            end

            DONE: begin
                state_d = IDLE;
            end

            default: begin
                state_d = IDLE;
            end
        endcase
    end

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            state_q  <= IDLE;
            period_q <= 8'd1;
            duty_q   <= 8'd0;
            count_q  <= 8'd0;
            pwm_out  <= 1'b0;
            done_o   <= 1'b0;
        end else begin
            state_q <= state_d;

            case (state_q)
                IDLE: begin
                    count_q <= 8'd0;
                    pwm_out <= 1'b0;
                    done_o  <= 1'b0;

                    if (start_i) begin
                        period_q <= (period_i == 8'd0) ? 8'd1 : period_i;
                        duty_q   <= duty_i;
                        pwm_out  <= (duty_i != 8'd0);
                    end
                end

                RUN: begin
                    done_o <= 1'b0;

                    if (count_q == (period_q - 8'd1)) begin
                        count_q <= 8'd0;
                        pwm_out <= 1'b0;
                        done_o  <= 1'b1;
                    end else begin
                        count_q <= count_q + 8'd1;
                        pwm_out <= ((count_q + 8'd1) < duty_q);
                    end
                end

                DONE: begin
                    count_q <= 8'd0;
                    pwm_out <= 1'b0;
                    done_o  <= 1'b0;
                end

                default: begin
                    period_q <= 8'd1;
                    duty_q   <= 8'd0;
                    count_q  <= 8'd0;
                    pwm_out  <= 1'b0;
                    done_o   <= 1'b0;
                end
            endcase
        end
    end

endmodule
