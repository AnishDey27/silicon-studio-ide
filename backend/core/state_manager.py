# =============================================================================
# File Path: backend/core/state_manager.py
# =============================================================================
"""Single-Point Telemetry Spine, Strict 4-Stage Pipeline State Machine & Bundle Assembler.

Key V3.3 Fix:
- Synchronizes the Ticket Pool (`agent_bus.json` / `active_ticket.md`) with Pipeline
  Stage Invalidation:
  1. When `invalidate_downstream_stages()` invalidates `synthesis` (e.g. when `1.Hier`,
     `2.Lint`, or `3.Sim` is re-run), any previous `TAPEOUT_READY` sign-off ticket from
     an earlier run is immediately purged so stale sign-offs never linger while synthesis
     is pending/stale.
  2. When `from_stage == "hierarchy"` is re-run to start a fresh flow, previous-run
     tickets are cleared so the new flow starts with a clean Blackboard.
"""
import datetime
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.core.workspace_manager import (
    STUDIO_ROOT,
    atomic_read_json,
    atomic_write_json,
    ensure_project_structure,
    get_active_project_name,
    get_project_dir,
    list_all_projects,
    load_workspace_context,
    select_active_project,
)

EXECUTION_TIMEOUT_SEC = 35.0
MAX_HISTORY_ITEMS = 250

MANDATORY_STAGE_ORDER = ("hierarchy", "lint", "simulation", "synthesis")

STAGE_PREREQUISITES: Dict[str, Tuple[str, ...]] = {
    "hierarchy": (),
    "lint": ("hierarchy",),
    "simulation": ("hierarchy", "lint"),
    "synthesis": ("hierarchy", "lint", "simulation"),
}

STAGE_DISPLAY_LABELS: Dict[str, str] = {
    "hierarchy": "1. Hier (resolve_project_hierarchy)",
    "lint": "2. Lint (run_verilator_lint)",
    "simulation": "3. Sim (run_iverilog_simulation)",
    "synthesis": "4. Synth (run_yosys_synthesis)",
}

_PROJECT_STATE_MEMORY: Dict[str, Dict[str, Any]] = {}


def _hash_directory_files(folder: Path, suffixes: Tuple[str, ...]) -> str:
    """Computes a 16-char SHA-256 digest over all matching files and their relative paths."""
    h = hashlib.sha256()
    if not folder.exists():
        return h.hexdigest()[:16]
    files = sorted(
        f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in suffixes
    )
    for f in files:
        rel = f.relative_to(folder).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        try:
            h.update(f.read_bytes())
        except OSError:
            pass
        h.update(b"\x00")
    return h.hexdigest()[:16]


def compute_project_hashes(project_dir: Path) -> Dict[str, str]:
    """Computes current SHA-256 digests for `src/` (RTL) and `verif/` (Testbench + vectors)."""
    rtl_hash = _hash_directory_files(project_dir / "src", (".sv", ".v", ".vh", ".svh"))
    tb_hash = _hash_directory_files(
        project_dir / "verif", (".sv", ".v", ".mem", ".hex", ".txt")
    )
    return {"rtl_sha256": rtl_hash, "tb_sha256": tb_hash}


def _merge_tool_histories(
    existing_list: List[Dict[str, Any]],
    incoming_list: List[Dict[str, Any]],
    proj_name: str = "",
    max_items: int = MAX_HISTORY_ITEMS,
) -> List[Dict[str, Any]]:
    """Merges two `tool_history` lists chronologically while enforcing strict project isolation."""
    combined: List[Dict[str, Any]] = []
    seen_keys = set()
    for item in (existing_list or []) + (incoming_list or []):
        if not isinstance(item, dict):
            continue
        item_proj = str(item.get("project_name", "")).strip()
        if proj_name and item_proj and item_proj != proj_name:
            continue
        if proj_name and not item_proj:
            item["project_name"] = proj_name
        ts = str(item.get("timestamp", ""))
        act = str(item.get("action", "")).strip()
        st = str(item.get("status", "")).strip()
        key = f"{ts}|{act}|{st}"
        if key in seen_keys:
            continue
        if combined:
            prev = combined[-1]
            prev_act = str(prev.get("action", "")).strip()
            prev_st = str(prev.get("status", "")).strip()
            if prev_act == act and prev_st == st and ts[:7] == str(prev.get("timestamp", ""))[:7]:
                seen_keys.add(key)
                continue
        seen_keys.add(key)
        combined.append(item)
    return combined[-max_items:]


