// =============================================================================
// File       : scl_pkg.sv
// Description: Global parameters and types for LLR-based SCL Polar Decoder
// Reference  : Balatsoukas-Stimming et al., IEEE TSP 2015
// =============================================================================
package scl_pkg;

    // Code and Decoder Parameters (Default N=8, L=2, P=4 for fast verification)
    parameter int N     = 8;                // Block length (2^n)
    parameter int STAGES= $clog2(N);        // n = 3 stages
    parameter int L     = 2;                // List size
    parameter int P     = 4;                // Processing Elements per SC core (N/2)
    parameter int Q     = 6;                // LLR quantization bits (signed)
    parameter int M     = 8;                // Path Metric quantization bits (unsigned)

    // Saturation bounds for Q-bit signed LLR (-32 to +31)
    localparam signed [Q-1:0] LLR_MAX =  (1 <<< (Q-1)) - 1;
    localparam signed [Q-1:0] LLR_MIN = -(1 <<< (Q-1));
    localparam logic  [M-1:0] PM_MAX  = '1; // 8'hFF

    // Frozen Bit Mask for P(8,4): 1 = Frozen (i not in A), 0 = Info bit (i in A)
    // Bit 0 is LSB, Bit 7 is MSB: {u7=Info, u6=Info, u5=Info, u4=Frozen, u3=Info, u2=Frozen, u1=Frozen, u0=Frozen}
    localparam logic [0:N-1] FROZEN_MASK = 8'b1110_1000;

endpackage
