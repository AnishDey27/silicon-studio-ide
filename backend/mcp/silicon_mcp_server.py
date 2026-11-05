# =============================================================================
# File Path: backend/mcp/silicon_mcp_server.py
# =============================================================================
"""Silicon Studio IDE V3.0 — Unified 15-Tool FastMCP Server (`silicon_mcp_server.py`).

Key V3.0 Architectural Guarantees:
1. Strict 4-Stage Pipeline Sequence: Enforces `1.Hier -> 2.Lint -> 3.Sim -> 4.Synth` via
   `check_stage_preconditions()` and `invalidate_downstream_stages()`.
2. Optional COI Diagnostic Branch: `extract_backward_coi` and `read_coi_sliced_waveform`
   call `ensure_rtlil_elaboration_for_coi()` so simulation failures can be debugged
   without advancing or spoofing `4.Synth`.
3. Single-Point Telemetry & Project-Scoped Logs: Global inspection calls only log into
   a project ledger when a project is explicitly targeted.
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Union

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from fastmcp import FastMCP
from backend.core.blackboard_bus import post_handoff_ticket, read_handoff_tickets
from backend.core.state_manager import (
    begin_tool_execution,
    check_stage_preconditions,
    finish_tool_execution,
    invalidate_downstream_stages,
    validate_and_invalidate_cache,
)
from backend.core.workspace_manager import (
    ensure_project_structure,
    get_active_project_name,
    list_all_projects,
    load_workspace_context,
)
from backend.engines.coi_slicer_engine import (
    convert_vcd_to_artifacts,
    extract_coi_subgraph,
)
from backend.engines.hierarchy_engine import resolve_hierarchy
from backend.engines.knowledge_engine import init_knowledge_engine, query_rule
from backend.engines.lint_engine import execute_verilator_lint
from backend.engines.pass_state_validator import query_capabilities
from backend.engines.schematic_engine import render_project_views
from backend.engines.sim_engine import execute_iverilog_simulation
from backend.engines.synth_engine import (
    ensure_rtlil_elaboration_for_coi,
    execute_custom_yosys_passes,
    execute_yosys_synthesis,
    list_available_synthesis_targets,
)

mcp = FastMCP("Silicon-Studio-V3-MCP-Server")

init_knowledge_engine()


@mcp.resource("eda://schemas/registry_index")
def get_schema_registry_index() -> str:
    """Returns the master JSON registry index of all EDA tool and knowledge schemas."""
    idx_path = STUDIO_ROOT / "schemas" / "registry_index.json"
    if idx_path.exists():
        return idx_path.read_text(encoding="utf-8")
    return "{}"


@mcp.resource("eda://schemas/knowledge_catalog")
def get_knowledge_catalog_resource() -> str:
    """Returns the master manifest of canary-validated silicon design rules."""
    manifest_path = STUDIO_ROOT / "schemas" / "knowledge" / "kb_manifest.json"
    if manifest_path.exists():
        return manifest_path.read_text(encoding="utf-8")
    return "{}"


@mcp.tool()
def list_projects(active_project_hint: str = "") -> Dict[str, Any]:
    """Lists all available hardware design projects in `projects/` and returns the active workspace state."""
    if active_project_hint and active_project_hint.strip():
        proj_dir = begin_tool_execution(active_project_hint, "list_projects")
        try:
            return {
                "projects": list_all_projects(),
                "workspace_context": load_workspace_context(),
            }
        finally:
            finish_tool_execution(proj_dir, "list_projects")
    return {
        "projects": list_all_projects(),
        "workspace_context": load_workspace_context(),
    }


@mcp.tool()
def list_synthesis_targets(project_name: str = "") -> Dict[str, Any]:
    """Lists all supported ASIC Liberty PDKs (`sky130`, `nangate45`, `asap7`) and FPGA targets (`artix7`, `ice40`, `ecp5`, `cyclonev`)."""
    if project_name and project_name.strip():
        proj_dir = begin_tool_execution(project_name, "list_synthesis_targets")
        try:
            return list_available_synthesis_targets(STUDIO_ROOT)
        finally:
            finish_tool_execution(proj_dir, "list_synthesis_targets")
    return list_available_synthesis_targets(STUDIO_ROOT)


@mcp.tool()
def resolve_project_hierarchy(project_name: str = "") -> Dict[str, Any]:
    """[STAGE 1: HIERARCHY] Resolves bottom-up SystemVerilog package and module compile order (`build/agent_bus/hierarchy.json`) and invalidates downstream stages (`Lint`, `Sim`, `Synth`)."""
    proj_dir = begin_tool_execution(project_name, "resolve_project_hierarchy")
    try:
        invalidated = invalidate_downstream_stages(proj_dir, from_stage="hierarchy")
        hier = resolve_hierarchy(proj_dir, studio_root=STUDIO_ROOT)
        cache_info = validate_and_invalidate_cache(proj_dir)
        return {
            "status": "SUCCESS",
            "project_name": proj_dir.name,
            "hierarchy": hier,
            "invalidated_downstream_stages": invalidated,
            "cache_state": cache_info,
            "agent_guidance": "Stage 1 (Hierarchy) complete. Mandatory next step: run_verilator_lint (Stage 2).",
        }
    finally:
        finish_tool_execution(proj_dir, "resolve_project_hierarchy")


@mcp.tool()
def run_verilator_lint(project_name: str = "") -> Dict[str, Any]:
    """[STAGE 2: LINT] Runs static SystemVerilog lint verification (`verilator_bin.exe --lint-only -Wall -sv`). Requires Stage 1 (`resolve_project_hierarchy`) to be complete. Invalidates downstream `Sim` and `Synth` stages."""
    proj_dir = begin_tool_execution(project_name, "run_verilator_lint")
    final_action = "run_verilator_lint"
    try:
        gate = check_stage_preconditions(proj_dir, "lint")
        if not gate["allowed"]:
            final_action = "run_verilator_lint_error: blocked_requires_hierarchy"
            return gate

        invalidate_downstream_stages(proj_dir, from_stage="lint")
        res = execute_verilator_lint(proj_dir.name, studio_root=STUDIO_ROOT)
        if res.get("status") == "PASS":
            cache_info = validate_and_invalidate_cache(proj_dir, mark_domain_fresh="lint")
        else:
            cache_info = validate_and_invalidate_cache(proj_dir)
            final_action = "run_verilator_lint_fail"
        res["rtl_sha256"] = cache_info["rtl_sha256"]
        res["invalidated_stale_domains"] = cache_info["invalidated_stale_domains"]
        return res
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def run_yosys_synthesis(
    project_name: str = "",
    synth_mode: str = "generic_structural",
    target: str = "cmos_primitives",
    gate_set: str = "AND,NAND,OR,NOR,XOR,XNOR,MUX",
) -> Dict[str, Any]:
    """[STAGE 4: SYNTHESIS] Runs two-stage Yosys synthesis (`cmos_primitives`, `sky130`, `nangate45`, `asap7`, or `artix7`). Strictly requires `1.Hier`, `2.Lint`, and `3.Sim` to be PASS."""
    action_tag = f"run_yosys_synthesis:{target}"
    proj_dir = begin_tool_execution(project_name, action_tag)
    final_action = action_tag
    try:
        gate = check_stage_preconditions(proj_dir, "synthesis")
        if not gate["allowed"]:
            final_action = (
                f"run_yosys_synthesis_error: blocked_requires_{gate['required_prerequisite']}"
            )
            return gate

        res = execute_yosys_synthesis(
            proj_dir.name,
            synth_mode=synth_mode,
            target=target,
            gate_set=gate_set,
            studio_root=STUDIO_ROOT,
        )
        if res.get("status") == "PASS":
            validate_and_invalidate_cache(
                proj_dir, mark_domain_fresh="synthesis", synth_target=target
            )
        else:
            final_action = f"run_yosys_synthesis_fail:{target}"
        return res
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def run_custom_yosys_pass_flow(
    project_name: str, passes: List[str]
) -> Dict[str, Any]:
    """Validates and executes a custom sequence of Yosys RTLIL synthesis passes. Requires `1.Hier`, `2.Lint`, and `3.Sim` to be PASS."""
    proj_dir = begin_tool_execution(project_name, "run_custom_yosys_pass_flow")
    final_action = "run_custom_yosys_pass_flow"
    try:
        gate = check_stage_preconditions(proj_dir, "synthesis")
        if not gate["allowed"]:
            final_action = "run_custom_yosys_pass_flow_error: blocked"
            return gate
        return execute_custom_yosys_passes(
            proj_dir.name, passes, studio_root=STUDIO_ROOT
        )
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def query_tool_capabilities(
    tool_name: str = "yosys",
    command_or_flag: str = "",
    category: str = "",
    search_keyword: str = "",
    project_name: str = "",
) -> Dict[str, Any]:
    """Queries deterministic compiler capability schemas (`yosys`, `verilator`, `iverilog`) for valid flags, passes, and ordering rules."""
    if project_name and project_name.strip():
        proj_dir = begin_tool_execution(
            project_name, f"query_tool_capabilities:{tool_name}"
        )
        try:
            return query_capabilities(
                STUDIO_ROOT, tool_name, command_or_flag, category, search_keyword
            )
        finally:
            finish_tool_execution(proj_dir, f"query_tool_capabilities:{tool_name}")
    return query_capabilities(
        STUDIO_ROOT, tool_name, command_or_flag, category, search_keyword
    )


@mcp.tool()
def run_iverilog_simulation(project_name: str = "") -> Dict[str, Any]:
    """[STAGE 3: SIMULATION] Compiles and executes dynamic SystemVerilog simulation (`iverilog -g2012` + `vvp`). Requires `1.Hier` and `2.Lint` to be PASS. Invalidates downstream `Synth` stage."""
    proj_dir = begin_tool_execution(project_name, "run_iverilog_simulation")
    final_action = "run_iverilog_simulation"
    try:
        gate = check_stage_preconditions(proj_dir, "simulation")
        if not gate["allowed"]:
            final_action = (
                f"run_iverilog_simulation_error: blocked_requires_{gate['required_prerequisite']}"
            )
            return gate

        invalidate_downstream_stages(proj_dir, from_stage="simulation")
        res = execute_iverilog_simulation(proj_dir.name, studio_root=STUDIO_ROOT)
        if res.get("status") == "PASS":
            cache_info = validate_and_invalidate_cache(
                proj_dir, mark_domain_fresh="simulation"
            )
        else:
            cache_info = validate_and_invalidate_cache(proj_dir)
            final_action = "run_iverilog_simulation_fail"
        res["rtl_sha256"] = cache_info["rtl_sha256"]
        res["tb_sha256"] = cache_info["tb_sha256"]
        res["invalidated_stale_domains"] = cache_info["invalidated_stale_domains"]
        return res
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def read_waveform(
    project_name: str = "", format_type: str = "hybrid", max_chars: int = 15000
) -> Dict[str, Any]:
    """[LEGACY FULL DUMP — DO NOT USE FOR COI DEBUGGING] Reads full unsliced simulation waveform tables (`wave_full.md`). NEVER call this tool during COI debugging or when `read_coi_sliced_waveform` is used; only call if the user explicitly asks for the raw VCD or full unsliced waveform."""
    proj_dir = begin_tool_execution(project_name, "read_waveform")
    final_action = "read_waveform"
    try:
        comp = ensure_project_structure(proj_dir)
        cache_info = validate_and_invalidate_cache(proj_dir)
        if "simulation" in cache_info["invalidated_stale_domains"]:
            final_action = "SHA-256 cache invalidated stale domains: simulation"
            return {
                "status": "STALE_SIMULATION_INVALIDATED",
                "rtl_sha256": cache_info["rtl_sha256"],
                "message": "RTL modified since last simulation. Stale waveforms purged.",
                "agent_guidance": f"Call run_iverilog_simulation(project_name='{proj_dir.name}') first.",
            }

        sim_dir = comp["simulation"]
        vcd_file = sim_dir / "wave.vcd"
        if not vcd_file.exists():
            final_action = "read_waveform_not_found"
            return {
                "status": "ERROR",
                "message": "wave.vcd not found. Run run_iverilog_simulation first.",
            }

        fmt = format_type.lower().strip()
        if fmt == "raw_vcd":
            raw = vcd_file.read_text(encoding="utf-8", errors="replace")
            return {
                "status": "SUCCESS",
                "format": "raw_vcd",
                "total_chars": len(raw),
                "content": raw[:max_chars],
            }

        wavedrom_file = sim_dir / "wavedrom_full.json"
        table_file = sim_dir / "wave_full.md"
        power_file = comp["reports"] / "power_activity.json"

        if not table_file.exists() or not wavedrom_file.exists():
            convert_vcd_to_artifacts(vcd_file, comp["build"])

        table_md = table_file.read_text(encoding="utf-8")
        wavedrom_json = json.loads(wavedrom_file.read_text(encoding="utf-8"))
        power_json = (
            json.loads(power_file.read_text(encoding="utf-8"))
            if power_file.exists()
            else {}
        )

        return {
            "status": "SUCCESS",
            "format": "hybrid",
            "rtl_sha256": cache_info["rtl_sha256"],
            "cycle_table_md": table_md[:max_chars],
            "wavedrom": wavedrom_json,
            "power_activity": power_json,
        }
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def render_project_schematics(project_name: str = "") -> Dict[str, Any]:
    """Renders interactive SVG schematics (Top RTL, Submodules, and Staged Gate-Level Netlists) into `build/views/`."""
    proj_dir = begin_tool_execution(project_name, "render_project_schematics")
    try:
        return render_project_views(proj_dir.name, studio_root=STUDIO_ROOT)
    finally:
        finish_tool_execution(proj_dir, "render_project_schematics")


@mcp.tool()
def extract_backward_coi(
    project_name: str,
    target_signal: Union[str, List[str]],
    max_hops: int = 4,
    direction: str = "backward",
    combine_mode: str = "union",
) -> Dict[str, Any]:
    """[OPTIONAL DIAGNOSTIC] Extracts the structural Cone of Influence (COI) subgraph from `synth_netlist.json` for debugging simulation failures without advancing the `4.Synth` stage."""
    proj_dir = begin_tool_execution(project_name, "extract_backward_coi")
    try:
        validate_and_invalidate_cache(proj_dir)
        netlist_path = ensure_rtlil_elaboration_for_coi(
            proj_dir.name, studio_root=STUDIO_ROOT
        )
        return extract_coi_subgraph(
            netlist_path,
            target_signals=target_signal,
            max_hops=max_hops,
            direction=direction,
            combine_mode=combine_mode,
        )
    finally:
        finish_tool_execution(proj_dir, "extract_backward_coi")


@mcp.tool()
def read_coi_sliced_waveform(
    project_name: str,
    target_signal: Union[str, List[str]] = "",
    explicit_signals: Union[str, List[str]] = "",
    max_hops: int = 4,
    direction: str = "backward",
    combine_mode: str = "union",
    center_time: Optional[str] = None,
    window_before: str = "-50ns",
    window_after: str = "+10ns",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    start_cycle: int = 0,
    end_cycle: Optional[int] = None,
    hide_constant_signals: bool = False,
) -> Dict[str, Any]:
    """[OPTIONAL DIAGNOSTIC] Slices `wave.vcd` by structural Cone of Influence and time window around `center_time` (`t0`), writing Post-Posedge (`t`) vs. Pre-Posedge Setup (`t - 1ps`) tables to `build/simulation/wave_slice.md`."""
    proj_dir = begin_tool_execution(project_name, "read_coi_sliced_waveform")
    final_action = "read_coi_sliced_waveform"
    try:
        comp = ensure_project_structure(proj_dir)
        cache_info = validate_and_invalidate_cache(proj_dir)
        if "simulation" in cache_info["invalidated_stale_domains"]:
            final_action = "SHA-256 cache invalidated stale domains: simulation"
            return {
                "status": "STALE_SIMULATION_INVALIDATED",
                "rtl_sha256": cache_info["rtl_sha256"],
                "message": "RTL changed since last simulation. Call run_iverilog_simulation first.",
            }

        vcd_path = comp["simulation"] / "wave.vcd"
        if not vcd_path.exists():
            final_action = "read_coi_sliced_waveform_no_vcd"
            return {
                "status": "ERROR",
                "message": "wave.vcd not found. Call run_iverilog_simulation first.",
            }

        coi_set: Set[str] = set()
        coi_res: Dict[str, Any] = {}
        has_coi_target = (
            bool(target_signal.strip())
            if isinstance(target_signal, str)
            else bool(target_signal)
        )
        if has_coi_target:
            netlist_path = ensure_rtlil_elaboration_for_coi(
                proj_dir.name, studio_root=STUDIO_ROOT
            )
            coi_res = extract_coi_subgraph(
                netlist_path,
                target_signals=target_signal,
                max_hops=max_hops,
                direction=direction,
                combine_mode=combine_mode,
            )
            if coi_res.get("status") != "SUCCESS":
                final_action = "read_coi_sliced_waveform_coi_error"
                return coi_res
            coi_set = set(coi_res.get("coi_signals", []))

        sliced_wave = convert_vcd_to_artifacts(
            vcd_path=vcd_path,
            work_dir=comp["build"],
            filter_signals=coi_set if coi_set else None,
            explicit_signals=explicit_signals if explicit_signals else None,
            start_cycle=start_cycle,
            end_cycle=end_cycle,
            center_time=center_time,
            window_before=window_before,
            window_after=window_after,
            start_time=start_time,
            end_time=end_time,
            hide_constant_signals=hide_constant_signals,
        )

        return {
            "status": "SUCCESS",
            "rtl_sha256": cache_info["rtl_sha256"],
            "coi_targets_resolved": coi_res.get("target_signals_resolved", []),
            "sequential_coi_signals": coi_res.get("sequential_coi_signals", []),
            "combinational_coi_signals": coi_res.get("combinational_coi_signals", []),
            "signals_included": sliced_wave.get("signals_included", []),
            "unpacked_array_proxy_notes": sliced_wave.get("unpacked_array_proxy_notes", []),
            "x_z_anomalies": sliced_wave.get("x_z_anomalies", []),
            "anchor_t0_ns": sliced_wave.get("anchor_t0_ns"),
            "slice_file_written": sliced_wave.get("slice_file_written"),
            "cycle_table_md": sliced_wave.get("cycle_table_md"),
            "wavedrom": sliced_wave.get("wavedrom_json"),
        }
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def post_agent_handoff(
    project_name: str,
    from_agent: str,
    to_agent: str,
    status: str,
    summary: str,
    anchor_time_ns: str = "",
    coi_signals: str = "",
    suspect_rtl_location: str = "",
    evidence_and_action: str = "",
    ticket_id: Optional[str] = None,
    kb_rule_id: str = "",
) -> Dict[str, Any]:
    """Posts or updates an inter-agent handoff ticket on the Blackboard (`build/agent_bus/active_ticket.md`), recording COI evidence, `t0`, suspect RTL line, and `kb_rule_id`."""
    proj_dir = begin_tool_execution(
        project_name, f"post_agent_handoff ({from_agent} -> {to_agent})"
    )
    final_action = f"post_handoff ({from_agent} -> {to_agent})"
    try:
        res = post_handoff_ticket(
            project_name=proj_dir.name,
            from_agent=from_agent,
            to_agent=to_agent,
            status=status,
            summary=summary,
            anchor_time_ns=anchor_time_ns,
            coi_signals=coi_signals,
            suspect_rtl_location=suspect_rtl_location,
            evidence_and_action=evidence_and_action,
            ticket_id=ticket_id,
            kb_rule_id=kb_rule_id,
        )
        t_id = res.get("ticket", {}).get("ticket_id", "TICKET")
        final_action = f"post_handoff:{t_id} ({from_agent} -> {to_agent})"
        return res
    finally:
        finish_tool_execution(proj_dir, final_action)


@mcp.tool()
def read_agent_handoff(project_name: str = "") -> Dict[str, Any]:
    """Reads the latest inter-agent handoff ticket and ticket history from `build/agent_bus/agent_bus.json`."""
    proj_dir = begin_tool_execution(project_name, "read_agent_handoff")
    try:
        return read_handoff_tickets(proj_dir.name)
    finally:
        finish_tool_execution(proj_dir, "read_agent_handoff")


@mcp.tool()
def query_design_knowledge(
    domain: Literal["cdc", "lint", "fsm", "sdc", "ppa"],
    symptom_or_pattern: str,
    project_name: str = "",
) -> Dict[str, Any]:
    """Searches canary-validated silicon design playbooks (`cdc`, `lint`, `fsm`, `sdc`, `ppa`) and returns the golden SystemVerilog/SDC template. Call BEFORE writing or patching RTL for CDC, lint, FSM, or PPA issues."""
    res = query_rule(domain=domain, symptom_or_pattern=symptom_or_pattern)
    if project_name and project_name.strip():
        proj_dir = begin_tool_execution(
            project_name, f"query_design_knowledge ({domain})"
        )
        rule_tag = res.get("rule", {}).get("rule_id", "MISS")
        finish_tool_execution(proj_dir, f"query_kb:{domain}:{rule_tag}")
    return res


if __name__ == "__main__":
    mcp.run()
