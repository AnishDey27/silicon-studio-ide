`timescale 1ns/1ps

module tb_programmable_pwm_timer;
  logic       clk_i;
  logic       rst_ni;
  logic       start_i;
  logic [7:0] period_i;
  logic [7:0] duty_i;
  logic       pwm_out;
  logic       done_o;

  integer cycle;
  integer effective_period;
  logic   expected_pwm;

  programmable_pwm_timer dut (
    .clk_i   (clk_i),
    .rst_ni  (rst_ni),
    .start_i (start_i),
    .period_i(period_i),
    .duty_i  (duty_i),
    .pwm_out (pwm_out),
    .done_o  (done_o)
  );

  initial begin
    clk_i = 1'b0;
    forever #5 clk_i = ~clk_i;
  end

  initial begin
    $dumpfile("wave.vcd");
    $dumpvars(0, tb_programmable_pwm_timer);
  end

  task automatic check_outputs(
    input logic expected_pwm_value,
    input logic expected_done_value,
    input integer test_period,
    input integer test_duty,
    input integer test_cycle
  );
    begin
      if (pwm_out !== expected_pwm_value || done_o !== expected_done_value) begin
        $display(
          "[TB_FAIL] period=%0d duty=%0d cycle=%0d expected pwm/done=%b/%b got=%b/%b",
          test_period,
          test_duty,
          test_cycle,
          expected_pwm_value,
          expected_done_value,
          pwm_out,
          done_o
        );
        $fatal(1, "PWM timer output mismatch");
      end
    end
  endtask

  task automatic run_case(
    input logic [7:0] test_period,
    input logic [7:0] test_duty
  );
    integer test_period_int;
    integer test_duty_int;
    begin
      test_period_int = (test_period == 8'd0) ? 1 : test_period;
      test_duty_int = test_duty;

      @(negedge clk_i);
      period_i = test_period;
      duty_i = test_duty;
      start_i = 1'b1;

      // The first RUN cycle is count zero, and configuration is sampled here.
      @(posedge clk_i);
      #1;
      check_outputs((test_duty != 8'd0), 1'b0,
                    test_period_int, test_duty_int, 0);

      // Change the inputs while RUN is active to verify the configuration registers.
      @(negedge clk_i);
      start_i = 1'b0;
      period_i = 8'hFF;
      duty_i = 8'h00;

      for (cycle = 1; cycle < test_period_int; cycle = cycle + 1) begin
        @(posedge clk_i);
        #1;
        expected_pwm = (cycle < test_duty_int);
        check_outputs(expected_pwm, 1'b0,
                      test_period_int, test_duty_int, cycle);
      end

      // DONE is asserted for one full cycle, with PWM low.
      @(posedge clk_i);
      #1;
      check_outputs(1'b0, 1'b1,
                    test_period_int, test_duty_int, test_period_int);

      @(posedge clk_i);
      #1;
      check_outputs(1'b0, 1'b0,
                    test_period_int, test_duty_int, test_period_int + 1);
    end
  endtask

  initial begin
    rst_ni = 1'b0;
    start_i = 1'b0;
    period_i = 8'd0;
    duty_i = 8'd0;

    repeat (2) @(posedge clk_i);
    #1;
    check_outputs(1'b0, 1'b0, 0, 0, -1);

    @(negedge clk_i);
    rst_ni = 1'b1;

    run_case(8'd4, 8'd2);
    run_case(8'd3, 8'd0);
    run_case(8'd2, 8'd5);
    run_case(8'd0, 8'd1);

    $display("[TB_PASS] programmable_pwm_timer configuration, PWM width, and DONE checks passed");
    $finish;
  end

  initial begin
    #10000;
    $display("[TB_FAIL] Global testbench timeout");
    $fatal(1, "Global testbench timeout");
  end
endmodule
