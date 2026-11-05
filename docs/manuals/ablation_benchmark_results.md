# Silicon Studio IDE V3.0 — Neuro-Symbolic Observability & Knowledge Base Benchmark Report

- **Generated At:** `2026-11-04T20:24:14`
- **Projects Audited:** `3`
- **Canary-Validated Knowledge Base Rules:** `21/21 (100% Pass)`

## 1. Neuro-Symbolic COI + Dual-Edge (`t` vs `t - 1ps`) Token Compression

| Project | Raw VCD (`wave.vcd`) | Full Table (`wave_full.md`) | COI Slice (`wave_slice.md`) | Reduction vs. Raw VCD | Reduction vs. Full Table | Signals (VCD → COI) | KB Rule Cited | Sign-Off Status |
| :--- | ---: | ---: | ---: | ---: | ---: | :---: | :--- | :--- |
| `async_fifo` | 7,937 tok (31,750 c) | 96,523 tok (386,094 c) | **436 tok** (1,746 c) | **+94.5%** | **+99.5%** | `51 → 10` | `—` | `VERIFIED` |
| `polar_scl_decoder` | 8,390 tok (33,561 c) | 33,509 tok (134,037 c) | **254 tok** (1,018 c) | **+97.0%** | **+99.2%** | `270 → 5` | `—` | `VERIFIED` |
| `programmable_pwm_timer` | 525 tok (2,103 c) | 2,700 tok (10,801 c) | **369 tok** (1,478 c) | **+29.7%** | **+86.3%** | `21 → 9` | `—` | `VERIFIED` |

## 2. Empirical Compiler-Canary Knowledge Base Verification

| Knowledge Domain | Compiler-Verified Rules | Validation Gate Applied | Runtime Token Footprint |
| :--- | ---: | :--- | :--- |
| `CDC` | 4 | Tier-1 Verilator `--lint-only -Wall` + Tier-2 Yosys `$dlatch` Audit | ~220 tokens/pull (`canary_spec` stripped) |
| `FSM` | 4 | Tier-1 Verilator `--lint-only -Wall` + Tier-2 Yosys `$dlatch` Audit | ~220 tokens/pull (`canary_spec` stripped) |
| `LINT` | 6 | Tier-1 Verilator `--lint-only -Wall` + Tier-2 Yosys `$dlatch` Audit | ~220 tokens/pull (`canary_spec` stripped) |
| `PPA` | 4 | Tier-1 Verilator `--lint-only -Wall` + Tier-2 Yosys `$dlatch` Audit | ~220 tokens/pull (`canary_spec` stripped) |
| `SDC` | 3 | Tier-1 Verilator `--lint-only -Wall` + Tier-2 Yosys `$dlatch` Audit | ~220 tokens/pull (`canary_spec` stripped) |
