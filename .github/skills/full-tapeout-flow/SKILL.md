---
name: full-tapeout-flow
description: "Use when the user asks to run the full EDA flow, full tapeout flow, end-to-end verification and synthesis, or complete sign-off on a project. Autonomously runs 1.Hier -> 2.Lint -> 3.Sim (with COI bug fix if needed) -> 4.Synth (Sky130, Nangate45, ASAP7) -> Schematics -> Sign-Off."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/full-tapeout-flow.prompt.md
     ========================================================================== -->
Execute the complete, autonomous Silicon Studio V3.0 tapeout flow in strict sequential order (`1.Hier -> 2.Lint -> 3.Sim -> 4.Synth`). If no project name was mentioned in the prompt, call `list_projects()` first to target `active_project` from `.silicon_studio/workspace.json`:

1. **Stage 1 & 2 — Hierarchy & Verilator Static Lint (`@rtl-architect`):**
   - Call `resolve_project_hierarchy(project_name)` (`1.Hier`).
   - Call `run_verilator_lint(project_name)` (`2.Lint`).
   - If any lint warnings/errors exist, call `query_design_knowledge(domain="lint", ..., project_name=project_name)`, fix `src/*.sv`, and re-run `1.Hier` + `2.Lint` until `0 warnings` (`PASS`).
2. **Stage 3 — Dynamic Simulation & Conditional COI Triage (`@dv-debugger`):**
   - Call `run_iverilog_simulation(project_name)` (`3.Sim`).
   - If simulation **FAILS**, run `extract_backward_coi` + `read_coi_sliced_waveform` (`hide_constant_signals=True`), call `query_design_knowledge`, post an `OPEN_BUG` ticket via `post_agent_handoff`, patch `src/*.sv`, and re-run `1.Hier` $\rightarrow$ `2.Lint` $\rightarrow$ `3.Sim` until `PASS`.
3. **Stage 4 — Multi-PDK ASIC Synthesis & Schematics (`@synth-qor`):**
   - Call `query_design_knowledge(domain="sdc" or "ppa", ..., project_name=project_name)` to pull the applicable rule card.
   - Run `run_yosys_synthesis` with `synth_mode="asic_liberty"` across all three PDKs: `sky130`, `nangate45`, and `asap7`.
   - Call `render_project_schematics(project_name)` to populate all RTL and Gate Netlist SVGs.
4. **Executive Sign-Off (`@eda-lead`):**
   - Call `post_agent_handoff(project_name=project_name, from_agent="@synth-qor", to_agent="@eda-lead", status="TAPEOUT_READY", kb_rule_id="<RULE_ID>", ...)` and display the final PPA & Verification sign-off table.