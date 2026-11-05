---
name: scaffold-new-project
description: "Use when the user asks to design, build, or scaffold a new hardware module and testbench inside a newly created or existing project folder."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/scaffold-new-project.prompt.md
     ========================================================================== -->
Execute the Hardware Project Scaffolding & Golden RTL/TB Generation workflow (`@eda-lead` $\rightarrow$ `@rtl-architect`):
1. Identify the target `project_name` (if the user created the project from the Web IDE `+ New` modal and didn't type the name in chat, call `list_projects()` to read `active_project` from `.silicon_studio/workspace.json`).
2. Call `query_design_knowledge` (`lint`, `fsm`, `cdc`, or `ppa`) to pull applicable golden coding templates before writing RTL.
3. Create clean, synthesizable IEEE 1800-2012 SystemVerilog RTL in `projects/<project_name>/src/<module>.sv` (zero inferred latches, explicit width casts, active-low async reset).
4. Create a self-checking SystemVerilog testbench in `projects/<project_name>/verif/tb_<module>.sv` that:
   - Includes `$dumpfile("wave.vcd"); $dumpvars(0, tb_<module>);`
   - Tests reset, corner cases, and normal operation with deterministic checks.
   - Prints `[TB_PASS] All checks passed!` on success or `[TB_FAIL] ...` on mismatch and finishes with `$finish;`.
5. Run `resolve_project_hierarchy(project_name)` (`1.Hier`) and `run_verilator_lint(project_name)` (`2.Lint`) to confirm `0 warnings` (`PASS`).