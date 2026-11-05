# =============================================================================
# File Path: backend/engines/synth_engine.py
# =============================================================================
"""Pure Two-Stage Yosys & Multi-PDK Synthesis Engine (`backend/engines/synth_engine.py`).

Key V3.0 Upgrades:
1. Pure Domain Function: Never calls `finish_tool_execution` internally, preventing
   duplicate synthesis rows (`run_yosys_synthesis:sky130` logged twice) in the UI log.
2. Built-in Default PDK Catalog (`sky130`, `nangate45`, `asap7`, `artix7`, `ice40`, `ecp5`)
   automatically resolving `pdk_lib/*.lib` (or legacy `tech_libs/asic/*.lib`).
3. Writes all outputs directly into `projects/<project>/build/netlists/` and
   `projects/<project>/build/reports/ppa_comparison_matrix.md`.
"""
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import run_cmd
from backend.core.state_manager import compute_project_hashes
from backend.core.workspace_manager import (
    atomic_write_json,
    ensure_project_structure,
    get_project_dir,
)
from backend.engines.hierarchy_engine import resolve_hierarchy
from backend.engines.pass_state_validator import validate_and_compile_yosys_passes

SEQ_CELL_KEYWORDS = (
    "dff",
    "dfrtp",
    "dfstp",
    "dfxtp",
    "dlatch",
    "sdff",
    "adff",
    "fdre",
    "fdse",
    "fdce",
    "fdpe",
    "trellis_ff",
    "sb_dff",
    "mistral_ff",
)

DEFAULT_SYNTH_CATALOG: Dict[str, Any] = {
    "default_mode": "generic_structural",
    "default_target": "cmos_primitives",
    "modes": {
        "generic_structural": {
            "targets": {
                "cmos_primitives": {
                    "gate_set": "AND,NAND,OR,NOR,XOR,XNOR,MUX",
                    "description": "Yosys intrinsic CMOS gate primitives",
                },
                "aig_nand": {
                    "gate_set": "NAND",
                    "description": "2-Input NAND And-Inverter Graph (AIG)",
                },
            }
        },
        "asic_liberty": {
            "targets": {
                "sky130": {
                    "process_node": "SkyWater 130nm HD (sky130_fd_sc_hd__tt_025C_1v80)",
                    "liberty_candidates": [
                        "pdk_lib/sky130_fd_sc_hd/sky130_fd_sc_hd__tt_025C_1v80.lib",
                        "pdk_lib/sky130_fd_sc_hd__tt_025C_1v80.lib",
                        "tech_libs/asic/sky130_fd_sc_hd__tt_025C_1v80.lib",
                    ],
                },
                "nangate45": {
                    "process_node": "Nangate 45nm Open Cell Library (typical)",
                    "liberty_candidates": [
                        "pdk_lib/nangate45/NangateOpenCellLibrary_typical.lib",
                        "pdk_lib/NangateOpenCellLibrary_typical.lib",
                        "tech_libs/asic/NangateOpenCellLibrary_typical.lib",
                    ],
                },
                "asap7": {
                    "process_node": "ASAP7 7nm Predictive FinFET RVT (TT)",
                    "liberty_Subdir": "pdk_lib/asap7",
                    "liberty_candidates": [
                        "pdk_lib/asap7/asap7sc7p5t_SIMPLE_RVT_TT_nldm_211120.lib",
                        "pdk_lib/asap7sc7p5t_SIMPLE_RVT_TT_nldm.lib",
                        "tech_libs/asic/asap7sc7p5t_SIMPLE_RVT_TT_nldm.lib",
                    ],
                },
            }
        },
        "fpga": {
            "targets": {
                "artix7": {
                    "architecture": "Xilinx 7-Series (Artix-7 / Basys3)",
                    "yosys_command": "synth_xilinx -family xc7",
                },
                "basys3": {
                    "architecture": "Xilinx Artix-7 (Basys3 XC7A35T)",
                    "yosys_command": "synth_xilinx -family xc7",
                },
                "ice40": {
                    "architecture": "Lattice iCE40 HX/UP",
                    "yosys_command": "synth_ice40",
                },
                "ecp5": {
                    "architecture": "Lattice ECP5",
                    "yosys_command": "synth_ecp5",
                },
                "cyclonev": {
                    "architecture": "Intel Cyclone V",
                    "yosys_command": "synth_intel_alm -family cyclonev",
                },
            }
        },
    },
}


