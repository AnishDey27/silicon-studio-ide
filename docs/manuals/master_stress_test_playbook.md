# Silicon Studio IDE V3.0 — 24-Prompt Plain-English Sequential Stress-Test Suite

This playbook is designed to be executed **sequentially from Prompt 1 to Prompt 24 in a single GitHub Copilot Chat session** while watching `http://127.0.0.1:8080` side-by-side.

Notice how **every prompt uses short, natural, everyday English**—no long technical instructions or tool-name babysitting required! Your updated `.github/copilot-instructions.md`, `.agent.md` personas, and 6 self-invoking `.prompt.md` skills automatically handle all tool routing, strict `1.Hier -> 2.Lint -> 3.Sim -> 4.Synth` gating, COI debugging, and Knowledge Base pulls in the background.

---

## Pre-Flight Check (Run Once Before Starting Chat)
1. Ensure your localhost server is running (`powershell -ExecutionPolicy Bypass -File .\scripts\start_studio.ps1`) and open **`http://127.0.0.1:8080`**.
2. In VS Code, press `Ctrl+Shift+P` $\rightarrow$ **`MCP: List Servers`** $\rightarrow$ restart **`silicon-studio-mcp`** so it loads the latest backend state manager.

---

## Phase 1: Workspace Audit & Step-by-Step Flow on `async_fifo` (Prompts 1–5)

### Prompt 1 — Natural-Language Workspace & PDK Check
> ```text
> @eda-lead Check what projects and synthesis PDK targets we have available in the workspace, and verify that our Yosys tool schema is loaded.
> ```
* **What to watch on `http://127.0.0.1:8080`:** Confirms `async_fifo` and `polar_scl_decoder` are discovered and `sky130`, `nangate45`, and `asap7` Liberty `.lib` files resolve cleanly without polluting any project's execution log.

### Prompt 2 — Step 1: RTL & Lint Only on `async_fifo` (`@rtl-architect`)
> ```text
> @rtl-architect Switch to async_fifo and run the RTL hierarchy and lint checks.
> ```
* **What to watch:** Top navbar dropdown automatically switches to **`async_fifo`**. Pipeline pills **`1.Hier`** and **`2.Lint`** turn solid emerald green (`PASS`). `3.Sim` and `4.Synth` remain pending.

### Prompt 3 — Step 2: Test the Strict Pipeline Sequence Guard (Intentional Out-of-Order Attempt!)
> ```text
> @synth-qor Try running synthesis on async_fifo right now before simulation has been run, and tell me what the state machine says.
> ```
* **What to watch:** Proves your new **Strict Sequence State Machine (`1.Hier -> 2.Lint -> 3.Sim -> 4.Synth`)** works! The backend blocks `run_yosys_synthesis` with `BLOCKED_SEQUENCE_VIOLATION` because `3.Sim` has not passed yet.

### Prompt 4 — Step 3: DV Simulation Only on `async_fifo` (`@dv-debugger`)
> ```text
> @dv-debugger Run simulation on async_fifo and give me the switching power summary.
> ```
* **What to watch:** Pipeline pill **`3.Sim`** turns green (`PASS`), Tab 2 WaveDrom diagram populates (with static uppercase parameters stripped out), and notice **`🔍 COI` does NOT appear** in the pipeline bar because simulation passed!

### Prompt 5 — Step 4: Multi-PDK Synthesis, Schematics & Sign-Off on `async_fifo` (`@synth-qor`)
> ```text
> @synth-qor Now run multi-PDK synthesis across sky130, nangate45, and asap7 for async_fifo, generate the schematics, and post the tapeout sign-off ticket.
> ```
* **What to watch:** Pipeline pill **`4.Synth`** turns green (`1.Hier → 2.Lint → 3.Sim → 4.Synth` all green!). Tab 1 shows `Top RTL (async_fifo)` schematic, Tab 3 shows the 3 visual area bars (`ASAP7`, `NANGATE45`, `SKY130`) + gate netlists, and `TICKET-001` appears in the central topology stack.

---

## Phase 2: Step-by-Step Flow on Complex Multi-Module `polar_scl_decoder` (Prompts 6–9)

### Prompt 6 — Step 1: RTL & Package-First Hierarchy on `polar_scl_decoder`
> ```text
> @rtl-architect Switch to polar_scl_decoder and check its hierarchy and Verilator lint.
> ```
* **What to watch:** Dropdown switches to **`polar_scl_decoder`**. Its Execution Log and Ticket Drawer are 100% isolated from `async_fifo`. Tab 1 shows `1. scl_pkg.sv` first in the compile order, and `1.Hier` + `2.Lint` turn green.

### Prompt 7 — Step 2: Dynamic Simulation on `polar_scl_decoder`
> ```text
> @dv-debugger Run simulation on polar_scl_decoder and verify all golden memory vectors pass.
> ```
* **What to watch:** `3.Sim` turns green (`PASS`), proving relative `$fopen("../verif/*.mem")` vectors load cleanly from `projects/polar_scl_decoder/build/`.

