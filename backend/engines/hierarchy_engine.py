# =============================================================================
# File Path: backend/engines/hierarchy_engine.py
# =============================================================================
"""Pure Package-Aware RTL (`src/`) & Verification (`verif/`) Hierarchy Engine.

Key V3.0 Upgrades:
1. Pure Domain Engine: Never mutates `session_state.json` or logs telemetry directly
   (telemetry and SHA-256 invalidation are owned exclusively by `state_manager.py`).
2. Writes `hierarchy.json` directly into `projects/<project>/build/agent_bus/hierarchy.json`.
3. Exposes both `"top_module"` and `"rtl_top"` keys so the frontend badge
   (`Top RTL (<top_module>)`) and all downstream engines stay 100% synchronized.
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import ensure_trailing_newlines
from backend.core.workspace_manager import (
    atomic_write_json,
    ensure_project_structure,
    get_project_dir,
)

SV_KEYWORDS = {
    "module", "endmodule", "if", "else", "case", "casex", "casez", "endcase",
    "for", "while", "repeat", "forever", "always", "always_ff", "always_comb",
    "always_latch", "initial", "assign", "begin", "end", "function", "task",
    "generate", "endgenerate", "typedef", "enum", "struct", "union", "package",
    "endpackage", "import", "input", "output", "inout", "wire", "reg", "logic",
    "int", "integer", "parameter", "localparam", "posedge", "negedge", "or", "and",
}


def _strip_comments(text: str) -> str:
    """Removes // single-line and /* */ multi-line comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


