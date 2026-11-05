---
name: rtl-lint-signoff
description: "Use when the user asks to check RTL, resolve hierarchy, or run Verilator lint on a project. Executes Stage 1 (1.Hier) and Stage 2 (2.Lint), auto-remediating any lint warnings via Pull-RAG."
disable-model-invocation: true
---
<!-- ==========================================================================
     File Path: .github/prompts/rtl-lint-signoff.prompt.md
     ========================================================================== -->
Execute the Frontend RTL & Static Lint Sign-Off workflow (`@rtl-architect`):
1. If no project name was specified, call `list_projects()` to target the active project from `.silicon_studio/workspace.json`.
2. Call `resolve_project_hierarchy(project_name)` (`1.Hier`) to compute the package-first bottom-up compile order.
3. Call `run_verilator_lint(project_name)` (`2.Lint`).
4. If Verilator reports any warnings or errors (`LATCH`, `WIDTH`, `BLKSEQ`, `UNOPTFLAT`, `CASEINCOMPLETE`), call `query_design_knowledge(domain="lint", symptom_or_pattern=..., project_name=project_name)`, fix the RTL in `src/*.sv`, and re-run `resolve_project_hierarchy` + `run_verilator_lint` until `0 warnings` (`PASS`).