// =============================================================================
// File       : tb_polar_scl.sv
// Description: Self-checking testbench for LLR-based SCL Polar Decoder
//              Verifies RTL against Python Golden Model test vectors.
// =============================================================================
`timescale 1ns/1ps

module tb_polar_scl;
    import scl_pkg::*;

    logic                       clk;
    logic                       rst_n;
    logic                       start_i;
    logic signed [N-1:0][Q-1:0] channel_llr_i;
    logic                       done_o;
    logic        [N-1:0]        decoded_u_o;
    logic        [M-1:0]        best_pm_o;

    // Instantiate DUT
    polar_scl_top u_dut (
        .clk           (clk),
        .rst_n         (rst_n),
        .start_i       (start_i),
        .channel_llr_i (channel_llr_i),
        .done_o        (done_o),
        .decoded_u_o   (decoded_u_o),
        .best_pm_o     (best_pm_o)
    );

    // 100 MHz Clock Generation
    initial clk = 1'b0;
    always #5 clk = ~clk;

    // Test Vector Memories
    logic [Q-1:0] tv_llrs [0:N-1];
    logic [0:0]   tv_exp_u[0:N-1];
    logic [N-1:0] expected_u_vec;
    int           cycle_count;
    integer       llr_file;
    integer       expected_file;

    initial begin
        $dumpfile("wave.vcd");
        $dumpvars(0, tb_polar_scl);

        llr_file = $fopen("../verif/tv_channel_llrs.mem", "r");
        if (llr_file == 0)
            $fatal(1, "Cannot open ../verif/tv_channel_llrs.mem");
        $fclose(llr_file);

        expected_file = $fopen("../verif/tv_expected_u.mem", "r");
        if (expected_file == 0)
            $fatal(1, "Cannot open ../verif/tv_expected_u.mem");
        $fclose(expected_file);

        $readmemh("../verif/tv_channel_llrs.mem", tv_llrs);
        $readmemh("../verif/tv_expected_u.mem", tv_exp_u);
        for (int i = 0; i < N; i++) begin
            channel_llr_i[i]  = $signed(tv_llrs[i]);
            expected_u_vec[i] = tv_exp_u[i];
        end

        rst_n   = 1'b0;
        start_i = 1'b0;
        repeat (3) @(posedge clk);
        rst_n   = 1'b1;
        @(posedge clk);

        // Launch Decoding
        $display("==========================================================");
        $display("Starting LLR-Based SCL Polar Decoder Simulation (N=%0d, L=%0d)", N, L);
        $display("==========================================================");
        start_i     = 1'b1;
        cycle_count = 0;
        @(posedge clk);
        start_i     = 1'b0;

        while (!done_o && cycle_count < 200) begin
            @(posedge clk);
            cycle_count++;
        end

        $display("Decoding completed in %0d clock cycles.", cycle_count);
        $display("Expected u_vec : %b", expected_u_vec);
        $display("Decoded  u_o   : %b (Best Path Metric = %0d)", decoded_u_o, best_pm_o);

        if (decoded_u_o === expected_u_vec) begin
            $display("STATUS: [PASS] RTL output matches Golden Model 100%%!");
        end else begin
            $display("STATUS: [FAIL] Mismatch detected!");
            $fatal(1);
        end
        $display("==========================================================");
        $finish;
    end

endmodule
