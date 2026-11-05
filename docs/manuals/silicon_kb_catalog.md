# Silicon Studio IDE V3.0 — Canary-Validated Knowledge Base Catalog

- **Generated At:** `2026-11-04T13:18:43`
- **Total Compiler-Verified Rules:** `21` across `5` domains
- **Authoritative Corpus Files Indexed:** `13` (`schema_factory/knowledge_factory/corpus/`)
- **Validation Gate:** Verilator Static Lint (`--lint-only -Wall -sv`) + Yosys RTLIL Latch Audit (`0 $dlatch`)

## 1. Summary Matrix by Domain

| Rule ID | Domain | Severity | Target Agent | Priority Tags ($w=10$) | Source Authority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`CDC-001-PULSE-SWALLOW`** | `cdc` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `pulse_swallowing`, `fast_to_slow`, `burst_pulse`, `toggle_handshake` | CummingsSNUG2008Boston_CDC.pdf (Section 5: Passing Control Pulses) |
| **`CDC-002-GRAY-FIFO-PTR`** | `cdc` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `gray_code`, `async_fifo`, `pointer_sync`, `multi_bit_bus` | CummingsSNUG2002SJ_FIFO1.pdf & cc_cdc_fifo_gray.sv |
| **`CDC-003-REQ-ACK-HANDSHAKE`** | `cdc` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `four_phase_handshake`, `req_ack`, `closed_loop_cdc`, `bus_transfer` | CummingsSNUG2008Boston_CDC.pdf (Section 7: Multi-Bit CDC Handshake) |
| **`CDC-004-SYNC-CONVERGENCE`** | `cdc` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `reconvergence`, `combinational_glitch_cdc`, `divergent_sync`, `reset_synchronizer` | CummingsSNUG2008Boston_CDC.pdf & snug03_reset_part_deux.pdf |
| **`FSM-001-SAFE-RECOVERY`** | `fsm` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `fsm_lockup`, `safe_state`, `deadlock`, `default_idle` | VerilogCodingStyle.md (lowRISC) & cummings-case-snug99.pdf |
| **`FSM-002-MEALY-GLITCH-OUT`** | `fsm` | `TIMING_HAZARD` | `@rtl-architect` | `mealy_glitch`, `registered_outputs`, `moore_output`, `control_strobe` | VerilogCodingStyle.md & CummingsSNUG2008Boston_CDC.pdf |
| **`FSM-003-TWO-BLOCK-STYLE`** | `fsm` | `SYNTHESIS_HAZARD` | `@rtl-architect` | `state_q_state_d`, `two_block_fsm`, `enum_encoding`, `sequential_separation` | VerilogCodingStyle.md (lowRISC State Machine Guidelines) |
| **`FSM-004-ONEHOT-DECODE`** | `fsm` | `QOR_DEGRADATION` | `@rtl-architect` | `onehot_fsm`, `fsm_critical_path`, `case_1b1`, `fast_state_decode` | cummings-case-snug99.pdf (One-Hot FSM Coding) |
| **`LINT-001-INFERRED-LATCH`** | `lint` | `SYNTHESIS_HAZARD` | `@rtl-architect` | `latch`, `inferred_latch`, `dlatch`, `incomplete_case` | VerilogCodingStyle.md (lowRISC) & warnings.rst (%Warning-LATCH) |
| **`LINT-002-WIDTH-TRUNC`** | `lint` | `SYNTHESIS_HAZARD` | `@rtl-architect` | `widthtrunc`, `widthexpand`, `width`, `bit_width_cast` | VerilogCodingStyle.md & warnings.rst (%Warning-WIDTHTRUNC / WIDTHEXPAND) |
| **`LINT-003-COMB-LOOP`** | `lint` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `unoptflat`, `combinational_loop`, `circular_feedback`, `zero_delay_oscillation` | warnings.rst (%Warning-UNOPTFLAT) & VerilogCodingStyle.md |
| **`LINT-004-BLKSEQ-ASSIGN`** | `lint` | `CRITICAL_SILICON_FAILURE` | `@rtl-architect` | `blkseq`, `blocking_in_sequential`, `non_blocking`, `sim_race_condition` | VerilogCodingStyle.md & warnings.rst (%Warning-BLKSEQ) |
| **`LINT-005-CASE-OVERLAP`** | `lint` | `SYNTHESIS_HAZARD` | `@rtl-architect` | `caseoverlap`, `caseincomplete`, `full_case`, `parallel_case` | cummings-case-snug99.pdf & warnings.rst (%Warning-CASEOVERLAP / CASEINCOMPLETE) |
| **`PPA-005-SVA-ASSERT-KNOWN`** | `lint` | `SYNTHESIS_HAZARD` | `@dv-debugger` | `x_z_anomalies`, `isunknown`, `assert_known`, `x_propagation` | prim_assert.sv (lowRISC OpenTitan) & DVCodingStyle.md |
| **`PPA-001-CRITICAL-PATH-LTP`** | `ppa` | `QOR_DEGRADATION` | `@synth-qor` | `critical_path`, `ltp_levels`, `logic_depth`, `priority_chain` | yosyshq-readthedocs-io-yosys-en-0.38.pdf (ltp & abc passes) |
| **`PPA-002-ARITH-RESOURCE-SHARE`** | `ppa` | `QOR_DEGRADATION` | `@synth-qor` | `resource_sharing`, `adder_mux`, `chip_area_um2`, `alu_sharing` | yosyshq-readthedocs-io-yosys-en-0.38.pdf (share & alumacc passes) |
| **`PPA-003-BITWIDTH-TRIMMING`** | `ppa` | `QOR_DEGRADATION` | `@synth-qor` | `bitwidth_trim`, `operator_sizing`, `transistor_count`, `datapath_width` | VerilogCodingStyle.md & yosyshq-readthedocs-io-yosys-en-0.38.pdf (wreduce) |
| **`PPA-004-DYNAMIC-TOGGLE-GATE`** | `ppa` | `QOR_DEGRADATION` | `@synth-qor` | `hamming_toggles`, `operand_isolation`, `clock_gating`, `switching_power` | VerilogCodingStyle.md & sim_engine.py |
| **`SDC-001-ASYNC-CLK-GROUPS`** | `sdc` | `TIMING_HAZARD` | `@synth-qor` | `set_clock_groups`, `asynchronous_clocks`, `cdc_sdc`, `clock_groups` | CummingsSNUG2008Boston_CDC.pdf & OpenLane base.sdc |
| **`SDC-002-MAX-DELAY-GRAY`** | `sdc` | `TIMING_HAZARD` | `@synth-qor` | `set_max_delay`, `datapath_only`, `gray_bus_skew`, `fifo_timing` | CummingsSNUG2002SJ_FIFO1.pdf & cc_cdc_fifo_gray.sv |
| **`SDC-003-QUASI-STATIC-FALSE`** | `sdc` | `TIMING_HAZARD` | `@synth-qor` | `set_false_path`, `reset_synchronizer`, `quasi_static`, `reset_recovery` | snug03_reset_part_deux.pdf & OpenLane base.sdc |

