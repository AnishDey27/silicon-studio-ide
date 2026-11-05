---
name: synth-ppa-closure
description: "Use when the user asks to synthesize a project, benchmark PPA across Sky130/Nangate45/ASAP7, or generate RTL and gate-level schematics."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/synth-ppa-closure.prompt.md
     ========================================================================== -->
Execute the Multi-PDK Physical Synthesis, PPA Benchmarking & Schematic Closure workflow (`@synth-qor`):
1. If no project name was specified, call `list_projects()` to target the active project from `.silicon_studio/workspace.json`.
2. Ensure prerequisites `1.Hier`, `2.Lint`, and `3.Sim` are `PASS` (if any prerequisite is pending/stale, run it in order first).
3. Call `query_design_knowledge(domain="ppa" or "sdc", symptom_or_pattern=..., project_name=project_name)` to pull the relevant optimization or timing constraint rule.
4. Run `run_yosys_synthesis(project_name=project_name, synth_mode="asic_liberty", target=...)` across `sky130`, `nangate45`, and `asap7`.
5. Call `render_project_schematics(project_name=project_name)` to render Top RTL, Submodule, and Gate Netlist SVGs.
6. Call `post_agent_handoff(project_name=project_name, from_agent="@synth-qor", to_agent="@eda-lead", status="TAPEOUT_READY", kb_rule_id="<RULE_ID>", ...)` and display the Multi-PDK PPA comparison matrix.