def _load_persistent_ledger(project_dir: Path) -> List[Dict[str, Any]]:
    ledger_path = project_dir / "build" / "agent_bus" / "tool_history.json"
    data = atomic_read_json(ledger_path)
    if data and isinstance(data.get("history"), list):
        return [
            item
            for item in data["history"]
            if isinstance(item, dict)
            and item.get("project_name") in (None, "", project_dir.name)
        ]
    return []


def _save_persistent_ledger(project_dir: Path, history: List[Dict[str, Any]]) -> None:
    ledger_path = project_dir / "build" / "agent_bus" / "tool_history.json"
    atomic_write_json(
        ledger_path,
        {"project_name": project_dir.name, "history": history[-MAX_HISTORY_ITEMS:]},
    )


def load_project_state(project_dir: Path) -> Dict[str, Any]:
    """Loads `build/agent_bus/session_state.json` merged with in-memory and ledger history."""
    ensure_project_structure(project_dir)
    proj_key = project_dir.name
    state_path = project_dir / "build" / "agent_bus" / "session_state.json"
    disk_state = atomic_read_json(state_path)
    mem_state = _PROJECT_STATE_MEMORY.get(proj_key)
    ledger_history = _load_persistent_ledger(project_dir)

    if disk_state is not None and disk_state.get("project_name") in (None, "", proj_key):
        state = dict(disk_state)
    elif mem_state is not None:
        state = dict(mem_state)
    else:
        state = {
            "project_name": proj_key,
            "active_project": proj_key,
            "rtl_sha256": None,
            "tb_sha256": None,
            "hier_rtl_sha256": None,
            "lint_rtl_sha256": None,
            "synth_rtl_sha256": None,
            "sim_rtl_sha256": None,
            "sim_tb_sha256": None,
            "synthesized_targets": [],
            "last_action": None,
            "updated_at": None,
            "completed_stages": [],
            "stale_stages": [],
            "failed_stages": [],
            "active_agent": "@eda-lead",
            "tool_history": [],
            "is_executing": False,
        }

    mem_history = mem_state.get("tool_history", []) if mem_state else []
    merged_history = _merge_tool_histories(ledger_history, mem_history, proj_name=proj_key)
    merged_history = _merge_tool_histories(
        merged_history, state.get("tool_history", []), proj_name=proj_key
    )
    state["tool_history"] = merged_history

    if mem_state and not state.get("completed_stages") and mem_state.get("completed_stages"):
        state["completed_stages"] = list(mem_state["completed_stages"])

    if state.get("is_executing"):
        last_up = state.get("updated_at")
        if last_up:
            try:
                ts = datetime.datetime.fromisoformat(last_up).timestamp()
                if time.time() - ts > EXECUTION_TIMEOUT_SEC:
                    state["is_executing"] = False
            except Exception:
                state["is_executing"] = False

    _PROJECT_STATE_MEMORY[proj_key] = dict(state)
    return state