---

## 2. Detailed Rule Cards & Golden Templates

### Domain: `CDC`

#### `CDC-001-PULSE-SWALLOW` — Fast-to-slow clock domain single-cycle pulses must use a closed-loop toggle-handshake synchronizer with busy backpressure, never a direct 2-FF level synchronizer.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `CummingsSNUG2008Boston_CDC.pdf (Section 5: Passing Control Pulses)`
- **Priority Tags ($w=10$):** `pulse_swallowing`, `fast_to_slow`, `burst_pulse`, `toggle_handshake`, `toggle_synchronizer`, `dropped_pulse`
- **Hardware Rationale:** If destination clock period T_dst > source pulse width T_src, a single-cycle pulse in Domain A can assert and deassert completely between two rising edges of clkB, causing silent pulse loss. In burst mode, back-to-back pulses separated by less than 2*T_dst also coalesce unless a closed-loop busy_o handshake throttles the source FSM until the destination acknowledges receipt.
- **SDC Requirement:** `set_clock_groups -asynchronous -group [get_clocks clkA] -group [get_clocks clkB]`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Direct 2-FF synchronizer on fast single-cycle pulse drops pulses when T_dst > T_src
always_ff @(posedge clkB or negedge rst_n) begin
  if (!rst_n) {sync_q2, sync_q1} <= 2'b00;
  else        {sync_q2, sync_q1} <= {sync_q1, cmd_pulse_clkA};
end
assign pulse_out_clkB = sync_q2;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Closed-Loop Toggle-Handshake Pulse Synchronizer with Backpressure
assign busy_o = toggle_src_q ^ ack_src_q2;
always_ff @(posedge clkA or negedge rst_n) begin
  if (!rst_n) toggle_src_q <= 1'b0;
  else if (pulse_in_clkA && !busy_o) toggle_src_q <= ~toggle_src_q;
end
always_ff @(posedge clkB or negedge rst_n) begin
  if (!rst_n) {sync_dst_q3, sync_dst_q2, sync_dst_q1} <= 3'b000;
  else        {sync_dst_q3, sync_dst_q2, sync_dst_q1} <= {sync_dst_q2, sync_dst_q1, toggle_src_q};
end
assign pulse_out_clkB = sync_dst_q2 ^ sync_dst_q3;
always_ff @(posedge clkA or negedge rst_n) begin
  if (!rst_n) {ack_src_q2, ack_src_q1} <= 2'b00;
  else        {ack_src_q2, ack_src_q1} <= {ack_src_q1, sync_dst_q2};
