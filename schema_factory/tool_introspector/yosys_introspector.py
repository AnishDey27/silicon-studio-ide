# =============================================================================
# File Path: schema_factory/tool_introspector/yosys_introspector.py
# =============================================================================
"""Live Binary Introspection Schema Builder for Yosys (`yosys_introspector.py`).

Interrogates `yosys.exe` via `BaseToolIntrospector`:
- `yosys -Q -T -p "help"` (master list of compiled passes)
- Batched `help <pass>` (exact CLI syntax, flags, and sub-pass expansions)
- `help -cells` (internal RTLIL & gate cell types)
- Embeds the deterministic RTLIL pass state machine (`PASS_STATE_RULES`)

Outputs:
- `schemas/tools/yosys.schema.json` (and `schemas/synthesis/yosys.schema.json`)
- `docs/manuals/yosys_capabilities.md`
"""
import datetime
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from schema_factory.tool_introspector.base_introspector import BaseToolIntrospector

PASS_STATE_RULES: Dict[str, Dict[str, Any]] = {
    "read_verilog": {"requires_state": "EMPTY", "produces_state": "LOADED_AST"},
    "hierarchy": {"requires_state": "LOADED_AST", "produces_state": "ELABORATED"},
    "proc": {"requires_state": "ELABORATED", "produces_state": "RTL_NETLIST"},
    "flatten": {"requires_state": "RTL_NETLIST", "produces_state": "RTL_NETLIST_FLAT"},
    "fsm": {"requires_state": "RTL_NETLIST", "produces_state": "RTL_NETLIST"},
    "memory": {"requires_state": "RTL_NETLIST", "produces_state": "RTL_NETLIST"},
    "techmap": {"requires_state": "RTL_NETLIST", "produces_state": "GENERIC_GATES"},
    "simplemap": {"requires_state": "RTL_NETLIST", "produces_state": "GENERIC_GATES"},
    "abc": {"requires_state": "GENERIC_GATES", "produces_state": "TECH_MAPPED"},
    "dfflibmap": {"requires_state": "GENERIC_GATES", "produces_state": "GENERIC_GATES"},
    "ltp": {
        "requires_state": "RTL_NETLIST",
        "produces_state": "UNCHANGED",
        "recommended_flags": ["-noff"],
    },
    "stat": {
        "requires_state": "ELABORATED",
        "produces_state": "UNCHANGED",
        "recommended_flags": ["-tech cmos"],
    },
    "write_json": {"requires_state": "ELABORATED", "produces_state": "UNCHANGED"},
    "write_verilog": {
        "requires_state": "ELABORATED",
        "produces_state": "UNCHANGED",
        "recommended_flags": ["-noattr", "-noexpr", "-simple-lhs"],
    },
    "show": {
        "requires_state": "ELABORATED",
        "produces_state": "UNCHANGED",
        "recommended_flags": ["-format dot"],
    },
}


def _classify_yosys_command(cmd_name: str) -> str:
    if cmd_name.startswith("read_"):
        return "01_frontend_input"
    if cmd_name.startswith("write_") or cmd_name == "show":
        return "02_backend_export"
    if cmd_name.startswith(("proc", "opt", "peepopt", "share", "wreduce", "alumacc")):
        return "03_rtl_optimization"
    if cmd_name.startswith(("fsm", "memory")):
        return "04_fsm_and_memory"
    if cmd_name.startswith(("techmap", "abc", "dff", "simplemap", "iopadmap", "hilomap")):
        return "05_gate_and_tech_mapping"
    if cmd_name.startswith("synth"):
        return "06_fpga_asic_meta_flows"
    if cmd_name in (
        "sat",
        "freduce",
        "miter",
        "equiv_make",
        "equiv_simple",
        "equiv_status",
        "chformal",
    ):
        return "07_formal_and_equivalence"
    if cmd_name in ("stat", "ltp", "check", "scc", "select", "dump", "tee"):
        return "08_analysis_and_reports"
    if cmd_name in (
        "hierarchy",
        "flatten",
        "submod",
        "uniquify",
        "rename",
        "connect",
        "splitnets",
    ):
        return "09_hierarchy_and_netlist_ops"
    return "10_specialized_passes"


