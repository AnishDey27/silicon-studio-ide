# =============================================================================
# File Path: backend/engines/sim_engine.py
# =============================================================================
"""Pure Icarus Verilog Simulation & Switching Power Engine (`backend/engines/sim_engine.py`).

Key V3.0 Upgrades:
1. Pure Domain Function: Never calls `finish_tool_execution` internally, preventing
   duplicate simulation rows in the Execution Log.
2. Executes `vvp` with `cwd = proj_dir / "build"` so testbench `$fopen("../verif/*.mem")`
   and `$dumpfile("wave.vcd")` resolve identically to V2 (`projects/<name>/verif/*.mem`).
3. Automatically invokes `convert_vcd_to_artifacts()` to generate `wave_full.md`,
   `wavedrom_full.json`, and `build/reports/power_activity.json` (Bit-Level Hamming
   switching activity).
"""
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import run_cmd
from backend.core.workspace_manager import ensure_project_structure, get_project_dir
from backend.engines.coi_slicer_engine import convert_vcd_to_artifacts
from backend.engines.hierarchy_engine import resolve_hierarchy


def execute_iverilog_simulation(
    project_name: str, studio_root: Path = STUDIO_ROOT
) -> Dict[str, Any]:
    """Compiles and simulates `project_name` using Icarus Verilog (`iverilog -g2012` + `vvp`)."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    if not hier["tb_top"]:
        return {
            "status": "ERROR",
            "message": f"No testbench top module found in {proj_dir / 'verif'}",
        }

    build_dir = comp["build"]
    sim_dir = comp["simulation"]
    reports_dir = comp["reports"]

    sim_bin = sim_dir / "sim.out"
    build_vcd = build_dir / "wave.vcd"
    sim_vcd = sim_dir / "wave.vcd"

    for old_file in (sim_bin, build_vcd, sim_vcd):
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                pass

    all_src = [str(studio_root / p) for p in hier["all_sim_files_ordered"]]
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-o",
        str(sim_bin),
        "-s",
        hier["tb_top"],
        *all_src,
    ]
    comp_res = run_cmd(compile_cmd, cwd=studio_root, timeout_sec=30)
    if comp_res["exit_code"] != 0:
        err_out = (comp_res["stdout"] + "\n" + comp_res["stderr"]).strip()
        (reports_dir / "sim_report.txt").write_text(err_out + "\n", encoding="utf-8")
        return {
            "stage": "COMPILE_FAIL",
            "status": "FAIL",
            "project_name": proj_dir.name,
            "compile_order_used": hier["all_sim_files_ordered"],
            "error": err_out,
            "agent_guidance": "Icarus compilation failed. Check compile_order_used and syntax errors in error.",
        }

    # Run vvp with cwd=build_dir so "../verif/*.mem" resolves to projects/<name>/verif/*.mem
    sim_res = run_cmd(["vvp", str(sim_bin)], cwd=build_dir, timeout_sec=45)
    sim_log = (sim_res["stdout"] + "\n" + sim_res["stderr"]).strip()
    (reports_dir / "sim_report.txt").write_text(sim_log + "\n", encoding="utf-8")

    # If the testbench dumped wave.vcd into build_dir (or build/simulation/wave.vcd), normalize to sim_vcd
    if build_vcd.exists() and not sim_vcd.exists():
        shutil.copy2(build_vcd, sim_vcd)
        try:
            build_vcd.unlink()
        except OSError:
            pass

    # Also check if testbench wrote to legacy work/simulation/wave.vcd path
    legacy_sim_vcd = proj_dir / "work" / "simulation" / "wave.vcd"
    if not sim_vcd.exists() and legacy_sim_vcd.exists():
        shutil.copy2(legacy_sim_vcd, sim_vcd)

    wave_meta: Dict[str, Any] = {}
    if sim_vcd.exists():
        wave_meta = convert_vcd_to_artifacts(sim_vcd, build_dir)

    p_act = wave_meta.get("power_activity", {})
    sim_passed = (
        sim_res["exit_code"] == 0
        and "[FAIL]" not in sim_log.upper()
        and "[TB_FAIL]" not in sim_log.upper()
        and "ERROR" not in sim_log.upper()
        and "FATAL" not in sim_log.upper()
    )

    return {
        "stage": "SIMULATION_COMPLETE",
        "status": "PASS" if sim_passed else "FAIL",
        "project_name": proj_dir.name,
        "rtl_top": hier["rtl_top"],
        "tb_top": hier["tb_top"],
        "compile_order_used": hier["all_sim_files_ordered"],
        "exit_code": sim_res["exit_code"],
        "timed_out": sim_res["timeout"],
        "sim_log": sim_log,
        "vcd_generated": sim_vcd.exists(),
        "x_z_anomalies": wave_meta.get("x_z_anomalies", []),
        "power_activity_summary": {
            "sampled_cycles": p_act.get("sampled_cycles"),
            "unique_signals_tracked": p_act.get("unique_signals_tracked"),
            "total_signal_event_toggles": p_act.get("total_signal_event_toggles"),
            "total_bit_hamming_toggles": p_act.get("total_bit_hamming_toggles"),
            "avg_bit_toggles_per_cycle": p_act.get("avg_bit_toggles_per_cycle"),
        },
        "agent_guidance": (
            "Simulation passed! Do NOT read raw_vcd unless asked. Use read_coi_sliced_waveform if inspecting specific timing."
            if sim_passed
            else (
                "Simulation detected a mismatch or failure! Follow the Zoom-and-Pan Debug Protocol: "
                "1) Check sim_log for the failure timestamp t0. "
                "2) Call read_coi_sliced_waveform with target_signal=<failing_output>, center_time=t0, "
                "window_before='-30ns', window_after='+10ns', hide_constant_signals=True."
            )
        ),
    }