end
```

#### `CDC-002-GRAY-FIFO-PTR` — Asynchronous FIFO read/write pointers must be converted to Gray code and registered in the source domain before passing through 2-FF synchronizers.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `CummingsSNUG2002SJ_FIFO1.pdf & cc_cdc_fifo_gray.sv`
- **Priority Tags ($w=10$):** `gray_code`, `async_fifo`, `pointer_sync`, `multi_bit_bus`, `wptr_gray`, `rptr_gray`, `wrap_flags`
- **Hardware Rationale:** Synchronizing a multi-bit binary counter directly across asynchronous clocks causes catastrophic pointer corruption because multiple bits flip simultaneously (e.g., 0111 -> 1000). Under interconnect skew and setup/hold metastability, the receiving domain samples a random combination of old and new bits. Gray code (bin ^ (bin >> 1)) guarantees unit Hamming distance (1 bit flip per increment).
- **SDC Requirement:** `set_max_delay -from [get_pins wptr_gray_q*/Q] -to [get_pins wq1_rptr*/D] -datapath_only [expr $T_wclk * 0.8]`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Passing multi-bit binary pointer directly into 2-FF synchronizer
always_ff @(posedge rclk or negedge rrst_n) begin
  if (!rrst_n) {wptr_bin_sync2, wptr_bin_sync1} <= '0;
  else         {wptr_bin_sync2, wptr_bin_sync1} <= {wptr_bin_sync1, wptr_bin_q};
end
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Binary-to-Gray conversion + source registration prior to 2-FF sync
assign wptr_bin_d  = wptr_bin_q + {{ADDR_W{1'b0}}, (winc_i && !wfull_o)};
assign wptr_gray_d = (wptr_bin_d >> 1) ^ wptr_bin_d;
always_ff @(posedge wclk or negedge wrst_n) begin
  if (!wrst_n) begin wptr_bin_q <= '0; wptr_gray_q <= '0; end
  else         begin wptr_bin_q <= wptr_bin_d; wptr_gray_q <= wptr_gray_d; end
end
always_ff @(posedge rclk or negedge rrst_n) begin
  if (!rrst_n) {wq2_rptr, wq1_rptr} <= '0;
  else         {wq2_rptr, wq1_rptr} <= {wq1_rptr, wptr_gray_q};
end
```

#### `CDC-003-REQ-ACK-HANDSHAKE` — Arbitrary multi-bit data buses crossing asynchronous domains must be held stable by the source register while a synchronized Req/Ack handshake completes.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `CummingsSNUG2008Boston_CDC.pdf (Section 7: Multi-Bit CDC Handshake)`
- **Priority Tags ($w=10$):** `four_phase_handshake`, `req_ack`, `closed_loop_cdc`, `bus_transfer`, `data_bus_cdc`
- **Hardware Rationale:** Non-Gray multi-bit data words cannot be synchronized bit-by-bit. Instead, the source domain must latch the data word into a holding register (data_hold_q), assert a request level/toggle, wait for the destination 2-FF synchronizer to detect the request edge and safely sample data_hold_q, and wait for the synchronized acknowledge before updating data_hold_q.
- **SDC Requirement:** `set_false_path -from [get_Cells data_hold_q*] -to [get_Cells data_out_q*]`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Sampling an asynchronous multi-bit data bus without holding it stable via Req/Ack
always_ff @(posedge clkB) begin
  data_sync_q <= async_data_clkA;
end
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Stable Holding Register + Synchronized Request Edge Sampling
always_ff @(posedge clkA or negedge rst_n) begin
  if (!rst_n) begin data_hold_q <= '0; req_tog_q <= 1'b0; end
  else if (send_en && !busy_o) begin data_hold_q <= data_in; req_tog_q <= ~req_tog_q; end
end
always_ff @(posedge clkB or negedge rst_n) begin
  if (!rst_n) begin {req_b3, req_b2, req_b1} <= 3'b000; data_out_q <= '0; end
  else begin
    {req_b3, req_b2, req_b1} <= {req_b2, req_b1, req_tog_q};
    if (req_b2 ^ req_b3) data_out_q <= data_hold_q;
  end
