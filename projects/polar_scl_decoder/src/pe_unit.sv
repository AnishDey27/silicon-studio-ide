// =============================================================================
// File       : pe_unit.sv
// Description: Processing Element implementing hardware-friendly Min-Sum f_minus
//              (Eq. 9) and g / f_plus (Eq. 8b) in Q-bit two's complement.
// =============================================================================
module pe_unit (
    input  logic signed [scl_pkg::Q-1:0] alpha_i,    // Upper input LLR
    input  logic signed [scl_pkg::Q-1:0] beta_i,     // Lower input LLR
    input  logic                u_psum_i,   // Partial sum bit for f_plus
    input  logic                func_sel_i, // 0: f_minus (Eq. 9), 1: f_plus (Eq. 8b)
    output logic signed [scl_pkg::Q-1:0] llr_o       // Output LLR
);
    localparam int Q = scl_pkg::Q;
    localparam logic signed [Q-1:0] LLR_MAX = scl_pkg::LLR_MAX;
    localparam logic signed [Q-1:0] LLR_MIN = scl_pkg::LLR_MIN;

    // -------------------------------------------------------------------------
    // 1. f_minus: sign(alpha)*sign(beta)*min(|alpha|, |beta|) (Eq. 9)
    // -------------------------------------------------------------------------
    logic                sign_a, sign_b, sign_f;
    logic [Q-1:0]        abs_a, abs_b, min_abs;
    logic signed [Q-1:0] f_minus_val;

    assign sign_a  = alpha_i[Q-1];
    assign sign_b  = beta_i[Q-1];
    assign sign_f  = sign_a ^ sign_b;

    // Clamp LLR_MIN (-32) to +31 before taking magnitude to prevent overflow
    assign abs_a   = (alpha_i == LLR_MIN) ? LLR_MAX : (sign_a ? -alpha_i : alpha_i);
    assign abs_b   = (beta_i  == LLR_MIN) ? LLR_MAX : (sign_b ? -beta_i  : beta_i);
    assign min_abs = (abs_a < abs_b) ? abs_a : abs_b;

    assign f_minus_val = sign_f ? -$signed(min_abs) : $signed(min_abs);

    // -------------------------------------------------------------------------
    // 2. f_plus (g-node): (-1)^u * alpha + beta (Eq. 8b) with Q-bit saturation
    // -------------------------------------------------------------------------
    logic signed [Q:0]   sum_ext;
    logic signed [Q-1:0] f_plus_val;

    always_comb begin
        if (u_psum_i == 1'b0)
            sum_ext = $signed(beta_i) + $signed(alpha_i);
        else
            sum_ext = $signed(beta_i) - $signed(alpha_i);

        // Symmetric saturation to [LLR_MIN, LLR_MAX]
        if (sum_ext > $signed({1'b0, LLR_MAX}))
            f_plus_val = LLR_MAX;
        else if (sum_ext < $signed({1'b1, LLR_MIN}))
            f_plus_val = LLR_MIN;
        else
            f_plus_val = sum_ext[Q-1:0];
    end

    // Output Mux
    assign llr_o = func_sel_i ? f_plus_val : f_minus_val;

endmodule
