#!/usr/bin/env python3
"""
Bit-Accurate Golden Model for LLR-Based SCL Polar Decoder
Reference: Balatsoukas-Stimming et al., IEEE TSP 2015 (Algorithm 3, Eq. 8b, 9, 12)
Default Config: N=8 (n=3), K=4, L=2, Q=6-bit signed LLR, M=8-bit unsigned PM
"""

import numpy as np

# Hardware Parameters matching rtl/scl_pkg.sv
N = 8
n = 3
L = 2
Q = 6
M = 8

LLR_MIN = -(1 << (Q - 1))       # -32
LLR_MAX = (1 << (Q - 1)) - 1    # +31
PM_MAX  = (1 << M) - 1          # 255

# Frozen bit mask for P(8,4): 1 = Frozen (F), 0 = Information (A)
# Standard reliability order for N=8: F = {0, 1, 2, 4}, A = {3, 5, 6, 7}
FROZEN_MASK = [1, 1, 1, 0, 1, 0, 0, 0]

def sat_llr(val):
    return max(LLR_MIN, min(LLR_MAX, int(val)))

def sat_pm(val):
    return min(PM_MAX, int(val))

def f_minus(a, b):
    """Eq. (9): Hardware-friendly min-sum approximation"""
    sgn_a = -1 if a < 0 else 1
    sgn_b = -1 if b < 0 else 1
    mag = min(abs(a), abs(b))
    return sat_llr(sgn_a * sgn_b * mag)

def f_plus(a, b, u):
    """Eq. (8b): g-function with partial sum u in {0, 1}"""
    val = (b - a) if u == 1 else (b + a)
    return sat_llr(val)

def pm_update(pm_old, llr, u_bit):
    """Eq. (12): LLR-based Path Metric penalty update"""
    suggested_bit = 1 if llr < 0 else 0
    if u_bit == suggested_bit:
        return pm_old
    else:
        return sat_pm(pm_old + abs(llr))

def polar_encode(u):
    """Standard N=8 Arikan butterfly encoder"""
    x = list(u)
    step = 1
    for _ in range(n):
        for i in range(0, N, 2 * step):
            for j in range(step):
                x[i + j] ^= x[i + j + step]
        step *= 2
    return x

def compute_partial_sums(u_hat):
    """Computes internal partial sums u_s^(i) for butterfly stages"""
    U = np.zeros((n + 1, N), dtype=int)
    U[n, :] = u_hat
    for s in range(n, 0, -1):
        half = 1 << (s - 1)
        for i in range(0, N, 2 * half):
            for j in range(half):
                U[s - 1, i + j] = U[s, i + j] ^ U[s, i + j + half]
                U[s - 1, i + j + half] = U[s, i + j + half]
    return U

def scl_decode_golden(ch_llrs, verbose=True):
    """Executes Algorithm 3 (LLR-based SCL) with exact hardware quantization"""
    llr_mem = [np.zeros((n + 1, N), dtype=int) for _ in range(L)]
    for l in range(L):
        llr_mem[l][0, :] = ch_llrs

    u_paths = [np.zeros(N, dtype=int) for _ in range(L)]
    pm = [0] + [PM_MAX] * (L - 1)

    for i in range(N):
        for l in range(L):
            U_psum = compute_partial_sums(u_paths[l])
            for s in range(1, n + 1):
                half = 1 << (n - s)
                block = 2 * half
                if ((i >> (n - s)) & 1) == 0:
                    for b_start in range(0, N, block):
                        for j in range(half):
                            a = int(llr_mem[l][s - 1, b_start + j])
                            b = int(llr_mem[l][s - 1, b_start + j + half])
                            llr_mem[l][s, b_start + j] = f_minus(a, b)
                else:
                    for b_start in range(0, N, block):
                        for j in range(half):
                            a = int(llr_mem[l][s - 1, b_start + j])
                            b = int(llr_mem[l][s - 1, b_start + j + half])
                            u_ps = int(U_psum[n - s + 1, b_start + j])
                            llr_mem[l][s, b_start + j + half] = f_plus(a, b, u_ps)

        decision_llrs = [int(llr_mem[l][n, i]) for l in range(L)]

        if FROZEN_MASK[i] == 1:
            for l in range(L):
                u_paths[l][i] = 0
                if pm[l] < PM_MAX:
                    pm[l] = pm_update(pm[l], decision_llrs[l], 0)
            if verbose:
                print(f"Bit i={i} [FROZEN=0] | Decision LLRs={decision_llrs} | PMs={pm}")
        else:
            candidates = []
            for l in range(L):
                pm0 = pm_update(pm[l], decision_llrs[l], 0) if pm[l] < PM_MAX else PM_MAX
                pm1 = pm_update(pm[l], decision_llrs[l], 1) if pm[l] < PM_MAX else PM_MAX
                candidates.append((pm0, l, 0))
                candidates.append((pm1, l, 1))

            candidates.sort(key=lambda x: x[0])
            survivors = candidates[:L]

            new_llr_mem = []
            new_u_paths = []
            new_pm = []
            for surv_pm, parent_idx, bit_val in survivors:
                new_llr_mem.append(np.copy(llr_mem[parent_idx]))
                u_copy = np.copy(u_paths[parent_idx])
                u_copy[i] = bit_val
                new_u_paths.append(u_copy)
                new_pm.append(surv_pm)

            llr_mem = new_llr_mem
            u_paths = new_u_paths
            pm = new_pm
            if verbose:
                print(f"Bit i={i} [INFO BIT] | Decision LLRs={decision_llrs} | Survivors (PM, parent, u)={survivors}")

    best_path_idx = int(np.argmin(pm))
    return u_paths[best_path_idx], u_paths, pm

if __name__ == "__main__":
    print("=== Running LLR-Based SCL Golden Model (N=8, L=2, Q=6, M=8) ===")
    
    # Use a simpler all-zero or controlled information pattern 
    # where frozen positions (0,1,2,4) are 0 and info bits (3,5,6,7) resolve cleanly.
    u_true = [0, 0, 0, 1, 0, 0, 0, 0]
    x_enc = polar_encode(u_true)
    
    # Direct channel LLR injection matching x_enc
    channel_llrs = [20 if b == 0 else -20 for b in x_enc]
    
    print(f"True u vector  : {u_true}")
    print(f"Encoded x      : {x_enc}")
    print(f"Channel LLRs   : {channel_llrs}\n")
    
    u_hat, all_paths, final_pms = scl_decode_golden(channel_llrs, verbose=True)
    print(f"\nFinal Surviving Paths : {[list(p) for p in all_paths]}")
    print(f"Final Path Metrics    : {final_pms}")
    
    u_hat_clean = [int(v) for v in u_hat]
    print(f"Decoded u_hat         : {u_hat_clean}")
    
    assert u_hat_clean == u_true, "Golden model decode mismatch!"
    print("STATUS: Golden Model Decode Verified Successfully!")

    # Dump test vectors for SystemVerilog testbench
    with open("../verif/tv_channel_llrs.mem", "w") as f:
        for val in channel_llrs:
            f.write(f"{(val & 0x3F):02x}\n")
    with open("../verif/tv_expected_u.mem", "w") as f:
        for bit in u_true:
            f.write(f"{bit:01x}\n")