end
```

#### `CDC-004-SYNC-CONVERGENCE` — Never feed combinational logic directly into a 2-FF synchronizer or reconverge two independent 2-FF synchronizers in the destination domain.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `CummingsSNUG2008Boston_CDC.pdf & snug03_reset_part_deux.pdf`
- **Priority Tags ($w=10$):** `reconvergence`, `combinational_glitch_cdc`, `divergent_sync`, `reset_synchronizer`, `skew_violation`
- **Hardware Rationale:** Combinational logic in the source domain produces transient hazards/glitches during input transitions; feeding a combinational net directly into a synchronizer allows clkB to sample a glitch pulse. Always register the signal in the source domain (clkA) immediately before the CDC boundary, and coalesce control conditions before crossing.
- **SDC Requirement:** `set_clock_groups -asynchronous -group [get_clocks clkA] -group [get_clocks clkB]`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Combinational AND gate driving a 2-FF synchronizer directly
assign comb_trig = en_a & valid_a;
always_ff @(posedge clkB) {sync_q2, sync_q1} <= {sync_q1, comb_trig};
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Register combinational condition in source domain (clkA) before 2-FF sync
always_ff @(posedge clkA or negedge rst_n) begin
  if (!rst_n) src_launch_q <= 1'b0;
  else        src_launch_q <= en_a & valid_a;
end
always_ff @(posedge clkB or negedge rst_n) begin
  if (!rst_n) {sync_q2, sync_q1} <= 2'b00;
  else        {sync_q2, sync_q1} <= {sync_q1, src_launch_q};
end
```

### Domain: `FSM`

#### `FSM-001-SAFE-RECOVERY` — Every FSM next-state case statement must include an explicit default branch that returns state_d to ST_IDLE and deasserts outputs.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `VerilogCodingStyle.md (lowRISC) & cummings-case-snug99.pdf`
- **Priority Tags ($w=10$):** `fsm_lockup`, `safe_state`, `deadlock`, `default_idle`, `seu_recovery`, `caseincomplete`
- **Hardware Rationale:** When an N-bit state register implements K < 2^N valid states, radiation-induced Single-Event Upsets (SEU) or power-on reset glitches can flip state_q into an unenumerated state. Without an explicit default transition to ST_IDLE, the controller locks up permanently until a hard power cycle.
- **SDC Requirement:** `N/A (FSM Architectural Requirement)`

**Anti-Pattern (Violates Rule):**
```systemverilog
always_comb begin
  state_d = state_q;
  case (state_q) // Missing default branch (%Warning-CASEINCOMPLETE)!
    2'b00: if (go_i) state_d = 2'b01;
    2'b01: state_d = 2'b10;
    2'b10: state_d = 2'b00;
  endcase
end
```

**Golden Synthesizable Template:**
```systemverilog
typedef enum logic [1:0] {
  ST_IDLE = 2'b00,
  ST_BUSY = 2'b01,
  ST_DONE = 2'b10
} state_e;
state_e state_q, state_d;
always_comb begin
  state_d = state_q;
  case (state_q)
    ST_IDLE: if (go_i) state_d = ST_BUSY;
    ST_BUSY: state_d = ST_DONE;
    ST_DONE: state_d = ST_IDLE;
    default: state_d = ST_IDLE; // Safe deterministic recovery
  endcase
end
```

#### `FSM-002-MEALY-GLITCH-OUT` — FSM control strobes driving asynchronous boundaries, write enables, or downstream clocks must be Moore-registered or look-ahead registered to eliminate combinational glitches.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `TIMING_HAZARD`
- **Source Reference:** `VerilogCodingStyle.md & CummingsSNUG2008Boston_CDC.pdf`
- **Priority Tags ($w=10$):** `mealy_glitch`, `registered_outputs`, `moore_output`, `control_strobe`, `write_enable_glitch`
- **Hardware Rationale:** Combinational Mealy outputs depend on both state_q bits and external inputs. Because multi-bit state_q transitions have non-zero gate/wire skew, decoding logic can produce narrow sub-nanosecond hazard glitches that falsely trigger downstream FIFOs, memories, or CDC synchronizers.
- **SDC Requirement:** `N/A (Registered output maximizes downstream setup margin)`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Combinational Mealy decode prone to state-bit skew glitches
assign fifo_push_o = (state_q == ST_WRITE) && ready_i;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Registered look-ahead output driven by next-state (state_d)
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) fifo_push_q <= 1'b0;
  else         fifo_push_q <= (state_d == ST_WRITE);
end
assign fifo_push_o = fifo_push_q;
```

#### `FSM-003-TWO-BLOCK-STYLE` — Separate FSM sequential registers (state_q in always_ff) from combinational next-state logic (state_d in always_comb) so COI and pre-posedge (t-1ps) waveform tables can isolate transition bugs.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `SYNTHESIS_HAZARD`
- **Source Reference:** `VerilogCodingStyle.md (lowRISC State Machine Guidelines)`
- **Priority Tags ($w=10$):** `state_q_state_d`, `two_block_fsm`, `enum_encoding`, `sequential_separation`
- **Hardware Rationale:** Single-block FSMs (where next-state decoding and output assignments are buried inside a monolithic always_ff block) hide the combinational next-state net (state_d) from waveform inspection at t-1ps and often lead to accidental one-cycle pipeline latency mismatches on outputs.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Monolithic single-block FSM hides next-state signal from COI/waveform debug
always_ff @(posedge clk_i) begin
  case (state_q)
    ST_IDLE: if (req_i) state_q <= ST_ACK;
    ST_ACK:  state_q <= ST_IDLE;
  endcase
end
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Explicit 2-Block state_q / state_d architecture
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) state_q <= ST_IDLE;
  else         state_q <= state_d;
end
always_comb begin
  state_d = state_q;
  unique case (state_q)
    ST_IDLE: if (req_i) state_d = ST_ACK;
    ST_ACK:  state_d = ST_IDLE;
    default: state_d = ST_IDLE;
  endcase
end
```