def _parse_help_detail(raw_block: str) -> Dict[str, Any]:
    lines = [line.rstrip() for line in raw_block.strip().splitlines()]
    usages: List[str] = []
    flags: List[Dict[str, str]] = []
    description_lines: List[str] = []
    sub_passes: List[str] = []

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if not line.strip():
            if usages:
                idx += 1
                break
            idx += 1
            continue
        if line.startswith("    ") and not line.strip().startswith("-"):
            usages.append(line.strip())
            idx += 1
        else:
            break

    current_flag = None
    current_flag_desc: List[str] = []

    for line in lines[idx:]:
        stripped = line.strip()
        flag_match = re.match(r"^    (-\S+(?:\s+<[^>]+>|\s+\[\S+\])*)\s*$", line)
        inline_flag_match = re.match(r"^    (-\S+(?:\s+<[^>]+>)?)\s{2,}(.+)$", line)

        if flag_match:
            if current_flag:
                flags.append(
                    {"flag": current_flag, "description": " ".join(current_flag_desc).strip()}
                )
            current_flag = flag_match.group(1).strip()
            current_flag_desc = []
        elif inline_flag_match:
            if current_flag:
                flags.append(
                    {"flag": current_flag, "description": " ".join(current_flag_desc).strip()}
                )
            flags.append(
                {
                    "flag": inline_flag_match.group(1).strip(),
                    "description": inline_flag_match.group(2).strip(),
                }
            )
            current_flag = None
            current_flag_desc = []
        elif current_flag and line.startswith("        "):
            current_flag_desc.append(stripped)
        else:
            if current_flag:
                flags.append(
                    {"flag": current_flag, "description": " ".join(current_flag_desc).strip()}
                )
                current_flag = None
                current_flag_desc = []
            if stripped:
                description_lines.append(stripped)
                if line.startswith("    ") and re.match(
                    r"^[a-z0-9_]+(?:\s+-[a-z0-9_-]+)*$", stripped
                ):
                    sub_passes.append(stripped)

    if current_flag:
        flags.append(
            {"flag": current_flag, "description": " ".join(current_flag_desc).strip()}
        )

    return {
        "usage_signatures": usages,
        "flags": flags,
        "sub_passes_executed": sub_passes,
        "description": " ".join(description_lines[:6]),
    }


