# =============================================================================
# File Path: schema_factory/tool_introspector/base_introspector.py
# =============================================================================
"""Base CLI Binary Introspector & Deterministic Schema Exporter (`base_introspector.py`).

Provides the shared DRY infrastructure for interrogating local EDA binaries
(`yosys`, `verilator`, `iverilog`, or any future CLI tool) via `backend.core.executor.run_cmd`:
- Extracts binary version strings (`--version` / `-V`).
- Parses CLI `--help` / `-h` flag tables using configurable regex patterns.
- Exports deterministic JSON capability schemas to `schemas/tools/<tool>.schema.json`
  (and mirrors to legacy `schemas/<domain>/<tool>.schema.json` for 100% compatibility).
- Generates human-readable Markdown capability manuals in `docs/manuals/<tool>_capabilities.md`.
"""
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.executor import run_cmd
from backend.core.workspace_manager import atomic_read_json, atomic_write_json

SCHEMAS_ROOT = STUDIO_ROOT / "schemas"
TOOLS_SCHEMA_DIR = SCHEMAS_ROOT / "tools"
MANUALS_DIR = STUDIO_ROOT / "docs" / "manuals"
REGISTRY_INDEX_PATH = SCHEMAS_ROOT / "registry_index.json"


class BaseToolIntrospector:
    """Shared base class for all CLI binary capability introspectors."""

    tool_name: str = "generic_tool"
    domain: str = "general"
    binary_cmd: str = "generic_tool"
    version_args: Sequence[str] = ("--version",)
    help_args: Sequence[str] = ("--help",)

    def __init__(self, studio_root: Path = STUDIO_ROOT) -> None:
        self.studio_root = studio_root
        self.tools_schema_dir = self.studio_root / "schemas" / "tools"
        self.domain_schema_dir = self.studio_root / "schemas" / self.domain
        self.manuals_dir = self.studio_root / "docs" / "manuals"

    def run_binary(self, args: Sequence[str], timeout_sec: int = 30) -> Dict[str, Any]:
        """Executes the target EDA binary with `args` using `backend.core.executor.run_cmd`."""
        cmd = [self.binary_cmd, *list(args)]
        return run_cmd(cmd, cwd=self.studio_root, timeout_sec=timeout_sec)

    def extract_version(self, default_version: str = "OSS CAD Suite") -> str:
        """Interrogates the binary for its version string."""
        res = self.run_binary(self.version_args, timeout_sec=15)
        combined = (res.get("stdout", "") + "\n" + res.get("stderr", "")).strip()
        if not combined:
            return default_version
        first_line = combined.splitlines()[0].strip()
        return first_line or default_version

    def extract_raw_help(self, timeout_sec: int = 20) -> str:
        """Interrogates the binary for its `--help` / `-h` output."""
        res = self.run_binary(self.help_args, timeout_sec=timeout_sec)
        return (res.get("stdout", "") + "\n" + res.get("stderr", "")).strip()

    @staticmethod
    def parse_standard_flags(
        raw_help: str,
        patterns: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, str]]:
        """Parses CLI flags and descriptions from `--help` text using regex patterns."""
        active_patterns = list(
            patterns
            or [
                r"^\s{2,8}(-[-\w+<>\[\]=]+)\s{2,}(.+)$",
                r"^\s*(-\S+(?:\s+\S+)?)\s*:\s*(.+)$",
            ]
        )
        compiled = [re.compile(p) for p in active_patterns]
        flags: List[Dict[str, str]] = []
        seen = set()

        for line in raw_help.splitlines():
            for reg in compiled:
                m = reg.match(line)
                if m:
                    flag_str = m.group(1).strip()
                    desc_str = m.group(2).strip()
                    if flag_str not in seen:
                        seen.add(flag_str)
                        flags.append({"flag": flag_str, "description": desc_str})
                    break
        return flags

    def write_schema_files(self, payload: Dict[str, Any]) -> Path:
        """Writes `<tool>.schema.json` to `schemas/tools/` and `schemas/<domain>/`."""
        self.tools_schema_dir.mkdir(parents=True, exist_ok=True)
        self.domain_schema_dir.mkdir(parents=True, exist_ok=True)

        primary_path = self.tools_schema_dir / f"{self.tool_name}.schema.json"
        domain_path = self.domain_schema_dir / f"{self.tool_name}.schema.json"

        atomic_write_json(primary_path, payload)
        atomic_write_json(domain_path, payload)
        return primary_path

    def write_markdown_manual(self, markdown_text: str) -> Path:
        """Writes `docs/manuals/<tool>_capabilities.md`."""
        self.manuals_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.manuals_dir / f"{self.tool_name}_capabilities.md"
        md_path.write_text(markdown_text.rstrip() + "\n", encoding="utf-8")
        return md_path

    def register_in_master_index(self, extra_metadata: Optional[Dict[str, Any]] = None) -> None:
        """Updates `schemas/registry_index.json` with this tool's schema and manual coordinates."""
        reg_data = atomic_read_json(REGISTRY_INDEX_PATH) or {"domains": {}, "tools": {}}
        reg_data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

        tool_entry = {
            "active_tool": self.tool_name,
            "domain": self.domain,
            "schema_path": f"schemas/tools/{self.tool_name}.schema.json",
            "legacy_schema_path": f"schemas/{self.domain}/{self.tool_name}.schema.json",
            "manual_path": f"docs/manuals/{self.tool_name}_capabilities.md",
        }
        if extra_metadata:
            tool_entry.update(extra_metadata)

        reg_data.setdefault("domains", {})[self.domain] = tool_entry
        reg_data.setdefault("tools", {})[self.tool_name] = tool_entry
        atomic_write_json(REGISTRY_INDEX_PATH, reg_data)