#### `FSM-004-ONEHOT-DECODE` — Use one-hot state encodings with single-bit index comparisons when FSM decode delay dominates the critical path (ltp -noff).
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@synth-qor` | **Severity:** `QOR_DEGRADATION`
- **Source Reference:** `cummings-case-snug99.pdf (One-Hot FSM Coding)`
- **Priority Tags ($w=10$):** `onehot_fsm`, `fsm_critical_path`, `case_1b1`, `fast_state_decode`
- **Hardware Rationale:** Binary-encoded FSMs with many states require wide multi-bit equality comparators on every state branch, adding 2 to 4 levels of combinational gate delay before datapath muxes. One-hot encoding reduces state detection to a 1-bit wire tap.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// Wide binary state comparison on critical control path
assign mux_sel_o = (state_q == 5'd19) || (state_q == 5'd23);
```

**Golden Synthesizable Template:**
```systemverilog
// One-hot state bit indexing reduces comparator depth to 1 OR gate
assign mux_sel_o = state_onehot_q[ST_BIT_19] | state_onehot_q[ST_BIT_23];
```

### Domain: `LINT`

#### `LINT-001-INFERRED-LATCH` — Initialize all outputs and local variables at the top of always_comb before conditional branches to guarantee zero inferred latches ($dlatch).
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `SYNTHESIS_HAZARD`
- **Source Reference:** `VerilogCodingStyle.md (lowRISC) & warnings.rst (%Warning-LATCH)`
- **Priority Tags ($w=10$):** `latch`, `inferred_latch`, `dlatch`, `incomplete_case`, `missing_else`
- **Hardware Rationale:** When a signal assigned inside an always_comb block is not assigned a value on every possible execution path, Yosys and ASIC synthesis tools infer a level-sensitive transparent latch ($dlatch) to preserve the previous value. Latches introduce severe timing-borrowing race conditions, glitch propagation, and DFT scan untestability.
- **SDC Requirement:** `N/A (Pure RTL Structural Fix)`

**Anti-Pattern (Violates Rule):**
```systemverilog
always_comb begin
  if (en_i)
    y_o = data_i; // Missing else branch infers $dlatch!
end
```

**Golden Synthesizable Template:**
```systemverilog
always_comb begin
  y_o = '0; // Upfront default initialization guarantees purely combinational logic
  if (en_i) begin
    y_o = data_i;
  end
end
```

#### `LINT-002-WIDTH-TRUNC` — Use explicit SystemVerilog width casts (e.g., WIDTH'(expr)) and sized literals to eliminate implicit bit-width truncation and expansion warnings.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `SYNTHESIS_HAZARD`
- **Source Reference:** `VerilogCodingStyle.md & warnings.rst (%Warning-WIDTHTRUNC / WIDTHEXPAND)`
- **Priority Tags ($w=10$):** `widthtrunc`, `widthexpand`, `width`, `bit_width_cast`, `truncation`
- **Hardware Rationale:** Implicitly assigning a wider expression (such as an unsized integer literal 1 or an N+1 bit carry sum) to an N-bit target silently truncates MSBs, which can clip carry-outs, wrap array indices prematurely, and trigger Verilator WIDTHTRUNC/WIDTHEXPAND errors.
- **SDC Requirement:** `N/A (Pure RTL Structural Fix)`

**Anti-Pattern (Violates Rule):**
```systemverilog
logic [3:0] count_q;
always_ff @(posedge clk_i) count_q <= count_q + 1; // 32-bit unsized literal '1' causes WIDTHTRUNC!
```

**Golden Synthesizable Template:**
```systemverilog
logic [3:0] count_q;
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) count_q <= 4'd0;
  else         count_q <= count_q + 4'd1; // Explicit 4-bit sized literal
end
```

#### `LINT-003-COMB-LOOP` — Break circular combinational feedback loops (UNOPTFLAT) by registering the feedback state in an always_ff sequential element.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `warnings.rst (%Warning-UNOPTFLAT) & VerilogCodingStyle.md`
- **Priority Tags ($w=10$):** `unoptflat`, `combinational_loop`, `circular_feedback`, `zero_delay_oscillation`, `scc_loop`
- **Hardware Rationale:** A combinational signal that depends on itself without an intervening flip-flop forms an asynchronous ring oscillator or unstable bistable latch in silicon, preventing Verilator static scheduling (UNOPTFLAT), hanging event-driven simulators, and breaking static timing analysis.
- **SDC Requirement:** `N/A (Combinational loops are illegal in synchronous STA)`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Combinational net 'acc_w' feeds back into its own equation
assign acc_w = in_i ^ acc_w;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Break feedback loop with an explicit clock-driven register
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) acc_q <= 1'b0;
  else         acc_q <= in_i ^ acc_q;