### Prompt 8 — Step 3: Multi-PDK Synthesis & Submodule Schematics on `polar_scl_decoder`
> ```text
> @synth-qor Synthesize polar_scl_decoder across sky130, nangate45, and asap7, render all module schematics, and post the tapeout sign-off ticket.
> ```
* **What to watch:** `4.Synth` turns green. In Tab 1, you can click through `Top RTL (polar_scl_top)`, `metric_sorter`, `pe_unit`, and `sc_core` schematics.

### Prompt 9 — Test Optional COI Waveform Slicing on Demand
> ```text
> @dv-debugger Slice the COI waveform for decoded_bits_o in polar_scl_decoder around 205ns so I can inspect the t vs t-1ps setup table.
> ```
* **What to watch:** Now the optional **`🔍 COI`** badge lights up next to `4.Synth`, and Tab 2 right pane displays **Table 1 (`Post-Posedge at t`)** and **Table 2 (`Pre-Posedge Setup at t - 1ps`)** with `[t0] 205ns` highlighted in amber.

---

## Phase 3: Cross-Project Interleaving & Cascading Invalidation Torture Test (Prompts 10–14)

### Prompt 10 — Interleaved Cross-Project Action (RTL on Project A, Sim on Project B)
> ```text
> @rtl-architect Re-run resolve_project_hierarchy on async_fifo only, and tell me which downstream stages got invalidated.
> ```
* **What to watch:** Switching to `async_fifo` and re-running `1.Hier` immediately marks **`2.Lint (STALE)`**, **`3.Sim (STALE)`**, and **`4.Synth (STALE)`** with amber strikethrough pills—proving cascading downstream invalidation!

### Prompt 11 — Verify `polar_scl_decoder` Was Untouched by `async_fifo`'s Invalidation
> ```text
> @eda-lead Switch back to polar_scl_decoder and confirm its pipeline stages and logs are still intact.
> ```
* **What to watch:** Or simply select `polar_scl_decoder` in the browser dropdown! All 4 pills (`1.Hier → 2.Lint → 3.Sim → 4.Synth`) on `polar_scl_decoder` are still green, and zero `async_fifo` logs leaked over.

### Prompt 12 — Re-Validate `async_fifo` Using Plain-English 1-Line Full Flow
> ```text
> @eda-lead Run the full tapeout flow on async_fifo to get all stages green again.
> ```
* **What to watch:** `@eda-lead` self-invokes the `full-tapeout-flow` skill, running `1.Hier -> 2.Lint -> 3.Sim -> 4.Synth` in sequence on `async_fifo` and clearing all `STALE` badges back to `PASS`.

### Prompt 13 — Inject a Subtle Hardware Bug in `async_fifo` to Test Failure & COI Triage
> ```text
> @eda-lead In async_fifo.sv, temporarily corrupt the write Gray pointer calculation by changing `(wbin_next >> 1) ^ wbin_next` to just `wbin_next`, then run hierarchy, lint, and simulation to observe the failure.
> ```
* **What to watch:** SHA-256 changes, `4.Synth` invalidates to `STALE`, and `3.Sim` turns red (`3.Sim (FAIL)`).

### Prompt 14 — Autonomous Bug Triage & Fix via Plain English (`/triage-and-fix-bug`)
> ```text
> @eda-lead Triage and fix the failing simulation bug in async_fifo, then take it back to tapeout sign-off.
> ```
* **What to watch:** `@dv-debugger` automatically runs `extract_backward_coi` + `read_coi_sliced_waveform` (`🔍 COI` badge activates), pulls `CDC-002-GRAY-FIFO-PTR` from the Knowledge Base, posts an `OPEN_BUG` ticket to `@rtl-architect`, patches `async_fifo.sv`, re-runs `1.Hier -> 2.Lint -> 3.Sim` (`PASS`), and `@synth-qor` re-runs `4.Synth` + schematics!

---

## Phase 4: Create a Brand-New Project From the Dashboard UI & Build From Scratch (Prompts 15–21)

### Prompt 15 — Create a New Project in the Browser UI (`+ New` Button) & Scaffold via Plain English
1. **In your browser (`http://127.0.0.1:8080`):** Click the **`+ New`** button next to the project dropdown, type **` programmable_pwm_timer `**, and click **Create & Switch**.
2. Notice the dashboard immediately switches to `programmable_pwm_timer` with an empty log (`0 events`) and all 4 stage pills in `IDLE`.
3. **Now type this simple sentence in Copilot Chat (without even mentioning the project name!):**
> ```text
> @eda-lead Design a synthesizable 8-bit programmable PWM timer with a 2-block FSM (IDLE, RUN, DONE), period and duty-cycle registers, and a glitch-free registered pwm_out strobe in our active project, along with a self-checking testbench, and run the RTL and lint checks.
> ```
* **What to watch:** Because the browser dropdown set `.silicon_studio/workspace.json` to `programmable_pwm_timer`, `@eda-lead` automatically targets `projects/programmable_pwm_timer/`, pulls FSM/Lint rules from the Knowledge Base, writes `src/programmable_pwm_timer.sv` and `verif/tb_programmable_pwm_timer.sv`, and turns `1.Hier` + `2.Lint` green!