class YosysIntrospector(BaseToolIntrospector):
    """Introspects `yosys` passes, flags, cell models, and RTLIL state transitions."""

    tool_name = "yosys"
    domain = "synthesis"
    binary_cmd = "yosys"
    version_args = ("-V",)
    help_args = ("-Q", "-T", "-p", "help")

    def build_schema(self, update_registry: bool = True) -> Dict[str, Any]:
        print("[Yosys Introspector] Interrogating local yosys binary...")
        version_str = self.extract_version("Yosys OSS CAD Suite")
        raw_index = self.extract_raw_help(timeout_sec=30)

        cmd_summaries: Dict[str, str] = {}
        for line in raw_index.splitlines():
            m = re.match(r"^\s{2,4}([a-zA-Z0-9_]+)\s+\.*\s+(.+)$", line)
            if m:
                cmd_summaries[m.group(1).strip()] = m.group(2).strip()

        commands_catalog: Dict[str, Any] = {}
        if cmd_summaries:
            script_parts = [
                f"log ===CMD_START:{c}===; help {c}; log ===CMD_END:{c}==="
                for c in sorted(cmd_summaries.keys())
            ]
            detail_res = self.run_binary(
                ["-Q", "-T", "-p", "; ".join(script_parts)], timeout_sec=60
            )
            pattern = re.compile(r"===CMD_START:(\S+)===\n(.*?)===CMD_END:\1===", re.DOTALL)
            for match in pattern.finditer(detail_res.get("stdout", "")):
                c_name = match.group(1)
                parsed = _parse_help_detail(match.group(2))
                commands_catalog[c_name] = {
                    "command": c_name,
                    "category": _classify_yosys_command(c_name),
                    "summary": cmd_summaries.get(c_name, ""),
                    **parsed,
                    "state_machine_contract": PASS_STATE_RULES.get(
                        c_name, {"requires_state": "ELABORATED", "produces_state": "UNCHANGED"}
                    ),
                }

        # Fallback seed catalog if binary is unavailable during offline CI
        if not commands_catalog:
            for c_name, sm_rule in PASS_STATE_RULES.items():
                commands_catalog[c_name] = {
                    "command": c_name,
                    "category": _classify_yosys_command(c_name),
                    "summary": f"Yosys synthesis pass '{c_name}'",
                    "usage_signatures": [c_name],
                    "flags": [
                        {"flag": f, "description": "Recommended flag"}
                        for f in sm_rule.get("recommended_flags", [])
                    ],
                    "sub_passes_executed": [],
                    "description": f"Deterministic Yosys RTLIL pass ({c_name}).",
                    "state_machine_contract": sm_rule,
                }

        cells_res = self.run_binary(["-Q", "-T", "-p", "help -cells"], timeout_sec=30)
        cell_models = [
            line.strip()
            for line in cells_res.get("stdout", "").splitlines()
            if line.strip().startswith("$")
        ]

        schema_payload: Dict[str, Any] = {
            "tool": "yosys",
            "version": version_str,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "total_commands": len(commands_catalog),
            "total_cell_models": len(cell_models),
            "canonical_recipes": {
                "two_stage_json_and_cmos_gates": [
                    "read_verilog -sv <rtl_files>",
                    "hierarchy -check -top <rtl_top>",
                    "proc; opt; fsm; opt; memory; opt",
                    'write_json "build/netlists/synth_netlist.json"',
                    "flatten; opt; techmap; simplemap; opt",
                    "abc -g AND,NAND,OR,NOR,XOR,XNOR,MUX; opt_clean -purge",
                    'write_json "build/netlists/mapped_cmos_primitives/synth_gates.json"',
                    'write_verilog -noattr -noexpr -simple-lhs "build/netlists/mapped_cmos_primitives/synth_gates.v"',
                    "stat -tech cmos",
                    "ltp -noff",
                ]
            },
            "commands": commands_catalog,
            "cell_models": cell_models,
        }

        schema_path = self.write_schema_files(schema_payload)

        md_lines = [
            "# Yosys Capabilities & Command Reference Manual",
            "",
            f"- **Binary Version:** `{version_str}`",
            f"- **Total Extracted Commands:** `{len(commands_catalog)}`",
            f"- **Total Internal Cell Models:** `{len(cell_models)}`",
            "",
            "| Category | Command | Summary | Flags | Required State |",
            "| :--- | :--- | :--- | ---: | :--- |",
        ]
        for c in sorted(
            commands_catalog.values(), key=lambda x: (x["category"], x["command"])
        ):
            req = c["state_machine_contract"].get("requires_state", "ELABORATED")
            md_lines.append(
                f"| `{c['category']}` | **`{c['command']}`** | {c['summary']} | {len(c['flags'])} | `{req}` |"
            )

        self.write_markdown_manual("\n".join(md_lines))
        if update_registry:
            self.register_in_master_index(
                {
                    "version": version_str,
                    "total_commands": len(commands_catalog),
                    "total_cell_models": len(cell_models),
                }
            )
        print(
            f"[OK] Wrote {len(commands_catalog)} Yosys commands -> {schema_path.relative_to(self.studio_root)}"
        )
        return schema_payload


def main() -> None:
    YosysIntrospector().build_schema(update_registry=True)


if __name__ == "__main__":
    main()