end
```

#### `LINT-004-BLKSEQ-ASSIGN` — Never use blocking assignments (=) on sequential registers inside always_ff; strictly use non-blocking assignments (<=).
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `CRITICAL_SILICON_FAILURE`
- **Source Reference:** `VerilogCodingStyle.md & warnings.rst (%Warning-BLKSEQ)`
- **Priority Tags ($w=10$):** `blkseq`, `blocking_in_sequential`, `non_blocking`, `sim_race_condition`, `always_ff_assign`
- **Hardware Rationale:** Using blocking assignments (=) inside a clocked always_ff block causes the simulator to update the LHS variable in the Active region rather than the NBA (Non-Blocking Assignment) region. Any downstream sequential block reading that signal on the same clock edge will sample the post-edge value instead of the pre-edge value, creating a severe simulation-vs-synthesis mismatch.
- **SDC Requirement:** `N/A (Pure RTL Coding Standard)`

**Anti-Pattern (Violates Rule):**
```systemverilog
always_ff @(posedge clk_i) begin
  stage1_q = data_i;   // %Warning-BLKSEQ!
  stage2_q = stage1_q; // Collapses 2-stage pipeline into 1 stage!
end
```

**Golden Synthesizable Template:**
```systemverilog
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) begin
    stage1_q <= '0;
    stage2_q <= '0;
  end else begin
    stage1_q <= data_i;
    stage2_q <= stage1_q;
  end
end
```

#### `LINT-005-CASE-OVERLAP` — Avoid overlapping casez patterns and never use synopsys full_case/parallel_case pragmas; use explicit mutually exclusive branches with a default clause.
- **Target Agent:** `@rtl-architect` | **Verifier Agent:** `@dv-debugger` | **Severity:** `SYNTHESIS_HAZARD`
- **Source Reference:** `cummings-case-snug99.pdf & warnings.rst (%Warning-CASEOVERLAP / CASEINCOMPLETE)`
- **Priority Tags ($w=10$):** `caseoverlap`, `caseincomplete`, `full_case`, `parallel_case`, `casez_hazard`
- **Hardware Rationale:** Overlapping case items or synthesis pragmas (full_case / parallel_case) cause synthesis tools to optimize logic differently from how event-driven RTL simulators evaluate top-down case branches, producing catastrophic gate-level functional divergence.
- **SDC Requirement:** `N/A (Pure RTL Structural Fix)`

**Anti-Pattern (Violates Rule):**
```systemverilog
always_comb begin
  casez (req_i)
    2'b1?: grant_o = 2'b10;
    2'b?1: grant_o = 2'b01; // Overlaps with 2'b11 (%Warning-CASEOVERLAP)!
    default: grant_o = 2'b00;
  endcase
end
```

**Golden Synthesizable Template:**
```systemverilog
always_comb begin
  grant_o = 2'b00;
  casez (req_i)
    2'b1?:   grant_o = 2'b10;
    2'b01:   grant_o = 2'b01; // Disjoint pattern eliminates overlap
    default: grant_o = 2'b00;
  endcase
end
```

#### `PPA-005-SVA-ASSERT-KNOWN` — Guard valid control strobes and FSM state registers against X/Z unknown propagation after reset deassertion using !$isunknown() checks.
- **Target Agent:** `@dv-debugger` | **Verifier Agent:** `@rtl-architect` | **Severity:** `SYNTHESIS_HAZARD`
- **Source Reference:** `prim_assert.sv (lowRISC OpenTitan) & DVCodingStyle.md`
- **Priority Tags ($w=10$):** `x_z_anomalies`, `isunknown`, `assert_known`, `x_propagation`, `uninitialized_reg`
- **Hardware Rationale:** In 4-state SystemVerilog simulation, an uninitialized register or out-of-bounds array read evaluates to 'X'. In standard if (cond) blocks, 'X' takes the else branch (X-optimism), silently hiding hardware reset bugs unless caught by x_z_anomalies or ASSERT_KNOWN.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Unreset control valid register propagates X onto the bus
always_ff @(posedge clk_i) valid_q <= next_valid_d;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Asynchronous active-low reset on all control & FSM state flops
always_ff @(posedge clk_i or negedge rst_ni) begin
  if (!rst_ni) valid_q <= 1'b0;
  else         valid_q <= next_valid_d;
end
```

### Domain: `PPA`