def _parse_sv_file(
    file_path: Path, studio_root: Path, role: str
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Extracts SystemVerilog package names and module definitions from a source file."""
    raw = file_path.read_text(encoding="utf-8", errors="replace")
    clean = _strip_comments(raw)
    try:
        rel_path = file_path.relative_to(studio_root).as_posix()
    except ValueError:
        rel_path = file_path.as_posix()

    packages: List[str] = [
        m.group(1)
        for m in re.finditer(
            r"\bpackage\s+(?:automatic\s+)?([a-zA-Z_][a-zA-Z0-9_$]*)\s*;", clean
        )
    ]

    modules: List[Dict[str, Any]] = []
    mod_pattern = re.compile(
        r"\bmodule\s+(?:automatic\s+)?([a-zA-Z_][a-zA-Z0-9_$]*)\s*(?:#\s*\(.*?\))?\s*(\(.*?\))?\s*;(.*?)\bendmodule\b",
        re.DOTALL,
    )

    for match in mod_pattern.finditer(clean):
        mod_name = match.group(1)
        port_blk = match.group(2) or ""
        body = match.group(3) or ""

        ports: List[Dict[str, str]] = []
        for p_match in re.finditer(
            r"\b(input|output|inout)\b[^;,\)]*?([a-zA-Z_][a-zA-Z0-9_$]*)\s*(?=[,;\)\=]|$)",
            port_blk + "\n" + body,
        ):
            ports.append({"direction": p_match.group(1), "name": p_match.group(2)})

        inst_candidates: List[Dict[str, str]] = []
        inst_pattern = re.compile(
            r"\b([a-zA-Z_][a-zA-Z0-9_$]*)\s+(?:#\s*\([^\)]*\)\s*)?([a-zA-Z_][a-zA-Z0-9_$]*)\s*\(",
            re.DOTALL,
        )
        for im in inst_pattern.finditer(body):
            sub_type = im.group(1)
            inst_name = im.group(2)
            if sub_type not in SV_KEYWORDS and inst_name not in SV_KEYWORDS:
                inst_candidates.append({"module": sub_type, "instance": inst_name})

        modules.append(
            {
                "name": mod_name,
                "file": rel_path,
                "role": role,
                "ports": ports,
                "raw_candidates": inst_candidates,
            }
        )

    return packages, modules


def resolve_hierarchy(project_dir: Path, studio_root: Path = STUDIO_ROOT) -> Dict[str, Any]:
    """Scans `src/` and `verif/` inside `project_dir`, orders packages and modules, and writes `hierarchy.json`."""
    comp = ensure_project_structure(project_dir)
    src_dir = project_dir / "src"
    verif_dir = project_dir / "verif"
    bus_dir = comp["agent_bus"]

    rtl_files = (
        sorted(list(src_dir.glob("*.sv")) + list(src_dir.glob("*.v")))
        if src_dir.exists()
        else []
    )
    tb_files = (
        sorted(list(verif_dir.glob("*.sv")) + list(verif_dir.glob("*.v")))
        if verif_dir.exists()
        else []
    )

    ensure_trailing_newlines(rtl_files + tb_files)

    package_files_ordered: List[str] = []
    discovered_packages: List[str] = []
    parsed_modules: List[Dict[str, Any]] = []

    for f in rtl_files:
        pkgs, mods = _parse_sv_file(f, studio_root, role="rtl")
        rel_f = f.relative_to(studio_root).as_posix()
        if pkgs:
            discovered_packages.extend(pkgs)
            if rel_f not in package_files_ordered:
                package_files_ordered.append(rel_f)
        parsed_modules.extend(mods)

    for f in tb_files:
        pkgs, mods = _parse_sv_file(f, studio_root, role="tb")
        rel_f = f.relative_to(studio_root).as_posix()
        if pkgs:
            discovered_packages.extend(pkgs)
            if rel_f not in package_files_ordered:
                package_files_ordered.append(rel_f)
        parsed_modules.extend(mods)

    known_module_names: Set[str] = {m["name"] for m in parsed_modules}
    module_map: Dict[str, Dict[str, Any]] = {}

    for m in parsed_modules:
        valid_insts = [
            inst
            for inst in m["raw_candidates"]
            if inst["module"] in known_module_names
        ]
        module_map[m["name"]] = {
            "name": m["name"],
            "file": m["file"],
            "role": m["role"],
            "ports": m["ports"],
            "instantiates": valid_insts,
        }

    rtl_mods = [m for m in module_map.values() if m["role"] == "rtl"]
    instantiated_by_rtl = {
        inst["module"] for m in rtl_mods for inst in m["instantiates"]
    }
    rtl_top_candidates = [
        m["name"] for m in rtl_mods if m["name"] not in instantiated_by_rtl
    ]
    rtl_top = (
        rtl_top_candidates[0]
        if rtl_top_candidates
        else (rtl_mods[0]["name"] if rtl_mods else "")
    )

    tb_mods = [m for m in module_map.values() if m["role"] == "tb"]
    instantiated_by_tb = {
        inst["module"] for m in tb_mods for inst in m["instantiates"]
    }
    tb_top_candidates = [
        m["name"] for m in tb_mods if m["name"] not in instantiated_by_tb
    ]
    tb_top = (
        tb_top_candidates[0]
        if tb_top_candidates
        else (tb_mods[0]["name"] if tb_mods else "")
    )

    visited: Set[str] = set()
    ordered_rtl_mods: List[str] = []

    def _dfs(mod_name: str) -> None:
        if mod_name in visited or mod_name not in module_map:
            return
        visited.add(mod_name)
        for inst in module_map[mod_name]["instantiates"]:
            sub = inst["module"]
            if sub in module_map and module_map[sub]["role"] == "rtl":
                _dfs(sub)
        ordered_rtl_mods.append(mod_name)

    if rtl_top:
        _dfs(rtl_top)
    for m in rtl_mods:
        _dfs(m["name"])

    # 1. Start with SystemVerilog package files first (e.g. scl_pkg.sv)
    rtl_compile_order: List[str] = list(package_files_ordered)

    # 2. Add bottom-up topological RTL modules
    for mod_name in ordered_rtl_mods:
        f_path = module_map[mod_name]["file"]
        if f_path not in rtl_compile_order:
            rtl_compile_order.append(f_path)

    # 3. Safety net: include any remaining RTL file in src/ not yet in list
    for f in rtl_files:
        rel_f = f.relative_to(studio_root).as_posix()
        if rel_f not in rtl_compile_order:
            rtl_compile_order.append(rel_f)

    tb_compile_order: List[str] = []
    for m in tb_mods:
        if m["file"] not in tb_compile_order:
            tb_compile_order.append(m["file"])
    for f in tb_files:
        rel_f = f.relative_to(studio_root).as_posix()
        if rel_f not in tb_compile_order:
            tb_compile_order.append(rel_f)

    hierarchy_data = {
        "project_name": project_dir.name,
        "top_module": rtl_top,
        "rtl_top": rtl_top,
        "tb_top": tb_top,
        "packages": discovered_packages,
        "package_files_ordered": package_files_ordered,
        "rtl_files_ordered": rtl_compile_order,
        "tb_files_ordered": tb_compile_order,
        "all_sim_files_ordered": rtl_compile_order + tb_compile_order,
        "modules": module_map,
    }

    atomic_write_json(bus_dir / "hierarchy.json", hierarchy_data)
    return hierarchy_data


def execute_hierarchy_resolution(project_name: str, studio_root: Path = STUDIO_ROOT) -> Dict[str, Any]:
    """High-level entry point for resolving a project's hierarchy by name."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}
    hier = resolve_hierarchy(proj_dir, studio_root=studio_root)
    return {
        "status": "SUCCESS",
        "project_name": proj_dir.name,
        "hierarchy": hier,
    }