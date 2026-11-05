# =============================================================================
# File Path: schema_factory/tool_introspector/verilator_introspector.py
# =============================================================================
"""Live Binary Introspection Schema Builder for Verilator (`verilator_introspector.py`).

Interrogates `verilator_bin.exe --version` and `--help` via `BaseToolIntrospector`
to extract supported CLI flags, warning controls (`-W*`), and language standards.

Outputs:
- `schemas/tools/verilator.schema.json` (and `schemas/lint/verilator.schema.json`)
- `docs/manuals/verilator_capabilities.md`
"""
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from schema_factory.tool_introspector.base_introspector import BaseToolIntrospector

DEFAULT_VERILATOR_FLAGS: List[Dict[str, str]] = [
    {"flag": "--lint-only", "description": "Lint the files only, do not create C++ or sim output"},
    {"flag": "-Wall", "description": "Enable all style and static hazard lint warnings"},
    {"flag": "-sv", "description": "Enable IEEE 1800-2017 SystemVerilog parsing"},
    {"flag": "--top-module <top>", "description": "Specify top-level SystemVerilog module name"},
    {"flag": "-Wno-DECLFILENAME", "description": "Suppress module-name vs filename mismatch warning"},
    {"flag": "-Wno-EOFNEWLINE", "description": "Suppress missing trailing newline warning"},
    {"flag": "-Wno-UNUSEDSIGNAL", "description": "Suppress unused signal warning"},
    {"flag": "-Wno-UNUSEDPARAM", "description": "Suppress unused parameter warning"},
]


class VerilatorIntrospector(BaseToolIntrospector):
    """Introspects `verilator_bin` CLI flags and static lint warning capabilities."""

    tool_name = "verilator"
    domain = "lint"
    binary_cmd = "verilator"
    version_args = ("--version",)
    help_args = ("--help",)

    def build_schema(self, update_registry: bool = True) -> Dict[str, Any]:
        print("[Verilator Introspector] Interrogating local verilator_bin binary...")
        version_str = self.extract_version("Verilator OSS CAD Suite")
        raw_help = self.extract_raw_help(timeout_sec=15)

        flags = self.parse_standard_flags(
            raw_help,
            patterns=[r"^\s{2,8}(-[-\w+<>\[\]=]+)\s{2,}(.+)$"],
        )
        if not flags:
            flags = list(DEFAULT_VERILATOR_FLAGS)

        schema_payload: Dict[str, Any] = {
            "tool": "verilator",
            "version": version_str,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "default_lint_invocation": [
                "verilator_bin.exe",
                "--lint-only",
                "-Wall",
                "-Wno-DECLFILENAME",
                "-Wno-EOFNEWLINE",
                "-sv",
                "--top-module",
                "<rtl_top>",
            ],
            "total_flags": len(flags),
            "flags": flags,
        }

        schema_path = self.write_schema_files(schema_payload)

        md_lines = [
            "# Verilator Capabilities & CLI Reference Manual",
            "",
            f"- **Binary Version:** `{version_str}`",
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
                {"version": version_str, "total_flags": len(flags)}
            )
        print(
            f"[OK] Wrote {len(flags)} Verilator flags -> {schema_path.relative_to(self.studio_root)}"
        )
        return schema_payload


def main() -> None:
    VerilatorIntrospector().build_schema(update_registry=True)


if __name__ == "__main__":
    main()