#### `PPA-001-CRITICAL-PATH-LTP` — Replace deep serial priority chains and linear ripple comparators with balanced binary tree reductions to minimize Yosys ltp -noff critical path levels across Sky130, Nangate45, and ASAP7.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `QOR_DEGRADATION`
- **Source Reference:** `yosyshq-readthedocs-io-yosys-en-0.38.pdf (ltp & abc passes)`
- **Priority Tags ($w=10$):** `critical_path`, `ltp_levels`, `logic_depth`, `priority_chain`, `tree_reduction`, `ltp_noff`
- **Hardware Rationale:** Linearly cascaded priority multiplexers or ripple comparators synthesize into O(N) gate levels in Yosys ABC. Restructuring associative operations (min/max sorters, wide reductions, parallel muxes) into explicit balanced binary trees compresses combinational logic depth to O(log2 N).
- **SDC Requirement:** `N/A (Structural Datapath Optimization)`

**Anti-Pattern (Violates Rule):**
```systemverilog
// Serial ripple min-finder: 3 sequential comparator stages
assign m1 = (a < b) ? a : b;
assign m2 = (m1 < c) ? m1 : c;
assign min_o = (m2 < d) ? m2 : d;
```

**Golden Synthesizable Template:**
```systemverilog
// Balanced binary tree min-finder: 2 parallel comparator stages (reduces ltp -noff depth)
assign min_ab = (a < b) ? a : b;
assign min_cd = (c < d) ? c : d;
assign min_o  = (min_ab < min_cd) ? min_ab : min_cd;
```

#### `PPA-002-ARITH-RESOURCE-SHARE` — Mux operands before a single shared adder/subtractor rather than instantiating parallel arithmetic units followed by an output mux to reduce standard-cell area (chip_area_um2).
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `QOR_DEGRADATION`
- **Source Reference:** `yosyshq-readthedocs-io-yosys-en-0.38.pdf (share & alumacc passes)`
- **Priority Tags ($w=10$):** `resource_sharing`, `adder_mux`, `chip_area_um2`, `alu_sharing`, `area_reduction`
- **Hardware Rationale:** Instantiating separate adders in each branch of an if-else statement forces synthesis to build two full carry-propagate adders plus a wide bus multiplexer. Selecting the input operand via a 2:1 mux before a single adder cuts arithmetic silicon area nearly in half.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Two separate adders synthesized before output MUX
assign res_o = sel_i ? (base_i + offset_a_i) : (base_i + offset_b_i);
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Single shared adder with pre-multiplexed operand
wire [W-1:0] selected_offset = sel_i ? offset_a_i : offset_b_i;
assign res_o = base_i + selected_offset;
```

#### `PPA-003-BITWIDTH-TRIMMING` — Size datapath accumulators, loop counters, and LLR path metrics to the exact mathematical dynamic range ceiling ($\lceil\log_2(\text{MAX})\rceil$) rather than defaulting to 32-bit integers.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `QOR_DEGRADATION`
- **Source Reference:** `VerilogCodingStyle.md & yosyshq-readthedocs-io-yosys-en-0.38.pdf (wreduce)`
- **Priority Tags ($w=10$):** `bitwidth_trim`, `operator_sizing`, `transistor_count`, `datapath_width`, `wreduce`
- **Hardware Rationale:** Using 32-bit int/integer registers for counters or channel decoder path metrics that only span [0..63] wastes 26 flip-flops per register and inflates comparator/sorter trees by 5x in cell count and dynamic toggle power.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] 32-bit integer register used for a 0..7 bit index counter
int bit_idx_q;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Parameterized exact bit-width ($clog2(N))
localparam int IDX_W = $clog2(N_BITS);
logic [IDX_W-1:0] bit_idx_q;
```

#### `PPA-004-DYNAMIC-TOGGLE-GATE` — Gate combinational datapath inputs (operand isolation) and enable-gate output registers when a submodule is idle to minimize bit-level Hamming toggles in power_activity.json.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `QOR_DEGRADATION`
- **Source Reference:** `VerilogCodingStyle.md & sim_engine.py`
- **Priority Tags ($w=10$):** `hamming_toggles`, `operand_isolation`, `clock_gating`, `switching_power`, `toggle_power`
- **Hardware Rationale:** If a wide combinational sorter or ALU remains directly connected to toggling bus nets during FSM states where its output is ignored, every internal gate charges and discharges load capacitance unnecessarily, inflating total_bit_hamming_toggles.
- **SDC Requirement:** `N/A`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Wide sorter/adder toggles every cycle even when valid_i is 0
assign sum_o = data_a_i + data_b_i;
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Operand Isolation: force datapath inputs to 0 when unit is inactive
wire [7:0] iso_a = valid_i ? data_a_i : 8'd0;
wire [7:0] iso_b = valid_i ? data_b_i : 8'd0;
assign sum_o = iso_a + iso_b;
```

### Domain: `SDC`

#### `SDC-001-ASYNC-CLK-GROUPS` — Declare unrelated clock domains using set_clock_groups -asynchronous only after verifying that all boundary crossings have hardware CDC synchronizers.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@eda-lead` | **Severity:** `TIMING_HAZARD`
- **Source Reference:** `CummingsSNUG2008Boston_CDC.pdf & OpenLane base.sdc`
- **Priority Tags ($w=10$):** `set_clock_groups`, `asynchronous_clocks`, `cdc_sdc`, `clock_groups`, `multi_clock_sta`
- **Hardware Rationale:** Static Timing Analysis (STA) engines cannot meaningfully compute setup/hold slack between two clocks with an irrational or asynchronous phase relationship (e.g., 10.0ns vs 31.7ns). Applying set_clock_groups -asynchronous instructs STA to ignore cross-domain paths so synthesis does not waste buffer area trying to close unclosable paths.
- **SDC Requirement:** `set_clock_groups -asynchronous -group [get_clocks clkA] -group [get_clocks clkB]`

