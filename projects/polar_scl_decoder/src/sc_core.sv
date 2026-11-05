// =============================================================================
// File       : sc_core.sv
// Description: Instantiates P Processing Elements (PEs) for 1 path in the MCU
// Reference  : Section IV-B of Balatsoukas-Stimming et al., IEEE TSP 2015
// =============================================================================
module sc_core (
    input  logic signed [scl_pkg::P-1:0][scl_pkg::Q-1:0] alpha_vec_i,
    input  logic signed [scl_pkg::P-1:0][scl_pkg::Q-1:0] beta_vec_i,
    input  logic        [scl_pkg::P-1:0]                 u_psum_vec_i,
    input  logic                       func_sel_i,   // 0: f_minus, 1: f_plus
    output logic signed [scl_pkg::P-1:0][scl_pkg::Q-1:0] llr_vec_o
);
    localparam int P = scl_pkg::P;

    genvar p;
    generate
        for (p = 0; p < P; p++) begin : gen_pe_array
            pe_unit u_pe (
                .alpha_i    (alpha_vec_i[p]),
                .beta_i     (beta_vec_i[p]),
                .u_psum_i   (u_psum_vec_i[p]),
                .func_sel_i (func_sel_i),
                .llr_o      (llr_vec_o[p])
            );
        end
    endgenerate

endmodule
