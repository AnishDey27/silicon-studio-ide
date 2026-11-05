# =============================================================================
# File Path: backend/engines/pass_state_validator.py
# =============================================================================
"""Deterministic Yosys Pass-State Validator & Capability Query Engine.

Loads `schemas/tools/yosys.schema.json` (or legacy `schemas/synthesis/yosys.schema.json`)
and enforces the RTLIL pass lifecycle state machine:
EMPTY -> LOADED_AST -> ELABORATED -> RTL_NETLIST -> RTL_NETLIST_FLAT -> GENERIC_GATES -> TECH_MAPPED
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

STATE_ORDER = [
    "EMPTY",
    "LOADED_AST",
    "ELABORATED",
    "RTL_NETLIST",
    "RTL_NETLIST_FLAT",
    "GENERIC_GATES",
    "TECH_MAPPED",
]

STATE_BRIDGES: Dict[str, List[str]] = {
    "RTL_NETLIST": ["proc", "opt"],
    "RTL_NETLIST_FLAT": ["proc", "opt", "flatten", "opt"],
    "GENERIC_GATES": ["proc", "opt", "flatten", "opt", "techmap", "simplemap", "opt"],
}

PASS_STATE_OVERRIDES: Dict[str, Dict[str, str]] = {
    "simplemap": {"requires_state": "RTL_NETLIST", "produces_state": "GENERIC_GATES"},
    "dfflibmap": {"requires_state": "GENERIC_GATES", "produces_state": "GENERIC_GATES"},
    "dfflegalize": {"requires_state": "GENERIC_GATES", "produces_state": "GENERIC_GATES"},
    "dffunmap": {"requires_state": "RTL_NETLIST", "produces_state": "RTL_NETLIST"},
    "abc": {"requires_state": "GENERIC_GATES", "produces_state": "TECH_MAPPED"},
    "synth_ice40": {"requires_state": "ELABORATED", "produces_state": "TECH_MAPPED"},
    "synth_ecp5": {"requires_state": "ELABORATED", "produces_state": "TECH_MAPPED"},
    "synth_xilinx": {"requires_state": "ELABORATED", "produces_state": "TECH_MAPPED"},
    "synth_gowin": {"requires_state": "ELABORATED", "produces_state": "TECH_MAPPED"},
}


def load_tool_schema(studio_root: Path = STUDIO_ROOT, tool_name: str = "yosys") -> Dict[str, Any]:
    """Loads the extracted JSON capability schema for `yosys`, `verilator`, or `iverilog`."""
    t_clean = tool_name.lower().strip()
    candidates = [
        studio_root / "schemas" / "tools" / f"{t_clean}.schema.json",
        studio_root / "schemas" / "synthesis" / f"{t_clean}.schema.json",
        studio_root / "schemas" / "lint" / f"{t_clean}.schema.json",
        studio_root / "schemas" / "simulation" / f"{t_clean}.schema.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return {}


def query_capabilities(
    studio_root: Path = STUDIO_ROOT,
    tool_name: str = "yosys",
    command_or_flag: str = "",
    category: str = "",
    search_keyword: str = "",
) -> Dict[str, Any]:
    """Queries the deterministic capability schema for any registered EDA tool."""
    schema = load_tool_schema(studio_root, tool_name)
    if not schema:
        return {
            "status": "SCHEMA_MISSING",
            "message": (
                f"Schema for '{tool_name}' not yet built. Run "
                f"`python -m schema_factory.build_all_schemas --tool {tool_name}`."
            ),
        }

    if tool_name.lower().strip() != "yosys":
        flags = schema.get("flags", [])
        kw = (command_or_flag or search_keyword).strip().lower()
        if kw:
            flags = [
                f
                for f in flags
                if kw in f.get("flag", "").lower()
                or kw in f.get("description", "").lower()
            ]
        return {
            "status": "SUCCESS",
            "tool": tool_name,
            "version": schema.get("version", ""),
            "matching_flags_count": len(flags),
            "flags": flags[:50],
        }

    commands = schema.get("commands", {})
    if command_or_flag.strip():
        target = command_or_flag.strip().lower()
        if target in commands:
            return {"status": "SUCCESS", "command_schema": commands[target]}
        similar = [k for k in commands if target in k]
        return {
            "status": "NOT_FOUND",
            "message": f"Yosys command '{target}' not found.",
            "similar_commands": similar[:15],
        }

    kw = search_keyword.strip().lower()
    cat = category.strip().lower()
    matches = []
    for c_name, info in sorted(commands.items()):
        if cat and cat not in info.get("category", "").lower():
            continue
        if kw and (
            kw not in c_name.lower()
            and kw not in info.get("summary", "").lower()
            and kw not in info.get("description", "").lower()
        ):
            continue
        matches.append(
            {
                "command": c_name,
                "category": info.get("category"),
                "summary": info.get("summary"),
                "requires_state": info.get("state_machine_contract", {}).get(
                    "requires_state"
                ),
                "flag_count": len(info.get("flags", [])),
            }
        )

    return {
        "status": "SUCCESS",
        "tool": "yosys",
        "total_matches": len(matches),
        "canonical_recipes": schema.get("canonical_recipes", {}),
        "matches": matches[:45],
    }


def validate_and_compile_yosys_passes(
    studio_root: Path,
    rtl_files_posix: List[str],
    rtl_top: str,
    requested_passes: List[str],
) -> Dict[str, Any]:
    """Validates a sequence of Yosys passes and auto-inserts missing state prerequisites."""
    schema = load_tool_schema(studio_root, "yosys")
    commands = schema.get("commands", {})

    posix_str = " ".join(f'"{p}"' for p in rtl_files_posix)
    compiled_steps: List[str] = [
        f"read_verilog -sv {posix_str}",
        f"hierarchy -check -top {rtl_top}",
    ]
    current_state_idx = STATE_ORDER.index("ELABORATED")
    auto_inserted: List[str] = []
    unknown_commands: List[str] = []

    for raw_pass in requested_passes:
        tokens = raw_pass.strip().split()
        if not tokens:
            continue
        cmd_name = tokens[0]

        if commands and cmd_name not in commands and cmd_name not in PASS_STATE_OVERRIDES:
            unknown_commands.append(cmd_name)
            continue

        contract = PASS_STATE_OVERRIDES.get(
            cmd_name,
            commands.get(cmd_name, {}).get("state_machine_contract", {})
            if commands
            else {},
        )
        req_state = contract.get("requires_state", "ELABORATED")
        prod_state = contract.get("produces_state", "UNCHANGED")

        if req_state in STATE_ORDER:
            req_idx = STATE_ORDER.index(req_state)
            if req_idx > current_state_idx and req_state in STATE_BRIDGES:
                for bridge_cmd in STATE_BRIDGES[req_state]:
                    if bridge_cmd not in compiled_steps:
                        compiled_steps.append(bridge_cmd)
                        auto_inserted.append(bridge_cmd)
                current_state_idx = req_idx

        compiled_steps.append(raw_pass.strip())
        if prod_state in STATE_ORDER:
            current_state_idx = max(current_state_idx, STATE_ORDER.index(prod_state))

    return {
        "valid": len(unknown_commands) == 0,
        "unknown_commands": unknown_commands,
        "auto_inserted_prerequisites": auto_inserted,
        "compiled_yosys_script": "; ".join(compiled_steps),
    }