// =============================================================================
// File       : metric_sorter.sv
// Description: True Hardware Parallel Radix-2L Sorter (Fig. 4a of Paper)
// =============================================================================
module metric_sorter (
    input  logic        [scl_pkg::L-1:0][scl_pkg::M-1:0]         pm_in_i,
    input  logic signed [scl_pkg::L-1:0][scl_pkg::Q-1:0]         dec_llr_i,
    input  logic                               is_frozen_i,
    output logic        [scl_pkg::L-1:0][scl_pkg::M-1:0]         pm_out_o,
    output logic        [scl_pkg::L-1:0][$clog2(scl_pkg::L)-1:0] parent_idx_o,
    output logic        [scl_pkg::L-1:0]                        dec_bit_o
);

    localparam int L = scl_pkg::L;
    localparam int Q = scl_pkg::Q;
    localparam int M = scl_pkg::M;
    localparam logic signed [Q-1:0] LLR_MAX = scl_pkg::LLR_MAX;
    localparam logic signed [Q-1:0] LLR_MIN = scl_pkg::LLR_MIN;
    localparam logic [M-1:0] PM_MAX = scl_pkg::PM_MAX;

    localparam int NUM_CAND = 2 * L;
    localparam int ID_W     = $clog2(L);

    logic [M-1:0]    cand_pm     [0:NUM_CAND-1];
    logic [ID_W-1:0] cand_parent [0:NUM_CAND-1];
    logic            cand_bit    [0:NUM_CAND-1];

    // 1. Candidate Metric Generation (Eq. 12)
    genvar g;
    generate
        for (g = 0; g < L; g++) begin : gen_cand
            logic signed [Q-1:0] llr;
            logic                llr_sign;
            logic [Q-1:0]        llr_abs;
            logic [M-1:0]        pm_curr;
            logic [M:0]          pen_sum;
            logic [M-1:0]        pm_pen;

            assign llr      = dec_llr_i[g];
            assign pm_curr  = pm_in_i[g];
            assign llr_sign = llr[Q-1];
            assign llr_abs  = (llr == LLR_MIN) ? LLR_MAX : (llr_sign ? -llr : llr);
            assign pen_sum  = {1'b0, pm_curr} + {{(M-Q+1){1'b0}}, llr_abs};
            assign pm_pen   = (pm_curr == PM_MAX) ? PM_MAX :
                              (pen_sum > {1'b0, PM_MAX}) ? PM_MAX : pen_sum[M-1:0];

            // Even candidate (2*g): u = 0
            assign cand_pm[2*g]       = (llr_sign == 1'b0) ? pm_curr : pm_pen;
            assign cand_parent[2*g]   = g[ID_W-1:0];
            assign cand_bit[2*g]      = 1'b0;

            // Odd candidate (2*g + 1): u = 1
            assign cand_pm[2*g+1]     = (llr_sign == 1'b1) ? pm_curr : pm_pen;
            assign cand_parent[2*g+1] = g[ID_W-1:0];
            assign cand_bit[2*g+1]    = 1'b1;
        end
    endgenerate

    // 2. Parallel Pairwise Rank Calculation (Fig. 4a: No sequential swaps!)
    // Candidate i's rank = number of candidates j that are strictly better than i
    // (or equal PM with smaller index j < i for deterministic tie-breaking).
    logic [$clog2(NUM_CAND)-1:0] rank [0:NUM_CAND-1];

    always_comb begin
        for (int i = 0; i < NUM_CAND; i++) begin
            rank[i] = '0;
            for (int j = 0; j < NUM_CAND; j++) begin
                if (i != j) begin
                    if ((cand_pm[j] < cand_pm[i]) || ((cand_pm[j] == cand_pm[i]) && (j < i))) begin
                        rank[i] = rank[i] + 1'b1;
                    end
                end
            end
        end
    end

    // 3. Output Crossbar Multiplexer (Selects candidates with rank 0 .. L-1)
    always_comb begin
        for (int l = 0; l < L; l++) begin
            pm_out_o[l]     = cand_pm[2*l];
            parent_idx_o[l] = l[ID_W-1:0];
            dec_bit_o[l]    = 1'b0;

            if (!is_frozen_i) begin
                for (int c = 0; c < NUM_CAND; c++) begin
                    if (rank[c] == l[$clog2(NUM_CAND)-1:0]) begin
                        pm_out_o[l]     = cand_pm[c];
                        parent_idx_o[l] = cand_parent[c];
                        dec_bit_o[l]    = cand_bit[c];
                    end
                end
            end
        end
    end

endmodule
