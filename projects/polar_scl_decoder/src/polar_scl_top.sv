// =============================================================================
// File       : polar_scl_top.sv
// Description: Synthesizable Top-Level LLR-Based SCL Polar Decoder
// =============================================================================
module polar_scl_top (
    input  logic                       clk,
    input  logic                       rst_n,
    input  logic                       start_i,
    input  logic signed [scl_pkg::N-1:0][scl_pkg::Q-1:0] channel_llr_i,
    output logic                       done_o,
    output logic        [scl_pkg::N-1:0] decoded_u_o,
    output logic        [scl_pkg::M-1:0] best_pm_o
);

    localparam int N = scl_pkg::N;
    localparam int STAGES = scl_pkg::STAGES;
    localparam int L = scl_pkg::L;
    localparam int P = scl_pkg::P;
    localparam int Q = scl_pkg::Q;
    localparam int M = scl_pkg::M;
    localparam logic [0:N-1] FROZEN_MASK = scl_pkg::FROZEN_MASK;
    localparam logic [M-1:0] PM_MAX = scl_pkg::PM_MAX;

    localparam int ID_W = $clog2(L);
    localparam int STG_W = $clog2(STAGES+1);
    localparam int IDX_W = $clog2(N);

    // -------------------------------------------------------------------------
    // Synthesizable Flattened Register Banks
    // -------------------------------------------------------------------------
    logic signed [N-1:0][Q-1:0] ch_llr_mem;
    
    logic signed [N-1:0][Q-1:0] llr_stg1 [0:L-1];
    logic signed [N-1:0][Q-1:0] llr_stg2 [0:L-1];
    logic signed [N-1:0][Q-1:0] llr_stg3 [0:L-1];

    logic [ID_W-1:0] ptr_stg1 [0:L-1];
    logic [ID_W-1:0] ptr_stg2 [0:L-1];
    logic [ID_W-1:0] ptr_stg3 [0:L-1];

    logic [N-1:0]    path_mem [0:L-1];
    logic [M-1:0]    pm_reg   [0:L-1];
    logic [3:0]      crc_reg  [0:L-1];

    // -------------------------------------------------------------------------
    // Control FSM States & Counters
    // -------------------------------------------------------------------------
    typedef enum logic [2:0] {
        ST_IDLE        = 3'd0,
        ST_STAGE_CALC  = 3'd1,
        ST_METRIC_SORT = 3'd2,
        ST_SELECT_OUT  = 3'd3,
        ST_DONE        = 3'd4
    } state_e;

    state_e               state_q;
    logic [IDX_W-1:0]     bit_idx_q; // 0 .. 7
    logic [STG_W-1:0]     stage_q;   // 1 .. 3

    // -------------------------------------------------------------------------
    // Partial Sum Network
    // -------------------------------------------------------------------------
    logic [N-1:0] u_s3 [0:L-1];
    logic [N-1:0] u_s2 [0:L-1];
    logic [N-1:0] u_s1 [0:L-1];

    genvar pl;
    generate
        for (pl = 0; pl < L; pl++) begin : gen_psum_net
            assign u_s3[pl] = path_mem[pl];

            for (genvar b = 0; b < N; b += 2) begin : stg2_xor
                assign u_s2[pl][b]   = u_s3[pl][b] ^ u_s3[pl][b+1];
                assign u_s2[pl][b+1] = u_s3[pl][b+1];
            end

            for (genvar b = 0; b < N; b += 4) begin : stg1_xor
                for (genvar j = 0; j < 2; j++) begin : stg1_inner
                    assign u_s1[pl][b+j]   = u_s2[pl][b+j] ^ u_s2[pl][b+j+2];
                    assign u_s1[pl][b+j+2] = u_s2[pl][b+j+2];
                end
            end
        end
    endgenerate

    // -------------------------------------------------------------------------
    // MCU: L Parallel SC Cores
    // -------------------------------------------------------------------------
    logic signed [P-1:0][Q-1:0] core_alpha   [0:L-1];
    logic signed [P-1:0][Q-1:0] core_beta    [0:L-1];
    logic        [P-1:0]        core_u_psum  [0:L-1];
    logic                       core_func_sel;
    logic signed [P-1:0][Q-1:0] core_llr_out [0:L-1];

    // Explicit cast to 1-bit to avoid WIDTHTRUNC
    assign core_func_sel = 1'( (bit_idx_q >> (STG_W'(STAGES) - stage_q)) & 1'b1 );

    always_comb begin
        for (int l = 0; l < L; l++) begin
            core_alpha[l]  = '0;
            core_beta[l]   = '0;
            core_u_psum[l] = '0;

            case (stage_q)
                2'd1: begin
                    for (int k = 0; k < P; k++) begin
                        core_alpha[l][k]  = ch_llr_mem[k];
                        core_beta[l][k]   = ch_llr_mem[k + 4];
                        core_u_psum[l][k] = u_s1[l][k];
                    end
                end
                2'd2: begin
                    for (int b = 0; b < 2; b++) begin
                        for (int j = 0; j < 2; j++) begin
                            core_alpha[l][2*b+j]  = llr_stg1[ptr_stg1[l]][4*b + j];
                            core_beta[l][2*b+j]   = llr_stg1[ptr_stg1[l]][4*b + j + 2];
                            core_u_psum[l][2*b+j] = u_s2[l][4*b + j];
                        end
                    end
                end
                default: begin
                    for (int k = 0; k < P; k++) begin
                        core_alpha[l][k]  = llr_stg2[ptr_stg2[l]][2*k];
                        core_beta[l][k]   = llr_stg2[ptr_stg2[l]][2*k + 1];
                        core_u_psum[l][k] = u_s3[l][2*k];
                    end
                end
            endcase
        end
    end

    genvar l_idx;
    generate
        for (l_idx = 0; l_idx < L; l_idx++) begin : gen_mcu_cores
            sc_core u_sc_core (
                .alpha_vec_i  (core_alpha[l_idx]),
                .beta_vec_i   (core_beta[l_idx]),
                .u_psum_vec_i (core_u_psum[l_idx]),
                .func_sel_i   (core_func_sel),
                .llr_vec_o    (core_llr_out[l_idx])
            );
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Metric Sorter Unit Instantiation
    // -------------------------------------------------------------------------
    logic        [L-1:0][M-1:0]  pm_in_packed;
    logic signed [L-1:0][Q-1:0]  decision_llrs;
    logic                        is_frozen_bit;
    logic        [L-1:0][M-1:0]  sorted_pm;
    logic        [L-1:0][ID_W-1:0] sorted_parent;
    logic        [L-1:0]         sorted_bit;

    assign is_frozen_bit = FROZEN_MASK[bit_idx_q];

    always_comb begin
        logic [ID_W-1:0] phys_bank;
        phys_bank = '0;
        for (int l = 0; l < L; l++) begin
            pm_in_packed[l]  = pm_reg[l];
            phys_bank        = ptr_stg3[l];
            decision_llrs[l] = llr_stg3[phys_bank][bit_idx_q];
        end
    end

    metric_sorter u_metric_sorter (
        .pm_in_i      (pm_in_packed),
        .dec_llr_i    (decision_llrs),
        .is_frozen_i  (is_frozen_bit),
        .pm_out_o     (sorted_pm),
        .parent_idx_o (sorted_parent),
        .dec_bit_o    (sorted_bit)
    );

    // -------------------------------------------------------------------------
    // Sequential Control FSM
    // -------------------------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q     <= ST_IDLE;
            bit_idx_q   <= '0;
            stage_q     <= 2'd1;
            done_o      <= 1'b0;
            decoded_u_o <= '0;
            best_pm_o   <= '0;
            ch_llr_mem  <= '0;
            for (int l = 0; l < L; l++) begin
                llr_stg1[l] <= '0;
                llr_stg2[l] <= '0;
                llr_stg3[l] <= '0;
                ptr_stg1[l] <= '0;
                ptr_stg2[l] <= '0;
                ptr_stg3[l] <= '0;
                path_mem[l] <= '0;
                pm_reg[l]   <= '0;
                crc_reg[l]  <= '0;
            end
        end else begin
            case (state_q)
                ST_IDLE: begin
                    done_o <= 1'b0;
                    if (start_i) begin
                        ch_llr_mem <= channel_llr_i;
                        bit_idx_q  <= '0;
                        stage_q    <= 2'd1;
                        pm_reg[0]  <= '0;
                        for (int l = 1; l < L; l++) begin
                            pm_reg[l] <= PM_MAX;
                        end
                        for (int l = 0; l < L; l++) begin
                            crc_reg[l] <= '0;
                            path_mem[l] <= '0;
                            ptr_stg1[l] <= l[ID_W-1:0];
                            ptr_stg2[l] <= l[ID_W-1:0];
                            ptr_stg3[l] <= l[ID_W-1:0];
                        end
                        state_q <= ST_STAGE_CALC;
                    end
                end

                ST_STAGE_CALC: begin

                    for (int l = 0; l < L; l++) begin
                        case (stage_q)
                            2'd1: begin
                                for (int k = 0; k < P; k++) begin
                                    if (!core_func_sel) llr_stg1[l][k]     <= core_llr_out[l][k];
                                    else                llr_stg1[l][k + 4] <= core_llr_out[l][k];
                                end
                                ptr_stg1[l] <= l[ID_W-1:0];
                            end
                            2'd2: begin
                                for (int b = 0; b < 2; b++) begin
                                    for (int j = 0; j < 2; j++) begin
                                        if (!core_func_sel) llr_stg2[l][4*b + j]     <= core_llr_out[l][2*b+j];
                                        else                llr_stg2[l][4*b + j + 2] <= core_llr_out[l][2*b+j];
                                    end
                                end
                                ptr_stg2[l] <= l[ID_W-1:0];
                            end
                            default: begin
                                for (int k = 0; k < P; k++) begin
                                    if (!core_func_sel) llr_stg3[l][2*k]     <= core_llr_out[l][k];
                                    else                llr_stg3[l][2*k + 1] <= core_llr_out[l][k];
                                end
                                ptr_stg3[l] <= l[ID_W-1:0];
                            end
                        endcase
                    end

                    if (stage_q == STG_W'(STAGES)) begin
                        state_q <= ST_METRIC_SORT;
                    end else begin
                        stage_q <= stage_q + 2'd1;
                    end
                end

                ST_METRIC_SORT: begin
                    for (int l = 0; l < L; l++) begin
                        pm_reg[l]   <= sorted_pm[l];
                        ptr_stg1[l] <= ptr_stg1[sorted_parent[l]];
                        ptr_stg2[l] <= ptr_stg2[sorted_parent[l]];
                        ptr_stg3[l] <= ptr_stg3[sorted_parent[l]];

                        for (int b = 0; b < N; b++) begin
                            if (IDX_W'(b) == bit_idx_q)
                                path_mem[l][b] <= sorted_bit[l];
                            else
                                path_mem[l][b] <= path_mem[sorted_parent[l]][b];
                        end

                        if (!is_frozen_bit) begin
                            crc_reg[l] <= {crc_reg[sorted_parent[l]][2:0], 1'b0} ^
                                          ((crc_reg[sorted_parent[l]][3] ^ sorted_bit[l]) ? 4'b0011 : 4'b0000);
                        end else begin
                            crc_reg[l] <= crc_reg[sorted_parent[l]];
                        end
                    end

                    if (bit_idx_q == IDX_W'(N - 1)) begin
                        state_q <= ST_SELECT_OUT;
                    end else begin
                        bit_idx_q <= bit_idx_q + 1'b1;
                        stage_q   <= 2'd1;
                        state_q   <= ST_STAGE_CALC;
                    end
                end

                ST_SELECT_OUT: begin
                    decoded_u_o <= path_mem[0];
                    best_pm_o   <= pm_reg[0];
                    done_o      <= 1'b1;
                    state_q     <= ST_DONE;
                end

                ST_DONE: begin
                    state_q <= ST_IDLE;
                end

                default: state_q <= ST_IDLE;
            endcase
        end
    end

endmodule