**Anti-Pattern (Violates Rule):**
```systemverilog
# [ANTI-PATTERN] Leaving asynchronous clocks unconstrained or using blanket set_false_path without clock groups
create_clock -name clkA -period 10.0 [get_ports clkA]
create_clock -name clkB -period 31.7 [get_ports clkB]
```

**Golden Synthesizable Template:**
```systemverilog
# [GOLDEN PATTERN] Master clock declarations + asynchronous clock group isolation
create_clock -name clkA -period 10.0 [get_ports clkA]
create_clock -name clkB -period 31.7 [get_ports clkB]
set_clock_groups -asynchronous -group [get_clocks clkA] -group [get_clocks clkB]
```

#### `SDC-002-MAX-DELAY-GRAY` — Constrain multi-bit Gray-code FIFO pointers with set_max_delay -datapath_only bounded to less than one source clock period to prevent multi-bit skew violations.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `TIMING_HAZARD`
- **Source Reference:** `CummingsSNUG2002SJ_FIFO1.pdf & cc_cdc_fifo_gray.sv`
- **Priority Tags ($w=10$):** `set_max_delay`, `datapath_only`, `gray_bus_skew`, `fifo_timing`, `pointer_skew`
- **Hardware Rationale:** Although Gray code changes only 1 bit per source clock cycle, if physical routing delay skew across the N pointer wires exceeds 1 source clock period (T_src), two sequential bit transitions from Cycle k and Cycle k+1 can arrive at the destination synchronizer simultaneously, defeating the Gray-code guarantee.
- **SDC Requirement:** `set_max_delay 8.0 -datapath_only -from [get_pins wptr_gray_q*/Q] -to [get_pins wq1_rptr*/D]`

**Anti-Pattern (Violates Rule):**
```systemverilog
# [ANTI-PATTERN] Using unrestricted set_false_path on a multi-bit Gray-code pointer bus allows arbitrary wire skew!
set_false_path -from [get_cells wptr_gray_q*] -to [get_cells wq1_rptr*]
```

**Golden Synthesizable Template:**
```systemverilog
# [GOLDEN PATTERN] Bound datapath routing delay across Gray pointer bits to <= 0.8 * T_src
set_max_delay 8.0 -datapath_only -from [get_pins wptr_gray_q*/Q] -to [get_pins wq1_rptr*/D]
```

#### `SDC-003-QUASI-STATIC-FALSE` — Synchronize asynchronous reset deassertion via a 2-FF reset bridge and apply set_false_path only to the asynchronous assertion pin.
- **Target Agent:** `@synth-qor` | **Verifier Agent:** `@rtl-architect` | **Severity:** `TIMING_HAZARD`
- **Source Reference:** `snug03_reset_part_deux.pdf & OpenLane base.sdc`
- **Priority Tags ($w=10$):** `set_false_path`, `reset_synchronizer`, `quasi_static`, `reset_recovery`, `arst_n`
- **Hardware Rationale:** While asynchronous reset assertion is timing-independent, asynchronous reset deassertion near an active clock edge violates flip-flop recovery time (t_rec), throwing registers into metastability. A 2-FF reset synchronizer asserts asynchronously and deasserts synchronously.
- **SDC Requirement:** `set_false_path -from [get_ports ext_rst_ni] -to [get_pins rst_sync_q*/CLR]`

**Anti-Pattern (Violates Rule):**
```systemverilog
// [ANTI-PATTERN] Feeding raw external pad reset directly into internal FSM flip-flops without a reset synchronizer
```

**Golden Synthesizable Template:**
```systemverilog
// [GOLDEN PATTERN] Asynchronous Assert, Synchronous Deassert Reset Bridge
always_ff @(posedge clk_i or negedge ext_rst_ni) begin
  if (!ext_rst_ni) {rst_sync_q2, rst_sync_q1} <= 2'b00;
  else             {rst_sync_q2, rst_sync_q1} <= {rst_sync_q1, 1'b1};
end
assign sys_rst_no = rst_sync_q2;
```