def save_project_state(project_dir: Path, state: Dict[str, Any]) -> None:
    """Atomically saves `session_state.json` and updates `tool_history.json`."""
    ensure_project_structure(project_dir)
    state["project_name"] = project_dir.name
    state["active_project"] = project_dir.name
    state["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    ledger_history = _load_persistent_ledger(project_dir)
    merged_history = _merge_tool_histories(
        ledger_history, state.get("tool_history", []), proj_name=project_dir.name
    )
    state["tool_history"] = merged_history

    _PROJECT_STATE_MEMORY[project_dir.name] = dict(state)
    _save_persistent_ledger(project_dir, merged_history)
    atomic_write_json(project_dir / "build" / "agent_bus" / "session_state.json", state)


def _prune_stale_tickets_on_disk(
    build_dir: Path,
    proj_name: str,
    current_rtl_sha: str,
    sim_passed: bool,
    synth_passed: bool = False,
) -> List[Dict[str, Any]]:
    """Synchronizes `agent_bus.json` with both SHA-256 state AND current pipeline stage completion.

    - A `TAPEOUT_READY` ticket is ONLY valid if `synth_passed` is True on `current_rtl_sha`.
      If synthesis was invalidated (e.g. by re-running `1.Hier`, `2.Lint`, or `3.Sim`),
      any prior `TAPEOUT_READY` ticket from an earlier session is purged immediately!
    - A `VERIFIED_PASS` ticket is ONLY valid if `sim_passed` is True on `current_rtl_sha`.
    - An `OPEN_BUG` / `FAIL` ticket is purged as soon as `sim_passed` or `synth_passed` is True.
    """
    bus_file = build_dir / "agent_bus" / "agent_bus.json"
    active_ticket_file = build_dir / "agent_bus" / "active_ticket.md"
    bus_data = atomic_read_json(bus_file)
    if not bus_data or not isinstance(bus_data.get("tickets"), list):
        return []

    raw_tickets = bus_data["tickets"]
    closing_statuses = {"TAPEOUT_READY", "VERIFIED_PASS"}
    bug_statuses = {"OPEN_BUG", "FAIL", "RTL_FIXED_PENDING_SIM"}

    has_closing_on_current_sha = any(
        isinstance(t, dict)
        and t.get("rtl_sha256") == current_rtl_sha
        and (
            (str(t.get("status", "")).upper() == "TAPEOUT_READY" and synth_passed)
            or (str(t.get("status", "")).upper() == "VERIFIED_PASS" and sim_passed)
        )
        for t in raw_tickets
    )

    kept_tickets: List[Dict[str, Any]] = []
    for t in raw_tickets:
        if not isinstance(t, dict):
            continue
        if t.get("project_name") not in (None, "", proj_name):
            continue
        t_sha = t.get("rtl_sha256", "")
        t_status = str(t.get("status", "")).upper()

        # 1. If synthesis is NOT currently completed, a TAPEOUT_READY ticket is stale!
        if t_status == "TAPEOUT_READY" and not synth_passed:
            continue

        # 2. If simulation is NOT currently completed, a VERIFIED_PASS ticket is stale!
        if t_status == "VERIFIED_PASS" and not sim_passed:
            continue

        # 3. Drop any ticket from an older RTL SHA once simulation passes or sign-off is reached
        if t_sha and current_rtl_sha and t_sha != current_rtl_sha:
            if t_status in closing_statuses or sim_passed or synth_passed or has_closing_on_current_sha:
                continue

        # 4. Drop superseded OPEN_BUG tickets once simulation passes or sign-off is reached
        if (sim_passed or synth_passed or has_closing_on_current_sha) and t_status in bug_statuses:
            continue

        kept_tickets.append(t)

    for idx, item in enumerate(kept_tickets, start=1):
        item["ticket_id"] = f"TICKET-{idx:03d}"

    if len(kept_tickets) != len(raw_tickets):
        bus_data["tickets"] = kept_tickets
        bus_data["latest_ticket"] = kept_tickets[-1] if kept_tickets else {}
        atomic_write_json(bus_file, bus_data)
        if not kept_tickets and active_ticket_file.exists():
            try:
                active_ticket_file.unlink()
            except OSError:
                pass

    return kept_tickets


def _purge_stage_files(build_dir: Path, stage: str) -> None:
    """Purges physical artifacts on disk when a stage is invalidated."""
    def _rm(directory: Path, patterns: Tuple[str, ...]) -> None:
        if not directory.exists():
            return
        for pat in patterns:
            for p in directory.glob(pat):
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except OSError:
                    pass

    if stage == "lint":
        _rm(build_dir / "reports", ("lint_report.txt",))
    elif stage == "simulation":
        _rm(build_dir / "simulation", ("*.vcd", "*.md", "*.json", "*.fst", "*.out"))
        _rm(build_dir / "reports", ("sim_report.txt", "power_activity.json"))
    elif stage == "synthesis":
        _rm(build_dir / "netlists", ("synth_netlist.json", "mapped_*"))
        _rm(
            build_dir / "reports",
            ("synth_qor_*.json", "synth_stat*.txt", "synth_report.json", "ppa_comparison_matrix.md"),
        )
        _rm(build_dir / "views", ("schematic_*.svg",))


def invalidate_downstream_stages(project_dir: Path, from_stage: str) -> List[str]:
    """Strictly invalidates all dependent stages after `from_stage` AND purges invalidated sign-off tickets."""
    if from_stage not in MANDATORY_STAGE_ORDER:
        return []
    state = load_project_state(project_dir)
    build_dir = project_dir / "build"
    hashes = compute_project_hashes(project_dir)
    completed = set(state.get("completed_stages", []))
    stale = set(state.get("stale_stages", []))
    failed = set(state.get("failed_stages", []))

    start_idx = MANDATORY_STAGE_ORDER.index(from_stage) + 1
    invalidated: List[str] = []
    for down_stg in MANDATORY_STAGE_ORDER[start_idx:]:
        if down_stg in completed or down_stg in failed:
            stale.add(down_stg)
            completed.discard(down_stg)
            failed.discard(down_stg)
            invalidated.append(down_stg)
        _purge_stage_files(build_dir, down_stg)
        if down_stg == "lint":
            state["lint_rtl_sha256"] = None
        elif down_stg == "simulation":
            state["sim_rtl_sha256"] = None
            state["sim_tb_sha256"] = None
            completed.discard("coi")
            stale.discard("coi")
        elif down_stg == "synthesis":
            state["synth_rtl_sha256"] = None
            state["synthesized_targets"] = []

    state["completed_stages"] = sorted(list(completed))
    state["stale_stages"] = sorted(list(stale))
    state["failed_stages"] = sorted(list(failed))

    # Sync ticket pool with the newly invalidated stages (e.g. if synthesis was invalidated,
    # any old TAPEOUT_READY ticket from a previous run is immediately removed!)
    sim_still_valid = "simulation" in completed and "simulation" not in stale
    synth_still_valid = "synthesis" in completed and "synthesis" not in stale
    _prune_stale_tickets_on_disk(
        build_dir,
        proj_name=project_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed=sim_still_valid,
        synth_passed=synth_still_valid,
    )

    save_project_state(project_dir, state)
    return invalidated


def check_stage_preconditions(project_dir: Path, target_stage: str) -> Dict[str, Any]:
    """Enforces the strict 1.Hier -> 2.Lint -> 3.Sim -> 4.Synth execution sequence."""
    validate_and_invalidate_cache(project_dir)
    state = load_project_state(project_dir)
    completed = set(state.get("completed_stages", []))
    stale = set(state.get("stale_stages", []))
    failed = set(state.get("failed_stages", []))

    prereqs = STAGE_PREREQUISITES.get(target_stage, ())
    missing: List[Dict[str, str]] = []
    for req in prereqs:
        if req not in completed or req in stale or req in failed:
            cur_st = "STALE" if req in stale else ("FAIL" if req in failed else "PENDING")
            missing.append(
                {
                    "stage": req,
                    "label": STAGE_DISPLAY_LABELS.get(req, req),
                    "current_status": cur_st,
                }
            )

    if missing:
        first_req = missing[0]
        return {
            "allowed": False,
            "status": "BLOCKED_SEQUENCE_VIOLATION",
            "project_name": project_dir.name,
            "blocked_stage": STAGE_DISPLAY_LABELS.get(target_stage, target_stage),
            "required_prerequisite": first_req["label"],
            "missing_prerequisites": missing,
            "completed_stages": sorted(list(completed)),
            "stale_stages": sorted(list(stale)),
            "message": (
                f"Strict Pipeline Sequence Violation: Cannot execute '{STAGE_DISPLAY_LABELS.get(target_stage, target_stage)}' "
                f"until prerequisite stage '{first_req['label']}' is complete and PASS "
                f"(current status: {first_req['current_status']})."
            ),
            "agent_guidance": (
                f"Follow the strict pipeline order: 1.Hier -> 2.Lint -> 3.Sim -> 4.Synth. "
                f"Call {first_req['label']} for project '{project_dir.name}' first."
            ),
        }

    return {"allowed": True}


def _reconcile_completed_stages_from_disk(
    project_dir: Path, state: Dict[str, Any], hashes: Dict[str, str]
) -> None:
    """Reconciles `completed_stages` with non-stale artifacts on disk while respecting sequential order."""
    build_dir = project_dir / "build"
    completed = set(state.get("completed_stages", []))
    stale = set(state.get("stale_stages", []))
    failed = set(state.get("failed_stages", []))

    if (build_dir / "agent_bus" / "hierarchy.json").exists() and "hierarchy" not in stale:
        completed.add("hierarchy")

    lint_file = build_dir / "reports" / "lint_report.txt"
    if lint_file.exists() and "lint" not in stale and "hierarchy" in completed:
        txt = lint_file.read_text(encoding="utf-8", errors="replace")
        if "%Warning-" not in txt and "%Error" not in txt:
            completed.add("lint")
            failed.discard("lint")
            if state.get("lint_rtl_sha256") is None:
                state["lint_rtl_sha256"] = hashes["rtl_sha256"]
        else:
            failed.add("lint")
            completed.discard("lint")

    sim_file = build_dir / "reports" / "sim_report.txt"
    if sim_file.exists() and "simulation" not in stale and "lint" in completed:
        txt = sim_file.read_text(encoding="utf-8", errors="replace").upper()
        if "[FAIL]" not in txt and "[TB_FAIL]" not in txt and "ERROR" not in txt and "FATAL" not in txt:
            completed.add("simulation")
            failed.discard("simulation")
            if state.get("sim_rtl_sha256") is None:
                state["sim_rtl_sha256"] = hashes["rtl_sha256"]
            if state.get("sim_tb_sha256") is None:
                state["sim_tb_sha256"] = hashes["tb_sha256"]
        else:
            failed.add("simulation")
            completed.discard("simulation")

    if (build_dir / "simulation" / "wave_slice.md").exists() and "coi" not in stale:
        completed.add("coi")

    if (
        (build_dir / "reports" / "synth_report.json").exists()
        and "synthesis" not in stale
        and "simulation" in completed
    ):
        completed.add("synthesis")
        if state.get("synth_rtl_sha256") is None:
            state["synth_rtl_sha256"] = hashes["rtl_sha256"]
    else:
        completed.discard("synthesis")

    state["completed_stages"] = sorted(list(completed))
    state["stale_stages"] = sorted(list(stale))
    state["failed_stages"] = sorted(list(failed))


def validate_and_invalidate_cache(
    project_dir: Path,
    mark_domain_fresh: Optional[str] = None,
    synth_target: Optional[str] = None,
) -> Dict[str, Any]:
    """Reconciles cached artifacts in `build/` with source hashes and purges stale outputs."""
    ensure_project_structure(project_dir)
    hashes = compute_project_hashes(project_dir)
    state = load_project_state(project_dir)
    build_dir = project_dir / "build"
    invalidated: List[str] = []
    stale_stages = set(state.get("stale_stages", []))
    completed_stages = set(state.get("completed_stages", []))
    failed_stages = set(state.get("failed_stages", []))

    if mark_domain_fresh == "simulation":
        state["sim_rtl_sha256"] = hashes["rtl_sha256"]
        state["sim_tb_sha256"] = hashes["tb_sha256"]
        stale_stages.discard("simulation")
        stale_stages.discard("coi")
        failed_stages.discard("simulation")
        completed_stages.add("simulation")
    elif mark_domain_fresh == "synthesis":
        state["synth_rtl_sha256"] = hashes["rtl_sha256"]
        stale_stages.discard("synthesis")
        failed_stages.discard("synthesis")
        completed_stages.add("synthesis")
        targets = list(state.get("synthesized_targets", []))
        if synth_target and synth_target not in targets:
            targets.append(synth_target)
        state["synthesized_targets"] = targets
    elif mark_domain_fresh == "lint":
        state["lint_rtl_sha256"] = hashes["rtl_sha256"]
        stale_stages.discard("lint")
        failed_stages.discard("lint")
        completed_stages.add("lint")

    previous_rtl = state.get("rtl_sha256")
    previous_tb = state.get("tb_sha256")
    rtl_changed = previous_rtl is not None and previous_rtl != hashes["rtl_sha256"]
    tb_changed = previous_tb is not None and previous_tb != hashes["tb_sha256"]

    has_sim_artifacts = (
        (build_dir / "simulation" / "wave.vcd").exists()
        or (build_dir / "reports" / "sim_report.txt").exists()
    )
    simulation_stale = (
        mark_domain_fresh != "simulation"
        and has_sim_artifacts
        and (
            rtl_changed
            or tb_changed
            or (state.get("sim_rtl_sha256") not in (None, hashes["rtl_sha256"]))
            or (state.get("sim_tb_sha256") not in (None, hashes["tb_sha256"]))
        )
    )
    if simulation_stale:
        _purge_stage_files(build_dir, "simulation")
        invalidated.append("simulation")
        stale_stages.add("simulation")
        completed_stages.discard("simulation")
        completed_stages.discard("coi")
        stale_stages.discard("coi")
        state["sim_rtl_sha256"] = None
        state["sim_tb_sha256"] = None
    else:
        state["sim_rtl_sha256"] = hashes["rtl_sha256"] if has_sim_artifacts else None
        state["sim_tb_sha256"] = hashes["tb_sha256"] if has_sim_artifacts else None

    has_synth_artifacts = (build_dir / "reports" / "synth_report.json").exists()
    synthesis_stale = (
        mark_domain_fresh != "synthesis"
        and has_synth_artifacts
        and (
            rtl_changed
            or (state.get("synth_rtl_sha256") not in (None, hashes["rtl_sha256"]))
        )
    )
    if synthesis_stale:
        _purge_stage_files(build_dir, "synthesis")
        invalidated.append("synthesis")
        stale_stages.add("synthesis")
        completed_stages.discard("synthesis")
        state["synth_rtl_sha256"] = None
        state["synthesized_targets"] = []
    else:
        state["synth_rtl_sha256"] = hashes["rtl_sha256"] if has_synth_artifacts else None

    has_lint_artifacts = (build_dir / "reports" / "lint_report.txt").exists()
    lint_stale = (
        mark_domain_fresh != "lint"
        and has_lint_artifacts
        and (
            rtl_changed
            or (state.get("lint_rtl_sha256") not in (None, hashes["rtl_sha256"]))
        )
    )
    if lint_stale:
        _purge_stage_files(build_dir, "lint")
        invalidated.append("lint")
        stale_stages.add("lint")
        completed_stages.discard("lint")
        state["lint_rtl_sha256"] = None
    else:
        state["lint_rtl_sha256"] = hashes["rtl_sha256"] if has_lint_artifacts else None

    if invalidated:
        history = list(state.get("tool_history", []))
        inval_msg = f"SHA-256 cache invalidated stale domains: {', '.join(invalidated)}"
        if not history or history[-1].get("action") != inval_msg:
            now_ms = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            history.append(
                {
                    "project_name": project_dir.name,
                    "timestamp": now_ms,
                    "domain": "EDA",
                    "action": inval_msg,
                    "agent": state.get("active_agent", "@rtl-architect"),
                    "status": "STALE",
                }
            )
            state["tool_history"] = history[-MAX_HISTORY_ITEMS:]

    state["stale_stages"] = sorted(list(stale_stages))
    state["completed_stages"] = sorted(list(completed_stages))
    state["failed_stages"] = sorted(list(failed_stages))
    state.update(hashes)
    _reconcile_completed_stages_from_disk(project_dir, state, hashes)

    sim_now_passing = (
        "simulation" in state.get("completed_stages", [])
        and "simulation" not in state.get("stale_stages", [])
        and "simulation" not in state.get("failed_stages", [])
    )
    synth_now_passing = (
        "synthesis" in state.get("completed_stages", [])
        and "synthesis" not in state.get("stale_stages", [])
        and "synthesis" not in state.get("failed_stages", [])
    )
    _prune_stale_tickets_on_disk(
        build_dir,
        proj_name=project_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed=sim_now_passing,
        synth_passed=synth_now_passing,
    )

    save_project_state(project_dir, state)
    return {
        **hashes,
        "invalidated_stale_domains": invalidated,
        "stale_stages": state["stale_stages"],
        "synthesized_targets": state.get("synthesized_targets", []),
    }


def infer_active_agent_from_action(action: str) -> str:
    """Maps a tool action string to the responsible silicon agent persona."""
    act_lower = action.lower()
    if "-> @rtl-architect" in act_lower:
        return "@rtl-architect"
    if "-> @dv-debugger" in act_lower:
        return "@dv-debugger"
    if "-> @synth-qor" in act_lower:
        return "@synth-qor"
    if "-> @eda-lead" in act_lower:
        return "@eda-lead"
    if "query_design_knowledge" in act_lower or "query_kb" in act_lower:
        if "(sdc" in act_lower or "(ppa" in act_lower or ":sdc:" in act_lower or ":ppa:" in act_lower:
            return "@synth-qor"
        return "@rtl-architect"
    if "hierarchy" in act_lower or "lint" in act_lower:
        return "@rtl-architect"
    if "simulation" in act_lower or "coi" in act_lower or "waveform" in act_lower or "triage" in act_lower:
        return "@dv-debugger"
    if "synthesis" in act_lower or "schematic" in act_lower or "ppa" in act_lower or "views" in act_lower:
        return "@synth-qor"
    return "@eda-lead"


def _classify_telemetry_domain_and_status(build_dir: Path, last_action: str) -> Tuple[str, str]:
    act_low = last_action.lower()
    domain = "EDA"
    status = "PASS"

    if "error" in act_low or "fail" in act_low or "blocked" in act_low:
        return domain, "FAIL"

    if "lint" in act_low or "hierarchy" in act_low:
        domain = "RTL"
        lint_file = build_dir / "reports" / "lint_report.txt"
        if "lint" in act_low and lint_file.exists():
            txt = lint_file.read_text(encoding="utf-8", errors="replace")
            if "%Warning-" in txt or "%Error" in txt:
                status = "FAIL"
    elif "simulation" in act_low or "coi" in act_low or "waveform" in act_low:
        domain = "EDA"
        sim_file = build_dir / "reports" / "sim_report.txt"
        if "simulation" in act_low and sim_file.exists():
            txt = sim_file.read_text(encoding="utf-8", errors="replace").upper()
            if "FAIL" in txt or "FATAL" in txt or "COMPILE_FAIL" in act_low.upper():
                status = "FAIL"
    elif "synthesis" in act_low or "schematic" in act_low or "views" in act_low:
        domain = "RTL"
        qor_file = build_dir / "reports" / "synth_report.json"
        if "synthesis" in act_low and qor_file.exists():
            qdata = atomic_read_json(qor_file) or {}
            if qdata.get("status") not in (None, "PASS", "SUCCESS"):
                status = "FAIL"
    elif "query_kb" in act_low or "query_design_knowledge" in act_low:
        domain = "KB"
        if ":miss" in act_low:
            status = "STALE"
    elif "handoff" in act_low:
        domain = "EDA"
        bus_file = build_dir / "agent_bus" / "agent_bus.json"
        bus_data = atomic_read_json(bus_file) or {}
        latest_st = bus_data.get("latest_ticket", {}).get("status", "")
        if "BUG" in latest_st or "FAIL" in latest_st:
            status = "FAIL"

    return domain, status


def begin_tool_execution(project_name: str, action: str) -> Path:
    """Pre-flight hook called ONLY by the MCP server before dispatching a tool."""
    resolved_name = get_active_project_name(project_name)
    proj_dir = get_project_dir(resolved_name, create_if_missing=True)
    state = load_project_state(proj_dir)

    if state.get("rtl_sha256") is None or state.get("tb_sha256") is None:
        hashes = compute_project_hashes(proj_dir)
        if state.get("rtl_sha256") is None:
            state["rtl_sha256"] = hashes["rtl_sha256"]
        if state.get("tb_sha256") is None:
            state["tb_sha256"] = hashes["tb_sha256"]

    active_agent = infer_active_agent_from_action(action)
    state["project_name"] = proj_dir.name
    state["active_project"] = proj_dir.name
    state["last_action"] = action
    state["is_executing"] = True
    state["active_agent"] = active_agent
    save_project_state(proj_dir, state)

    select_active_project(
        proj_dir.name,
        switched_by=f"mcp_agent:{active_agent}",
        create_if_missing=True,
        active_agent=active_agent,
        is_executing=True,
        last_action=action,
        rtl_sha256=state.get("rtl_sha256"),
        tb_sha256=state.get("tb_sha256"),
    )
    return proj_dir


def finish_tool_execution(project_dir: Path, last_action: str) -> Dict[str, Any]:
    """Post-flight hook called ONLY once per MCP tool completion."""
    ensure_project_structure(project_dir)
    build_dir = project_dir / "build"
    hashes = compute_project_hashes(project_dir)
    state = load_project_state(project_dir)

    state["project_name"] = project_dir.name
    state["active_project"] = project_dir.name
    state["last_action"] = last_action
    state.update(hashes)

    stages = set(state.get("completed_stages", []))
    stale = set(state.get("stale_stages", []))
    failed = set(state.get("failed_stages", []))
    act_lower = last_action.lower()
    is_error_or_inval = (
        "error" in act_lower
        or "fail" in act_lower
        or "blocked" in act_lower
        or "invalidated" in act_lower
        or "not_found" in act_lower
    )

    if not is_error_or_inval:
        if "hierarchy" in act_lower:
            stages.add("hierarchy")
            stale.discard("hierarchy")
            failed.discard("hierarchy")
            state["hier_rtl_sha256"] = hashes["rtl_sha256"]
        if "lint" in act_lower:
            stages.add("lint")
            stale.discard("lint")
            failed.discard("lint")
            state["lint_rtl_sha256"] = hashes["rtl_sha256"]
        if "simulation" in act_lower:
            stages.add("simulation")
            stale.discard("simulation")
            stale.discard("coi")
            failed.discard("simulation")
            state["sim_rtl_sha256"] = hashes["rtl_sha256"]
            state["sim_tb_sha256"] = hashes["tb_sha256"]
        if "coi" in act_lower or "waveform" in act_lower:
            stages.add("coi")
            stale.discard("coi")
        if (
            "synthesis" in act_lower
            or "render_project_views" in act_lower
            or "render_project_schematics" in act_lower
        ):
            stages.add("synthesis")
            stale.discard("synthesis")
            failed.discard("synthesis")
            state["synth_rtl_sha256"] = hashes["rtl_sha256"]
            if "run_yosys_synthesis:" in act_lower:
                tgt = last_action.split(":", 1)[-1].strip()
                targets = list(state.get("synthesized_targets", []))
                if tgt and tgt not in targets:
                    targets.append(tgt)
                state["synthesized_targets"] = targets

    active_agent = infer_active_agent_from_action(last_action)
    domain_tag, status_badge = _classify_telemetry_domain_and_status(build_dir, last_action)

    state["completed_stages"] = sorted(list(stages))
    state["stale_stages"] = sorted(list(stale))
    state["failed_stages"] = sorted(list(failed))
    _reconcile_completed_stages_from_disk(project_dir, state, hashes)
    state["active_agent"] = active_agent
    state["is_executing"] = False

    now_ms = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    history = list(state.get("tool_history", []))
    new_entry = {
        "project_name": project_dir.name,
        "timestamp": now_ms,
        "domain": domain_tag,
        "action": last_action,
        "agent": active_agent,
        "status": status_badge,
    }
    if (
        history
        and history[-1].get("action") == last_action
        and history[-1].get("status") == status_badge
        and str(history[-1].get("timestamp", ""))[:7] == now_ms[:7]
    ):
        history[-1] = new_entry
    else:
        history.append(new_entry)
    state["tool_history"] = history[-MAX_HISTORY_ITEMS:]

    sim_now_passing = (
        "simulation" in state.get("completed_stages", [])
        and "simulation" not in state.get("stale_stages", [])
        and "simulation" not in state.get("failed_stages", [])
    )
    synth_now_passing = (
        "synthesis" in state.get("completed_stages", [])
        and "synthesis" not in state.get("stale_stages", [])
        and "synthesis" not in state.get("failed_stages", [])
    )
    _prune_stale_tickets_on_disk(
        build_dir,
        proj_name=project_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed=sim_now_passing,
        synth_passed=synth_now_passing,
    )

    save_project_state(project_dir, state)
    select_active_project(
        project_dir.name,
        switched_by=f"mcp_agent:{active_agent}",
        active_agent=active_agent,
        is_executing=False,
        last_action=last_action,
        rtl_sha256=hashes["rtl_sha256"],
        tb_sha256=hashes["tb_sha256"],
    )
    return state


def assemble_project_bundle(project_name: str = "") -> Dict[str, Any]:
    """Assembles the complete zero-copy state bundle directly from `projects/<name>/build/`."""
    target_name = get_active_project_name(project_name)
    proj_dir = get_project_dir(target_name, create_if_missing=False)
    ensure_project_structure(proj_dir)
    build_dir = proj_dir / "build"

    hashes = compute_project_hashes(proj_dir)
    sess_state = load_project_state(proj_dir)
    if sess_state.get("rtl_sha256") is None:
        sess_state["rtl_sha256"] = hashes["rtl_sha256"]
    if sess_state.get("tb_sha256") is None:
        sess_state["tb_sha256"] = hashes["tb_sha256"]
    _reconcile_completed_stages_from_disk(proj_dir, sess_state, hashes)

    sim_now_passing = (
        "simulation" in sess_state.get("completed_stages", [])
        and "simulation" not in sess_state.get("stale_stages", [])
        and "simulation" not in sess_state.get("failed_stages", [])
    )
    synth_now_passing = (
        "synthesis" in sess_state.get("completed_stages", [])
        and "synthesis" not in sess_state.get("stale_stages", [])
        and "synthesis" not in sess_state.get("failed_stages", [])
    )
    project_tickets = _prune_stale_tickets_on_disk(
        build_dir,
        proj_name=proj_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed=sim_now_passing,
        synth_passed=synth_now_passing,
    )

    hier_file = build_dir / "agent_bus" / "hierarchy.json"
    active_ticket_file = build_dir / "agent_bus" / "active_ticket.md"
    lint_file = build_dir / "reports" / "lint_report.txt"
    sim_file = build_dir / "reports" / "sim_report.txt"
    power_file = build_dir / "reports" / "power_activity.json"
    ppa_file = build_dir / "reports" / "ppa_comparison_matrix.md"
    slice_file = build_dir / "simulation" / "wave_slice.md"
    coi_graph_file = build_dir / "simulation" / "coi_graph.json"
    wavedrom_file = build_dir / "simulation" / "wavedrom_slice.json"
    if not wavedrom_file.exists():
        wavedrom_file = build_dir / "simulation" / "wavedrom_full.json"

    def _read_txt(p: Path) -> str:
        if not p.exists():
            return ""
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    svg_map: Dict[str, str] = {}
    views_dir = build_dir / "views"
    if views_dir.exists():
        for svg_p in sorted(views_dir.glob("*.svg")):
            raw_svg = _read_txt(svg_p)
            if "<svg" in raw_svg:
                svg_map[svg_p.stem] = raw_svg[raw_svg.find("<svg") :]

    latest_ticket = project_tickets[-1] if project_tickets else {}
    hier_data = atomic_read_json(hier_file) or {}
    coi_graph_data = atomic_read_json(coi_graph_file) or {}
    ws_ctx = load_workspace_context()

    return {
        "type": "WORKSPACE_UPDATE",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "workspace_context": ws_ctx,
        "available_projects": list_all_projects(),
        "session_state": sess_state,
        "hierarchy": hier_data,
        "active_ticket_md": _read_txt(active_ticket_file) if project_tickets else "",
        "tickets_history": project_tickets,
        "latest_ticket": latest_ticket,
        "lint_report_txt": _read_txt(lint_file),
        "sim_report_txt": _read_txt(sim_file),
        "power_activity": atomic_read_json(power_file) or {},
        "ppa_comparison_matrix_md": _read_txt(ppa_file),
        "wave_slice_md": _read_txt(slice_file),
        "coi_graph": coi_graph_data,
        "wavedrom_json": atomic_read_json(wavedrom_file) or {},
        "svg_schematics": svg_map,
    }
