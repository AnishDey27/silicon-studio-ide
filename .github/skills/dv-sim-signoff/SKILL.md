---
name: dv-sim-signoff
description: "Use when the user asks to simulate a project, run verification, check testbench results, or inspect switching power and waveforms."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/dv-sim-signoff.prompt.md
     ========================================================================== -->
Execute the Dynamic Verification & Simulation Sign-Off workflow (`@dv-debugger`):
1. If no project name was specified, call `list_projects()` to target the active project from `.silicon_studio/workspace.json`.
2. Ensure Stage 1 (`resolve_project_hierarchy`) and Stage 2 (`run_verilator_lint`) are `PASS` for the current `rtl_sha256` (if not yet run, execute them first so the strict pipeline gate is satisfied).
3. Call `run_iverilog_simulation(project_name)` (`3.Sim`).
4. Report the simulation status (`PASS`/`FAIL`), sampled cycles, X/Z anomaly count, and dynamic bit-level Hamming switching power metrics. (If the user also asked to slice or inspect a specific signal, call `read_coi_sliced_waveform` with `hide_constant_signals=True`).