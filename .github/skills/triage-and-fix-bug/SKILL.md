---
name: triage-and-fix-bug
description: "Use when a simulation fails or when the user asks to debug, triage, root-cause, or fix a hardware bug. Runs COI structural slicing, Dual-Edge (t vs t-1ps) waveform zooming, Pull-RAG template lookup, surgical RTL patching, and regression verification."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/triage-and-fix-bug.prompt.md
     ========================================================================== -->
Execute the autonomous Neuro-Symbolic Bug Triage & Remediation workflow on the target project (if no project name was mentioned, call `list_projects()` first):

1. **Step 1 — Reproduce Failure (`@dv-debugger`):**
   - Ensure `resolve_project_hierarchy` (`1.Hier`) and `run_verilator_lint` (`2.Lint`) are `PASS`, then call `run_iverilog_simulation` (`3.Sim`).
   - Extract the failure timestamp $t_{\text{fail}}$ and failing output signal from `sim_log`.
2. **Step 2 — Structural COI + Dual-Edge (`t` vs `t - 1ps`) Isolation (`@dv-debugger`):**
   - Call `extract_backward_coi(project_name=project_name, target_signal="<failing_signal>", max_hops=4)`.
   - Call `read_coi_sliced_waveform(project_name=project_name, target_signal="<failing_signal>", center_time="<t0>", window_before="-30ns", window_after="+15ns", hide_constant_signals=True)`.
   - Compare **Table 1 (`Post-Posedge at t`)** against **Table 2 (`Pre-Posedge Setup at t - 1ps`)** to prove the root cause.
3. **Step 3 — Silicon Knowledge Base Lookup & Ticket Handoff (`@dv-debugger` $\rightarrow$ `@rtl-architect`):**
   - Call `query_design_knowledge(domain=..., symptom_or_pattern=..., project_name=project_name)` to pull the verified golden template and `rule_id`.
   - Call `post_agent_handoff(project_name=project_name, from_agent="@dv-debugger", to_agent="@rtl-architect", status="OPEN_BUG", kb_rule_id="<RULE_ID>", ...)`.
4. **Step 4 — Surgical RTL Fix & Strict Sequence Re-Verification (`@rtl-architect` $\rightarrow$ `@dv-debugger`):**
   - Patch `src/*.sv` using the golden template (never edit `verif/tb_*.sv`).
   - Re-run `resolve_project_hierarchy` (`1.Hier`) $\rightarrow$ `run_verilator_lint` (`2.Lint`) $\rightarrow$ `run_iverilog_simulation` (`3.Sim`) to confirm 0 warnings and `[TB_PASS]`.
   - Update the handoff ticket via `post_agent_handoff(project_name=project_name, from_agent="@dv-debugger", to_agent="@eda-lead", status="VERIFIED_PASS", kb_rule_id="<RULE_ID>", ...)`.