### Prompt 16 — Simulate the New Project (`@dv-debugger`)
> ```text
> @dv-debugger Simulate the active project and verify the PWM duty cycle and done strobe pass all checks.
> ```
* **What to watch:** `3.Sim` turns green on `programmable_pwm_timer`, and WaveDrom renders the new PWM waveform live.

### Prompt 17 — Synthesize the New Project Across All 3 ASIC PDKs + FPGA (`@synth-qor`)
> ```text
> @synth-qor Synthesize the active project across sky130, nangate45, asap7, and artix7 FPGA, render the schematics, and post the tapeout sign-off ticket.
> ```
* **What to watch:** `4.Synth` turns green, Tab 1 shows `Top RTL (programmable_pwm_timer)`, and Tab 3 compares `asap7`, `nangate45`, `sky130`, and `artix7`!

### Prompt 18 — Inject a Lint Hazard (`LATCH`) in the New Project & Test Lint Gate
> ```text
> @eda-lead In programmable_pwm_timer.sv, comment out the default initialization in always_comb so it infers a latch on one branch, then run hierarchy and Verilator lint.
> ```
* **What to watch:** `2.Lint` turns red (`2.Lint (FAIL)` with `%Warning-LATCH`), and downstream `3.Sim` and `4.Synth` immediately invalidate to `STALE`!

### Prompt 19 — Test That `3.Sim` Is Blocked While `2.Lint` Is Failing
> ```text
> @dv-debugger Try running simulation on programmable_pwm_timer while lint is failing.
> ```
* **What to watch:** The state machine blocks `run_iverilog_simulation` with `BLOCKED_SEQUENCE_VIOLATION (Requires 2. Lint)`.

### Prompt 20 — Fix the Lint Hazard Using Pull-RAG & Re-Close Full Flow
> ```text
> @rtl-architect Pull the inferred latch rule from our knowledge base, fix programmable_pwm_timer.sv, and have @eda-lead complete the full flow back to tapeout.
> ```
* **What to watch:** `@rtl-architect` pulls `LINT-001-INFERRED-LATCH`, restores the upfront default initialization, and `@eda-lead` drives `1.Hier -> 2.Lint -> 3.Sim -> 4.Synth` back to all-green!

### Prompt 21 — Rapid 3-Way UI Dropdown Switch Test
* **In your browser (`http://127.0.0.1:8080`):**
  1. Click the **Sun/Moon (`☀`) Theme Button** in the top-right header—verify the entire IDE (header, topology panel, log table, tabs, cards, and schematics) switches cleanly between **Obsidian Dark** and **Silicon Daylight**.
  2. Switch the top project dropdown between `async_fifo` $\rightarrow$ `polar_scl_decoder` $\rightarrow$ `programmable_pwm_timer`. Verify every project loads its own isolated logs, tickets, waveforms, PPA bars, and schematics with zero cross-project bleed.

---

## Phase 5: Complex Project End-to-End Bug-to-Tapeout & Final Ablation Benchmark (Prompts 22–24)

### Prompt 22 — Inject a Subtle Path-Metric / Frozen-Bit Bug in `polar_scl_decoder`
> ```text
> @eda-lead Switch to polar_scl_decoder, inject a 1-line bug in sc_core.sv (for example, invert the frozen-bit decision or corrupt path metric accumulation for bit_idx_q == 3), and run hierarchy, lint, and simulation.
> ```
* **What to watch:** `1.Hier` and `2.Lint` pass (because a functional logic bug is syntactically valid SV), `3.Sim` fails (`3.Sim (FAIL)`), and `4.Synth` invalidates to `STALE`.

### Prompt 23 — Autonomous 5-Stage Progressive Zoom-and-Pan Bug Triage on `polar_scl_decoder`
> ```text
> @eda-lead Use our triage-and-fix-bug workflow to root-cause the failure in polar_scl_decoder using the control roadmap and COI t-1ps waveform slice, fix sc_core.sv, and run the full tapeout flow.
> ```
* **What to watch:** `@dv-debugger` runs the 4-signal Control Roadmap $\rightarrow$ Backward COI on `decoded_bits_o` $\rightarrow$ Dual-Edge (`t` vs `t - 1ps`) slice around `205ns` $\rightarrow$ posts `OPEN_BUG` ticket $\rightarrow$ `@rtl-architect` fixes `sc_core.sv` $\rightarrow$ `1.Hier -> 2.Lint -> 3.Sim -> 4.Synth` all turn green!

### Prompt 24 — Generate the Final Quantitative Ablation & Token-Compression Report
> ```text
> @eda-lead Run scripts/run_ablation_benchmarks.py and display the complete observability token-compression and Knowledge Base verification tables across all three projects (`polar_scl_decoder`, `async_fifo`, and `programmable_pwm_timer`).
> ```
* **What to watch:** Generates `docs/manuals/ablation_benchmark_results.md` with the exact token compression percentages ($>94\%$ reduction vs. raw VCD) across all three projects, ready to drop straight into your GitHub `README.md`!