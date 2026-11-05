module async_fifo #(
    parameter int unsigned DATA_WIDTH = 8,
    parameter int unsigned DEPTH      = 16
) (
    input  logic                  wr_clk_i,
    input  logic                  wr_rst_ni,
    input  logic                  wr_en_i,
    input  logic [DATA_WIDTH-1:0] wr_data_i,
    output logic                  full_o,

    input  logic                  rd_clk_i,
    input  logic                  rd_rst_ni,
    input  logic                  rd_en_i,
    output logic [DATA_WIDTH-1:0] rd_data_o,
    output logic                  empty_o
);

    localparam int unsigned ADDR_W = $clog2(DEPTH);
    localparam int unsigned PTR_W  = ADDR_W + 1;
    localparam logic [PTR_W-1:0] FULL_XOR_MASK =
        {2'b11, {(PTR_W-2){1'b0}}};

    logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    logic [PTR_W-1:0] wr_bin_q;
    logic [PTR_W-1:0] wr_gray_q;
    logic [PTR_W-1:0] wr_bin_next;
    logic [PTR_W-1:0] wr_gray_next;

    logic [PTR_W-1:0] rd_bin_q;
    logic [PTR_W-1:0] rd_gray_q;
    logic [PTR_W-1:0] rd_bin_next;
    logic [PTR_W-1:0] rd_gray_next;

    logic [PTR_W-1:0] rd_gray_sync1_q;
    logic [PTR_W-1:0] rd_gray_sync2_q;
    logic [PTR_W-1:0] wr_gray_sync1_q;
    logic [PTR_W-1:0] wr_gray_sync2_q;

    logic wr_accept;
    logic rd_accept;
    logic full_next;
    logic empty_next;

    assign wr_accept = wr_en_i && !full_o;
    assign rd_accept = rd_en_i && !empty_o;

    assign wr_bin_next  = wr_bin_q + PTR_W'(wr_accept);
    assign wr_gray_next = (wr_bin_next >> 1) ^ wr_bin_next;
    assign rd_bin_next  = rd_bin_q + PTR_W'(rd_accept);
    assign rd_gray_next = (rd_bin_next >> 1) ^ rd_bin_next;

    assign full_next  = (wr_gray_next == (rd_gray_sync2_q ^ FULL_XOR_MASK));
    assign empty_next = (rd_gray_next == wr_gray_sync2_q);

    // Synchronize Gray-coded pointers into the opposite clock domains.
    always_ff @(posedge wr_clk_i or negedge wr_rst_ni) begin
        if (!wr_rst_ni) begin
            rd_gray_sync1_q <= '0;
            rd_gray_sync2_q <= '0;
        end else begin
            rd_gray_sync1_q <= rd_gray_q;
            rd_gray_sync2_q <= rd_gray_sync1_q;
        end
    end

    always_ff @(posedge rd_clk_i or negedge rd_rst_ni) begin
        if (!rd_rst_ni) begin
            wr_gray_sync1_q <= '0;
            wr_gray_sync2_q <= '0;
        end else begin
            wr_gray_sync1_q <= wr_gray_q;
            wr_gray_sync2_q <= wr_gray_sync1_q;
        end
    end

    // Write-domain pointer, memory write, and full flag.
    always_ff @(posedge wr_clk_i or negedge wr_rst_ni) begin
        if (!wr_rst_ni) begin
            wr_bin_q  <= '0;
            wr_gray_q <= '0;
            full_o    <= 1'b0;
        end else begin
            wr_bin_q  <= wr_bin_next;
            wr_gray_q <= wr_gray_next;
            full_o    <= full_next;

            if (wr_accept) begin
                mem[wr_bin_q[ADDR_W-1:0]] <= wr_data_i;
            end
        end
    end

    // Read-domain pointer, registered data output, and empty flag.
    always_ff @(posedge rd_clk_i or negedge rd_rst_ni) begin
        if (!rd_rst_ni) begin
            rd_bin_q  <= '0;
            rd_gray_q <= '0;
            rd_data_o <= '0;
            empty_o   <= 1'b1;
        end else begin
            rd_bin_q  <= rd_bin_next;
            rd_gray_q <= rd_gray_next;
            empty_o   <= empty_next;

            if (rd_accept) begin
                rd_data_o <= mem[rd_bin_q[ADDR_W-1:0]];
            end
        end
    end

endmodule