def _sanitize_target_slug(target: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", target.strip().lower()).strip("_")
    return slug or "cmos_primitives"


def load_synth_targets_catalog(studio_root: Path = STUDIO_ROOT) -> Dict[str, Any]:
    """Loads synthesis target definitions with fallback to `DEFAULT_SYNTH_CATALOG`."""
    for rel in (
        "schemas/tools/synth_targets.json",
        "schemas/synthesis/synth_targets.json",
    ):
        p = studio_root / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return DEFAULT_SYNTH_CATALOG


def _resolve_liberty_paths(studio_root: Path, t_info: Dict[str, Any]) -> List[Path]:
    """Finds existing `.lib` files for an ASIC target across `pdk_lib/<subdir>/` and `pdk_lib/`."""
    if "liberty_Subdir" in t_info and t_info["liberty_Subdir"]:
        sub_dir = studio_root / str(t_info["liberty_Subdir"])
        if sub_dir.exists() and sub_dir.is_dir():
            sub_libs = sorted(sub_dir.glob("*.lib"))
            if sub_libs:
                return sub_libs

    if "liberty_paths" in t_info and isinstance(t_info["liberty_paths"], list):
        paths = [studio_root / r for r in t_info["liberty_paths"] if r]
        if paths and all(p.exists() for p in paths):
            return paths

    if "liberty_path" in t_info and t_info["liberty_path"]:
        p = studio_root / t_info["liberty_path"]
        if p.exists():
            return [p]

    for cand in t_info.get("liberty_candidates", []):
        p = studio_root / cand
        if p.exists():
            return [p]

    # Search `pdk_lib/` recursively by keyword if exact filename differs
    pdk_dir = studio_root / "pdk_lib"
    if pdk_dir.exists():
        all_libs = sorted(pdk_dir.rglob("*.lib"))
        node_desc = str(t_info.get("process_node", "")).lower()
        for keyword in ("sky130", "nangate", "asap7"):
            if keyword in node_desc:
                matched = [f for f in all_libs if keyword in f.name.lower() or keyword in f.parent.name.lower()]
                if matched:
                    return matched

    return []


def _ensure_uncompressed_liberty(lib_path: Path) -> str:
    raw_bytes = lib_path.read_bytes()
    if raw_bytes[:2] == b"\x1f\x8b":
        text = gzip.decompress(raw_bytes).decode("utf-8", errors="replace")
        lib_path.write_text(text, encoding="utf-8")
        return text
    return raw_bytes.decode("utf-8", errors="replace")


def _prepare_liberty_flags(
    lib_paths: List[Path], target_netlist_dir: Path
) -> Tuple[str, str]:
    for p in lib_paths:
        if p.exists():
            _ensure_uncompressed_liberty(p)

    all_lib_flags = " ".join(f'-liberty "{p.as_posix()}"' for p in lib_paths)
    if len(lib_paths) == 1:
        return all_lib_flags, all_lib_flags

    comb_paths = [p for p in lib_paths if "seq" not in p.name.lower()] or lib_paths
    base_text = _ensure_uncompressed_liberty(comb_paths[0]).rstrip()
    if base_text.endswith("}"):
        base_text = base_text[:-1].rstrip()

    extra_bodies: List[str] = []
    for extra_p in comb_paths[1:]:
        ext_text = _ensure_uncompressed_liberty(extra_p)
        m = re.search(r"\blibrary\s*\([^\)]+\)\s*\{", ext_text)
        body = ext_text[m.end() :] if m else ext_text
        first_block = re.search(
            r"\b(?:lu_table_template|power_lut_template|cell)\s*\(", body
        )
        if first_block:
            body = body[first_block.start() :]
        body_trimmed = body.rstrip()
        if body_trimmed.endswith("}"):
            body_trimmed = body_trimmed[:-1].rstrip()
        extra_bodies.append(body_trimmed)

    merged_lib_path = target_netlist_dir / "merged_comb_abc.lib"
    merged_content = base_text + "\n\n" + "\n\n".join(extra_bodies) + "\n}\n"
    merged_lib_path.write_text(merged_content, encoding="utf-8")

    abc_lib_flag = f'-liberty "{merged_lib_path.as_posix()}"'
    return all_lib_flags, abc_lib_flag


def list_available_synthesis_targets(studio_root: Path = STUDIO_ROOT) -> Dict[str, Any]:
    """Returns all configured synthesis modes, ASIC Liberty (.lib) targets, and FPGA targets."""
    catalog = load_synth_targets_catalog(studio_root)
    asic_targets = catalog.get("modes", {}).get("asic_liberty", {}).get("targets", {})
    resolved_asic: Dict[str, Any] = {}
    for t_name, t_info in asic_targets.items():
        lib_paths = _resolve_liberty_paths(studio_root, t_info)
        resolved_asic[t_name] = {
            "process_node": t_info.get("process_node", t_name),
            "resolved_liberty_files": [p.relative_to(studio_root).as_posix() for p in lib_paths],
            "liberty_files_exist": bool(lib_paths) and all(p.exists() for p in lib_paths),
        }

    return {
        "status": "SUCCESS",
        "default_mode": catalog.get("default_mode", "generic_structural"),
        "default_target": catalog.get("default_target", "cmos_primitives"),
        "generic_structural_targets": list(
            catalog.get("modes", {})
            .get("generic_structural", {})
            .get("targets", {})
            .keys()
        )
        or ["cmos_primitives", "aig_nand"],
        "asic_liberty_targets": resolved_asic,
        "fpga_targets": catalog.get("modes", {}).get("fpga", {}).get("targets", {}),
    }


def ensure_rtlil_elaboration_for_coi(
    project_name: str, studio_root: Path = STUDIO_ROOT
) -> Path:
    """Elaborates ONLY Stage-1 word-level RTLIL (`build/netlists/synth_netlist.json`) for COI debugging.

    Used when a simulation fails so `@dv-debugger` can run `extract_backward_coi` or
    `read_coi_sliced_waveform` without executing gate-level synthesis or advancing `4.Synth`.
    """
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    comp = ensure_project_structure(proj_dir)
    netlist_json_path = comp["netlists"] / "synth_netlist.json"
    if netlist_json_path.exists():
        return netlist_json_path

    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    if not hier.get("rtl_files_ordered") or not hier.get("rtl_top"):
        return netlist_json_path

    posix_rtl = " ".join(
        f'"{(studio_root / p).as_posix()}"' for p in hier["rtl_files_ordered"]
    )
    rtl_top = hier["rtl_top"]
    stage1_script = (
        f"read_verilog -sv {posix_rtl}; "
        f"hierarchy -check -top {rtl_top}; "
        f"proc; opt; fsm; opt; memory; opt; "
        f'write_json "{netlist_json_path.as_posix()}"'
    )
    run_cmd(["yosys", "-Q", "-T", "-p", stage1_script], cwd=studio_root, timeout_sec=45)
    return netlist_json_path


def _is_sequential_cell_name(cell_name: str) -> bool:
    low = cell_name.lower()
    return any(tag in low for tag in SEQ_CELL_KEYWORDS)


def parse_yosys_stat_and_ltp(
    full_log: str, gates_json_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Parses Yosys `stat` and `ltp -noff` outputs across all synthesis modes."""
    stat_section = full_log
    if "Printing statistics." in full_log:
        stat_section = full_log.split("Printing statistics.")[-1]

    if "=== design hierarchy ===" in stat_section:
        target_stat_block = stat_section.split("=== design hierarchy ===")[-1]
    else:
        target_stat_block = stat_section

    target_stat_block = re.split(
        r"^\s*\d+\.\s+Executing\s+", target_stat_block, flags=re.MULTILINE
    )[0]

    combinational_gates: Dict[str, int] = {}
    sequential_ff_cells: Dict[str, int] = {}

    parsed_from_json = False
    if gates_json_path and gates_json_path.exists():
        try:
            gdata = json.loads(gates_json_path.read_text(encoding="utf-8"))
            modules = gdata.get("modules", {})
            top_mod = next(
                (
                    m
                    for m in modules.values()
                    if int(m.get("attributes", {}).get("top", "0"), 2) == 1
                ),
                next(iter(modules.values()), None),
            )
            if top_mod:
                for c_info in top_mod.get("cells", {}).values():
                    c_type = c_info.get("type", "")
                    if not c_type or c_type.startswith("$scopeinfo"):
                        continue
                    if _is_sequential_cell_name(c_type):
                        sequential_ff_cells[c_type] = (
                            sequential_ff_cells.get(c_type, 0) + 1
                        )
                    else:
                        combinational_gates[c_type] = (
                            combinational_gates.get(c_type, 0) + 1
                        )
                parsed_from_json = (
                    sum(combinational_gates.values())
                    + sum(sequential_ff_cells.values())
                ) > 0
        except Exception:
            parsed_from_json = False

    if not parsed_from_json:
        stat_exclude = {
            "wires",
            "wire",
            "public",
            "ports",
            "port",
            "memories",
            "memory",
            "processes",
            "cells",
            "submodules",
        }
        for line in target_stat_block.splitlines():
            m = re.match(r"^\s*(\d+)\s+([\$a-zA-Z0-9_]+)\s*$", line)
            if m:
                cnt, cname = int(m.group(1)), m.group(2)
                if cname.lower() in stat_exclude:
                    continue
                if _is_sequential_cell_name(cname):
                    sequential_ff_cells[cname] = (
                        sequential_ff_cells.get(cname, 0) + cnt
                    )
                else:
                    combinational_gates[cname] = (
                        combinational_gates.get(cname, 0) + cnt
                    )

    transistor_matches = re.findall(
        r"Estimated number of transistors:\s*(\d+)", target_stat_block
    )
    estimated_transistors = (
        int(transistor_matches[-1]) if transistor_matches else None
    )

    area_matches = re.findall(
        r"Chip area for (?:top )?module\s+\S+:\s*([0-9.]+)", target_stat_block
    )
    if not area_matches:
        area_matches = re.findall(r"Chip area.*?:\s*([0-9.]+)", target_stat_block)
    chip_area_um2 = round(float(area_matches[-1]), 4) if area_matches else None

    ltp_header = re.search(
        r"Longest topological path in (\S+) \(length=(\d+)\):", full_log
    )
    critical_path_levels = int(ltp_header.group(2)) if ltp_header else 0
    critical_path_nodes: List[str] = []

    if ltp_header:
        ltp_tail = full_log[ltp_header.end() :]
        for line in ltp_tail.splitlines():
            m = re.match(r"^\s*\d+:\s*(.+)$", line)
            if m:
                critical_path_nodes.append(m.group(1).strip())
            elif critical_path_nodes:
                break

    return {
        "total_combinational_gates": sum(combinational_gates.values()),
        "total_sequential_ff_cells": sum(sequential_ff_cells.values()),
        "total_primitive_cells": sum(combinational_gates.values())
        + sum(sequential_ff_cells.values()),
        "combinational_gate_breakdown": combinational_gates,
        "sequential_ff_breakdown": sequential_ff_cells,
        "estimated_cmos_transistors": estimated_transistors,
        "chip_area_um2": chip_area_um2,
        "critical_path_logic_levels_ltp": critical_path_levels,
        "critical_path_startpoint": (
            critical_path_nodes[0] if critical_path_nodes else None
        ),
        "critical_path_endpoint": (
            critical_path_nodes[-1] if critical_path_nodes else None
        ),
        "critical_path_trace": critical_path_nodes,
    }


def _resolve_mode_and_target(
    studio_root: Path,
    synth_mode: str,
    target: str,
    gate_set: str,
) -> Dict[str, Any]:
    catalog = load_synth_targets_catalog(studio_root)
    mode_norm = synth_mode.strip().lower() if synth_mode else "generic_structural"
    target_norm = target.strip() if target else "cmos_primitives"
    target_low = target_norm.lower()

    asic_dict = catalog.get("modes", {}).get("asic_liberty", {}).get("targets", {})
    fpga_dict = catalog.get("modes", {}).get("fpga", {}).get("targets", {})

    if target_low in asic_dict or target_low.endswith(".lib"):
        mode_norm = "asic_liberty"
    elif target_low in fpga_dict or target_low.startswith("synth_"):
        mode_norm = "fpga"

    if mode_norm == "asic_liberty":
        if target_low in asic_dict:
            t_cfg = asic_dict[target_low]
            lib_paths = _resolve_liberty_paths(studio_root, t_cfg)
            process_label = t_cfg.get("process_node", target_low)
        else:
            raw_parts = [p.strip() for p in target_norm.split(",") if p.strip()]
            lib_paths = [
                Path(p) if Path(p).is_absolute() else (studio_root / p)
                for p in raw_parts
            ]
            names = ", ".join(p.name for p in lib_paths)
            process_label = f"Custom Liberty ({names})"

        return {
            "mode": "asic_liberty",
            "target": target_norm,
            "target_slug": _sanitize_target_slug(target_norm),
            "process_label": process_label,
            "liberty_paths": lib_paths,
        }

    if mode_norm == "fpga":
        t_cfg = fpga_dict.get(target_low, {})
        yosys_cmd = t_cfg.get(
            "yosys_command",
            target_low if target_low.startswith("synth") else "synth -lut 4",
        )
        arch_label = t_cfg.get("architecture", f"FPGA ({yosys_cmd})")
        return {
            "mode": "fpga",
            "target": target_norm,
            "target_slug": _sanitize_target_slug(target_norm),
            "process_label": arch_label,
            "fpga_command": yosys_cmd,
        }

    gen_dict = (
        catalog.get("modes", {}).get("generic_structural", {}).get("targets", {})
    )
    resolved_gates = gate_set.strip() or "AND,NAND,OR,NOR,XOR,XNOR,MUX"
    if target_low in gen_dict and not gate_set.strip():
        resolved_gates = gen_dict[target_low].get("gate_set", resolved_gates)

    return {
        "mode": "generic_structural",
        "target": target_norm,
        "target_slug": _sanitize_target_slug(target_norm),
        "process_label": f"Yosys Intrinsic Structural Primitives ({resolved_gates})",
        "gate_set": resolved_gates,
    }


def _update_ppa_comparison_matrix(
    reports_dir: Path, project_name: str, rtl_sha256: str
) -> None:
    """Rebuilds `build/reports/ppa_comparison_matrix.md` across all `synth_qor_*.json` reports."""
    rows: List[Dict[str, Any]] = []
    for qor_file in sorted(reports_dir.glob("synth_qor_*.json")):
        try:
            data = json.loads(qor_file.read_text(encoding="utf-8"))
            if data.get("status") == "PASS":
                rows.append(data)
        except Exception:
            continue

    if not rows:
        return

    md = [
        f"# Multi-Target PPA & QoR Comparison Matrix — `{project_name}`",
        "",
        f"- **RTL SHA-256 Digest:** `{rtl_sha256}`",
        f"- **Targets Benchmarked:** `{len(rows)}`",
        "",
        "| Target (`--target`) | Mode | Comb. Cells | Seq. Flip-Flops | Total Cells | Chip Area ($\\mu\\text{m}^2$) | CMOS Transistors | Critical Path (`ltp -noff`) |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        t_name = f"`{r.get('target_technology')}`"
        m_name = f"`{r.get('synth_mode')}`"
        comb = r.get("total_combinational_gates", 0)
        seq = r.get("total_sequential_ff_cells", 0)
        tot = r.get("total_primitive_cells", 0)
        area = (
            f"{r['chip_area_um2']:.4f}"
            if r.get("chip_area_um2") is not None
            else "—"
        )
        trans = (
            str(r["estimated_cmos_transistors"])
            if r.get("estimated_cmos_transistors") is not None
            else "—"
        )
        ltp = f"{r.get('critical_path_logic_levels_ltp', 0)} levels"
        md.append(
            f"| {t_name} | {m_name} | {comb} | {seq} | {tot} | {area} | {trans} | {ltp} |"
        )

    (reports_dir / "ppa_comparison_matrix.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8"
    )


def execute_yosys_synthesis(
    project_name: str,
    synth_mode: str = "generic_structural",
    target: str = "cmos_primitives",
    gate_set: str = "AND,NAND,OR,NOR,XOR,XNOR,MUX",
    studio_root: Path = STUDIO_ROOT,
) -> Dict[str, Any]:
    """Runs two-stage Yosys synthesis into `projects/<name>/build/netlists/` and `build/reports/`."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    if not hier["rtl_files_ordered"] or not hier["rtl_top"]:
        return {"status": "ERROR", "message": "Could not resolve RTL files or rtl_top."}

    hashes = compute_project_hashes(proj_dir)
    resolved = _resolve_mode_and_target(studio_root, synth_mode, target, gate_set)
    active_mode = resolved["mode"]
    target_slug = resolved["target_slug"]

    target_netlist_dir = comp["netlists"] / f"mapped_{target_slug}"
    target_netlist_dir.mkdir(parents=True, exist_ok=True)

    posix_rtl = " ".join(
        f'"{(studio_root / p).as_posix()}"' for p in hier["rtl_files_ordered"]
    )
    netlist_json_path = comp["netlists"] / "synth_netlist.json"
    gates_json_path = target_netlist_dir / "synth_gates.json"
    gates_v_path = target_netlist_dir / "synth_gates.v"
    rtl_top = hier["rtl_top"]

    stage1_script = (
        f"read_verilog -sv {posix_rtl}; "
        f"hierarchy -check -top {rtl_top}; "
        f"proc; opt; fsm; opt; memory; opt; "
        f'write_json "{netlist_json_path.as_posix()}"; '
    )

    if active_mode == "asic_liberty":
        lib_paths: List[Path] = resolved.get("liberty_paths", [])
        missing_libs = [str(p) for p in lib_paths if not p.exists()]
        if not lib_paths or missing_libs:
            return {
                "status": "ERROR",
                "message": (
                    f"Liberty (.lib) file(s) not found for '{target}': {missing_libs}. "
                    "Ensure pdk_lib/*.lib files are present."
                ),
            }
        all_lib_flags, abc_lib_flag = _prepare_liberty_flags(
            lib_paths, target_netlist_dir
        )
        stage2_script = (
            f"flatten; opt; "
            f"techmap; simplemap; opt; "
            f"dfflibmap {all_lib_flags}; "
            f"abc {abc_lib_flag}; "
            f"opt_clean -purge; "
            f'write_json "{gates_json_path.as_posix()}"; '
            f'write_verilog -noattr -noexpr -simple-lhs "{gates_v_path.as_posix()}"; '
            f"stat {all_lib_flags}; "
            f"ltp -noff"
        )
    elif active_mode == "fpga":
        fpga_cmd = resolved["fpga_command"]
        stage2_script = (
            f"{fpga_cmd} -top {rtl_top}; "
            f"opt_clean -purge; "
            f'write_json "{gates_json_path.as_posix()}"; '
            f'write_verilog -noattr -noexpr -simple-lhs "{gates_v_path.as_posix()}"; '
            f"stat; "
            f"ltp -noff"
        )
    else:
        g_set = resolved["gate_set"]
        stage2_script = (
            f"flatten; opt; "
            f"techmap; simplemap; opt; "
            f"abc -g {g_set}; "
            f"opt_clean -purge; "
            f'write_json "{gates_json_path.as_posix()}"; '
            f'write_verilog -noattr -noexpr -simple-lhs "{gates_v_path.as_posix()}"; '
            f"stat -tech cmos; "
            f"ltp -noff"
        )

    yosys_script = stage1_script + stage2_script
    res = run_cmd(["yosys", "-p", yosys_script], cwd=studio_root, timeout_sec=60)
    full_log = res["stdout"] + "\n" + res["stderr"]

    (comp["reports"] / f"synth_stat_{target_slug}.txt").write_text(
        full_log, encoding="utf-8"
    )
    (comp["reports"] / "synth_stat.txt").write_text(full_log, encoding="utf-8")

    metrics = parse_yosys_stat_and_ltp(full_log, gates_json_path=gates_json_path)
    passed = res["exit_code"] == 0

    synth_summary = {
        "status": "PASS" if passed else "FAIL",
        "project_name": proj_dir.name,
        "rtl_top": rtl_top,
        "rtl_sha256": hashes["rtl_sha256"],
        "synth_mode": active_mode,
        "target_technology": resolved["target"],
        "target_slug": target_slug,
        "technology_description": resolved["process_label"],
        "structural_netlist_noexpr": True,
        **metrics,
        "generated_files": [
            f"projects/{proj_dir.name}/build/netlists/synth_netlist.json",
            f"projects/{proj_dir.name}/build/netlists/mapped_{target_slug}/synth_gates.v",
            f"projects/{proj_dir.name}/build/netlists/mapped_{target_slug}/synth_gates.json",
            f"projects/{proj_dir.name}/build/reports/synth_qor_{target_slug}.json",
            f"projects/{proj_dir.name}/build/reports/ppa_comparison_matrix.md",
        ],
        "agent_guidance": (
            f"Synthesis to '{resolved['target']}' succeeded! You can now call render_project_schematics, "
            f"extract_backward_coi, or benchmark another PDK target to update ppa_comparison_matrix.md."
            if passed
            else "Synthesis failed. Inspect stderr and fix the syntax/elaboration issue in src/*.sv."
        ),
    }
    if not passed:
        synth_summary["stderr"] = res["stderr"]

    atomic_write_json(comp["reports"] / f"synth_qor_{target_slug}.json", synth_summary)
    atomic_write_json(comp["reports"] / "synth_report.json", synth_summary)

    if passed:
        _update_ppa_comparison_matrix(
            comp["reports"], proj_dir.name, hashes["rtl_sha256"]
        )

    return synth_summary


def execute_custom_yosys_passes(
    project_name: str,
    requested_passes: List[str],
    studio_root: Path = STUDIO_ROOT,
) -> Dict[str, Any]:
    """Validates and executes a custom list of Yosys passes using the state-machine validator."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    rtl_posix = [(studio_root / p).as_posix() for p in hier["rtl_files_ordered"]]

    compilation = validate_and_compile_yosys_passes(
        studio_root, rtl_posix, hier["rtl_top"], requested_passes
    )
    if not compilation["valid"]:
        return {
            "status": "INVALID_PASSES",
            "unknown_commands": compilation["unknown_commands"],
            "message": "One or more requested passes do not exist in the Yosys schema.",
        }

    res = run_cmd(
        ["yosys", "-p", compilation["compiled_yosys_script"]],
        cwd=comp["build"],
        timeout_sec=45,
    )
    return {
        "status": "PASS" if res["exit_code"] == 0 else "FAIL",
        "compiled_script": compilation["compiled_yosys_script"],
        "auto_inserted_prerequisites": compilation["auto_inserted_prerequisites"],
        "exit_code": res["exit_code"],
        "stdout_tail": res["stdout"][-4000:],
        "stderr": res["stderr"],
    }
