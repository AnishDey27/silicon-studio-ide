# =============================================================================
# File Path: schema_factory/tool_introspector/iverilog_introspector.py
# =============================================================================
"""Live Binary Introspection Schema Builder for Icarus Verilog (`iverilog_introspector.py`).

Interrogates `iverilog.exe` and `vvp.exe` via `BaseToolIntrospector` to extract version
and compiler/runtime flags.

Outputs:
- `schemas/tools/iverilog.schema.json` (and `schemas/simulation/iverilog.schema.json`)
- `docs/manuals/iverilog_capabilities.md`
"""
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from schema_factory.tool_introspector.base_introspector import BaseToolIntrospector

DEFAULT_IVERILOG_FLAGS: List[Dict[str, str]] = [
    {"flag": "-g2012", "description": "Enable IEEE 1800-2012 SystemVerilog generation"},
    {"flag": "-o <filename>", "description": "Specify compiled vvp output binary path"},
    {"flag": "-s <topmodule>", "description": "Specify top-level module to elaborate"},
    {"flag": "-I <includedir>", "description": "Append directory to Verilog include search path"},
    {"flag": "-D <macro[=defn]>", "description": "Define preprocessor macro"},
]


class IverilogIntrospector(BaseToolIntrospector):
    """Introspects `iverilog` and `vvp` compiler/runtime flags."""

    tool_name = "iverilog"
    domain = "simulation"
    binary_cmd = "iverilog"
    version_args = ("-V",)
    help_args = ("-h",)

    def build_schema(self, update_registry: bool = True) -> Dict[str, Any]:
        print("[Icarus Introspector] Interrogating local iverilog and vvp binaries...")
        version_line = self.extract_version("Icarus Verilog OSS CAD Suite")
        raw_help = self.extract_raw_help(timeout_sec=15)

        flags = self.parse_standard_flags(
            raw_help,
            patterns=[r"^\s*(-\S+(?:\s+\S+)?)\s*:\s*(.+)$"],
        )
        if not flags:
            flags = list(DEFAULT_IVERILOG_FLAGS)

        schema_payload: Dict[str, Any] = {
            "tool": "iverilog",
            "version": version_line,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "default_compile_invocation": [
                "iverilog.exe",
                "-g2012",
                "-o",
                "build/simulation/sim.out",
                "-s",
                "<tb_top>",
                "<rtl_files_ordered>",
                "<tb_files_ordered>",
            ],
            "default_runtime_invocation": ["vvp.exe", "build/simulation/sim.out"],
            "total_flags": len(flags),
            "flags": flags,
        }

        schema_path = self.write_schema_files(schema_payload)

        md_lines = [
            "# Icarus Verilog (`iverilog` + `vvp`) Capabilities & CLI Reference Manual",
            "",
            f"- **Binary Version:** `{version_line}`",
            f"- **Total Extracted Flags:** `{len(flags)}`",
            "",
            "| Flag | Description |",
            "| :--- | :--- |",
        ]
        for f in flags:
            md_lines.append(f"| `{f['flag']}` | {f['description']} |")

        self.write_markdown_manual("\n".join(md_lines))
        if update_registry:
            self.register_in_master_index(
                {"version": version_line, "total_flags": len(flags)}
            )
        print(
            f"[OK] Wrote {len(flags)} Icarus Verilog flags -> {schema_path.relative_to(self.studio_root)}"
        )
        return schema_payload


def main() -> None:
    IverilogIntrospector().build_schema(update_registry=True)


if __name__ == "__main__":
    main()