# =============================================================================
# File Path: schema_factory/build_all_schemas.py
# =============================================================================
"""Master CLI Schema & Knowledge Factory Orchestrator (`build_all_schemas.py`).

Solves the V2 Makefile/Registry Overwrite Problem:
- Interrogates all 3 core EDA binaries (`yosys`, `verilator`, `iverilog`) and/or
  runs the 2-stage Knowledge Base Canary Compiler Gate (`mine_kb_candidates.py` ->
  `build_knowledge_schema.py`).
- Writes the unified `schemas/registry_index.json` atomically at the end so individual
  builders never overwrite each other's registry entries.

Usage Examples:
  python -m schema_factory.build_all_schemas --all
  python -m schema_factory.build_all_schemas --only tools
  python -m schema_factory.build_all_schemas --only kb
  python -m schema_factory.build_all_schemas --tool yosys
"""
import argparse
import datetime
import sys
from pathlib import Path
from typing import Any, Dict

STUDIO_ROOT = Path(__file__).resolve().parents[1]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from backend.core.workspace_manager import atomic_read_json, atomic_write_json
from schema_factory.knowledge_factory.build_knowledge_schema import build_knowledge_schemas
from schema_factory.knowledge_factory.mine_kb_candidates import main as run_kb_miner
from schema_factory.tool_introspector.iverilog_introspector import IverilogIntrospector
from schema_factory.tool_introspector.verilator_introspector import VerilatorIntrospector
from schema_factory.tool_introspector.yosys_introspector import YosysIntrospector

REGISTRY_INDEX_PATH = STUDIO_ROOT / "schemas" / "registry_index.json"


def build_all(
    run_tools: bool = True,
    run_kb: bool = True,
    specific_tool: str = "",
) -> Dict[str, Any]:
    """Executes requested tool introspectors and knowledge base canary builders."""
    tool_builders = {
        "yosys": YosysIntrospector(STUDIO_ROOT),
        "verilator": VerilatorIntrospector(STUDIO_ROOT),
        "iverilog": IverilogIntrospector(STUDIO_ROOT),
    }

    if specific_tool:
        t_key = specific_tool.strip().lower()
        if t_key not in tool_builders:
            raise ValueError(
                f"Unknown tool '{specific_tool}'. Supported tools: {sorted(tool_builders.keys())}"
            )
        tool_builders[t_key].build_schema(update_registry=True)
        return atomic_read_json(REGISTRY_INDEX_PATH) or {}

    if run_tools:
        print("==========================================================================")
        print("  [STAGE 1/2] Running Live CLI Binary Introspectors (Yosys, Verilator, Icarus)")
        print("==========================================================================")
        for name in ("verilator", "yosys", "iverilog"):
            tool_builders[name].build_schema(update_registry=True)

    if run_kb:
        print("\n==========================================================================")
        print("  [STAGE 2/2] Running Silicon Knowledge Base Miner & 3-Tier Canary Gate")
        print("==========================================================================")
        run_kb_miner()
        build_knowledge_schemas(update_registry=True)

    reg_data = atomic_read_json(REGISTRY_INDEX_PATH) or {"domains": {}, "tools": {}}
    reg_data["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    atomic_write_json(REGISTRY_INDEX_PATH, reg_data)
    print("\n==========================================================================")
    print(f"  [COMPLETE] Master Registry Index synchronized -> {REGISTRY_INDEX_PATH.relative_to(STUDIO_ROOT)}")
    print("==========================================================================")
    return reg_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Silicon Studio IDE V3.0 — Master CLI Tool & Knowledge Schema Factory"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build all CLI tool schemas and run the Knowledge Base Canary Validator (default)",
    )
    parser.add_argument(
        "--only",
        choices=["tools", "kb"],
        default="",
        help="Build only CLI tool schemas ('tools') or only Knowledge Base rules ('kb')",
    )
    parser.add_argument(
        "--tool",
        type=str,
        default="",
        help="Rebuild a single specific tool schema ('yosys', 'verilator', or 'iverilog')",
    )
    args = parser.parse_args()

    if args.tool:
        build_all(run_tools=False, run_kb=False, specific_tool=args.tool)
    elif args.only == "tools":
        build_all(run_tools=True, run_kb=False)
    elif args.only == "kb":
        build_all(run_tools=False, run_kb=True)
    else:
        build_all(run_tools=True, run_kb=True)


if __name__ == "__main__":
    main()