`timescale 1ns/1ps

module tb_async_fifo;
  localparam int DATA_WIDTH = 8;
  localparam int DEPTH = 16;
  localparam int TIMEOUT_CYCLES = 1000;

  logic                 wr_clk_i;
  logic                 wr_rst_ni;
  logic                 wr_en_i;
  logic [DATA_WIDTH-1:0] wr_data_i;
  logic                 full_o;
  logic                 rd_clk_i;
  logic                 rd_rst_ni;
  logic                 rd_en_i;
  logic [DATA_WIDTH-1:0] rd_data_o;
  logic                 empty_o;

  logic [DATA_WIDTH-1:0] expected_q[$];
  integer accepted_writes;
  integer accepted_reads;

  async_fifo #(
    .DATA_WIDTH(DATA_WIDTH),
    .DEPTH(DEPTH)
  ) dut (
    .wr_clk_i (wr_clk_i),
    .wr_rst_ni(wr_rst_ni),
    .wr_en_i  (wr_en_i),
    .wr_data_i(wr_data_i),
    .full_o   (full_o),
    .rd_clk_i (rd_clk_i),
    .rd_rst_ni(rd_rst_ni),
    .rd_en_i  (rd_en_i),
    .rd_data_o(rd_data_o),
    .empty_o  (empty_o)
  );

  initial begin
    wr_clk_i = 1'b0;
    forever #5 wr_clk_i = ~wr_clk_i;
  end

  initial begin
    rd_clk_i = 1'b0;
    #1.25;
    forever #12.5 rd_clk_i = ~rd_clk_i;
  end

  initial begin
    $dumpfile("wave.vcd");
    $dumpvars(0, tb_async_fifo);
  end

  task automatic write_byte(input logic [DATA_WIDTH-1:0] data);
    integer wait_cycles;
    begin
      wait_cycles = 0;
      while (full_o && wait_cycles < TIMEOUT_CYCLES) begin
        @(posedge wr_clk_i);
        wait_cycles = wait_cycles + 1;
      end
      if (full_o)
        $fatal(1, "Timed out waiting for write space");

      @(negedge wr_clk_i);
      wr_data_i = data;
      wr_en_i = 1'b1;
      @(posedge wr_clk_i);
      #1;
      expected_q.push_back(data);
      accepted_writes = accepted_writes + 1;
      @(negedge wr_clk_i);
      wr_en_i = 1'b0;
    end
  endtask

  task automatic read_byte;
    integer wait_cycles;
    logic [DATA_WIDTH-1:0] expected_data;
    begin
      wait_cycles = 0;
      while (empty_o && wait_cycles < TIMEOUT_CYCLES) begin
        @(posedge rd_clk_i);
        wait_cycles = wait_cycles + 1;
      end
      if (empty_o)
        $fatal(1, "Timed out waiting for readable data");
      if (expected_q.size() == 0)
        $fatal(1, "Scoreboard underflow before read");

      expected_data = expected_q[0];
      @(negedge rd_clk_i);
      rd_en_i = 1'b1;
      @(posedge rd_clk_i);
      #1;
      if (rd_data_o !== expected_data)
        $fatal(1, "Read data mismatch: expected %02h, got %02h",
               expected_data, rd_data_o);
      expected_q.pop_front();
      accepted_reads = accepted_reads + 1;
      @(negedge rd_clk_i);
      rd_en_i = 1'b0;
    end
  endtask

  task automatic wait_for_full;
    integer wait_cycles;
    begin
      wait_cycles = 0;
      while (!full_o && wait_cycles < TIMEOUT_CYCLES) begin
        @(posedge wr_clk_i);
        wait_cycles = wait_cycles + 1;
      end
      #1;
      if (!full_o)
        $fatal(1, "FULL did not assert within the write-clock timeout");
    end
  endtask

  task automatic wait_for_empty;
    integer wait_cycles;
    begin
      wait_cycles = 0;
      while (!empty_o && wait_cycles < TIMEOUT_CYCLES) begin
        @(posedge rd_clk_i);
        wait_cycles = wait_cycles + 1;
      end
      #1;
      if (!empty_o)
        $fatal(1, "EMPTY did not assert within the read-clock timeout");
    end
  endtask

  integer i = 0;
  integer burst_round = 0;
  integer fill_attempts = 0;
  integer writes_before = 0;
  integer reads_before = 0;

  initial begin
    wr_rst_ni = 1'b0;
    rd_rst_ni = 1'b0;
    wr_en_i = 1'b0;
    rd_en_i = 1'b0;
    wr_data_i = '0;
    accepted_writes = 0;
    accepted_reads = 0;

    repeat (8) @(posedge wr_clk_i);
    #1;
    wr_rst_ni = 1'b1;
    rd_rst_ni = 1'b1;
    repeat (4) @(posedge rd_clk_i);

    wait_for_empty();
    if (full_o)
      $fatal(1, "FULL asserted after reset with an empty FIFO");

    // Fill until full; the bounded attempt count catches a missing FULL flag.
    fill_attempts = 0;
    while (!full_o && fill_attempts < DEPTH + 2) begin
      write_byte(8'h20 + fill_attempts);
      fill_attempts = fill_attempts + 1;
    end
    wait_for_full();
    if (expected_q.size() != DEPTH)
      $fatal(1, "Expected FIFO occupancy %0d at FULL, scoreboard has %0d",
             DEPTH, expected_q.size());
    if (accepted_writes != DEPTH)
      $fatal(1, "Expected %0d accepted writes at FULL, got %0d",
             DEPTH, accepted_writes);

    // Drain the full FIFO and verify EMPTY follows the read-pointer CDC delay.
    while (expected_q.size() != 0)
      read_byte();
    wait_for_empty();
    repeat (2) @(posedge rd_clk_i);
    if (!empty_o)
      $fatal(1, "EMPTY deasserted while the scoreboard was empty");

    // Exercise repeated mixed bursts with both clocks running asynchronously.
    for (burst_round = 0; burst_round < 4; burst_round = burst_round + 1) begin
      writes_before = accepted_writes;
      reads_before = accepted_reads;
      for (i = 0; i < 5 + burst_round; i = i + 1)
        write_byte(8'h60 + burst_round * 8 + i);
      for (i = 0; i < 2 + (burst_round % 3); i = i + 1)
        read_byte();
      for (i = 0; i < 4; i = i + 1)
        write_byte(8'hA0 + burst_round * 4 + i);
      while (expected_q.size() != 0)
        read_byte();
      wait_for_empty();
      if (accepted_writes - writes_before != (5 + burst_round) + 4)
        $fatal(1, "Unexpected write count in mixed burst round %0d", burst_round);
      if (accepted_reads - reads_before != (5 + burst_round) + 4)
        $fatal(1, "Unexpected read count in mixed burst round %0d", burst_round);
    end

    if (expected_q.size() != 0)
      $fatal(1, "Scoreboard not empty at test completion");
    if (accepted_writes != accepted_reads)
      $fatal(1, "Final count mismatch: writes=%0d reads=%0d",
             accepted_writes, accepted_reads);
    if (!empty_o)
      $fatal(1, "FIFO not empty at test completion");

    $display("PASS: async_fifo accepted %0d writes and %0d reads; all data matched",
             accepted_writes, accepted_reads);
    $finish;
  end

  initial begin
    #100000;
    $fatal(1, "Global testbench timeout");
  end
endmodule
