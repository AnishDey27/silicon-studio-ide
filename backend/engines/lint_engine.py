# =============================================================================
# File Path: backend/engines/lint_engine.py
# =============================================================================
"""Pure Verilator Static Lint Engine (`backend/engines/lint_engine.py`).

Key V3.0 Upgrades:
- Pure Domain Function: Never calls `finish_tool_execution` or `sync_to_active_work`
  internally, eliminating the V2 duplicate log row bug (`17:00:54.347` vs `.356`).
- Writes `lint_report.txt` directly to `projects/<project>/build/reports/lint_report.txt`.
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import ensure_trailing_newlines, run_cmd
from backend.core.workspace_manager import ensure_project_structure, get_project_dir
from backend.engines.hierarchy_engine import resolve_hierarchy


def execute_verilator_lint(
    project_name: str, studio_root: Path = STUDIO_ROOT
) -> Dict[str, Any]:
    """Runs Verilator static lint (`--lint-only -Wall -sv`) on `projects/<project_name>/src/`."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    rtl_paths = [studio_root / p for p in hier["rtl_files_ordered"]]
    tb_paths = [studio_root / p for p in hier["tb_files_ordered"]]

    if not rtl_paths:
        return {"status": "ERROR", "message": f"No RTL files found in {proj_dir / 'src'}"}

    ensure_trailing_newlines(rtl_paths + tb_paths)

    cmd = [
        "verilator",
        "--lint-only",
        "-Wall",
        "-Wno-DECLFILENAME",
        "-Wno-EOFNEWLINE",
        "-sv",
    ]
    if hier["rtl_top"]:
        cmd.extend(["--top-module", hier["rtl_top"]])
    cmd.extend([str(p) for p in rtl_paths])

    res = run_cmd(cmd, cwd=studio_root, timeout_sec=30)

    report_text = (
        (res["stdout"] + "\n" + res["stderr"]).strip()
        or "Verilator lint passed with 0 warnings."
    )
    report_file = comp["reports"] / "lint_report.txt"
    report_file.write_text(report_text + "\n", encoding="utf-8")

    warning_types: Dict[str, int] = {}
    for m in re.finditer(r"%Warning-([A-Z0-9_]+):", report_text):
        w_type = m.group(1)
        warning_types[w_type] = warning_types.get(w_type, 0) + 1

    passed = (
        res["exit_code"] == 0
        and "%Warning-" not in report_text
        and "%Error" not in report_text
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "project_name": proj_dir.name,
        "rtl_top": hier["rtl_top"],
        "files_linted": hier["rtl_files_ordered"],
        "exit_code": res["exit_code"],
        "warning_summary": warning_types,
        "lint_output": report_text,
        "report_path": f"projects/{proj_dir.name}/build/reports/lint_report.txt",
        "agent_guidance": (
            "Verilator lint passed cleanly! Next step: run_yosys_synthesis or run_iverilog_simulation."
            if passed
            else (
                "Verilator reported static warnings/errors. Call query_design_knowledge(domain='lint', ...) "
                "to pull the verified golden pattern and fix the flagged lines in src/*.sv."
            )
        ),
    }