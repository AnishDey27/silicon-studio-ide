# =============================================================================
# File Path: backend/core/blackboard_bus.py
# =============================================================================
"""Zero-Copy Inter-Agent Blackboard & Handoff Ticket Manager (`backend/core/blackboard_bus.py`).

Stores tickets directly inside `projects/<project_name>/build/agent_bus/`:
- `agent_bus.json`   (Structured JSON log of all tickets for the project)
- `active_ticket.md` (Single overwrite Markdown view of the latest active ticket)

Key V3.3 Fix:
- Stamps every ticket with both `timestamp` (`YYYY-MM-DD HH:MM:SS`) and `display_time`
  (`HH:MM:SS`) so the UI Ticket Drawer and tabs clearly show when each ticket was created.
- Synchronizes ticket validity with current pipeline stage completion (`sim_passed` and
  `synth_passed`), purging old `TAPEOUT_READY` tickets whenever synthesis has been
  invalidated by a new run.
"""
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.state_manager import compute_project_hashes, load_project_state
from backend.core.workspace_manager import (
    atomic_read_json,
    atomic_write_json,
    ensure_project_structure,
    get_project_dir,
)


def _format_active_ticket_md(ticket: Dict[str, Any]) -> str:
    """Renders the latest inter-agent handoff ticket as a crisp Markdown document."""
    kb_rule = ticket.get("kb_rule_id") or "None cited"
    lines = [
        f"# Inter-Agent Handoff Ticket: `{ticket.get('ticket_id', 'TICKET-001')}`",
        "",
        f"- **Project:** `{ticket.get('project_name')}`",
        f"- **Status:** **`{ticket.get('status', 'OPEN')}`**",
        f"- **Created At:** `{ticket.get('timestamp', '')}`",
        f"- **From Agent:** `{ticket.get('from_agent')}` $\\rightarrow$ **Assigned To:** `{ticket.get('to_agent')}`",
        f"- **Validated KB Rule Cited:** **`{kb_rule}`**",
        f"- **RTL SHA-256 Digest:** `{ticket.get('rtl_sha256')}`",
        "",
        "---",
        "",
        "## 1. Failure / Task Summary",
        f"{ticket.get('summary', 'N/A')}",
        "",
        "## 2. Neuro-Symbolic Verification & Knowledge Evidence",
        f"- **Anchor Timestamp ($t_0$):** `{ticket.get('anchor_time_ns', 'N/A')}`",
        f"- **Causal COI Signals:** `{ticket.get('coi_signals', 'N/A')}`",
        f"- **Suspect RTL File / Line:** `{ticket.get('suspect_rtl_location', 'N/A')}`",
        f"- **Silicon Knowledge Rule ID:** `{kb_rule}`",
        "",
        "## 3. Root-Cause Analysis / Action Required",
        f"{ticket.get('evidence_and_action', 'N/A')}",
        "",
    ]
    return "\n".join(lines)


def _filter_live_tickets(
    raw_tickets: List[Dict[str, Any]],
    proj_name: str,
    current_rtl_sha: str,
    sim_passed_on_current_sha: bool = False,
    synth_passed_on_current_sha: bool = False,
    incoming_status: str = "",
) -> List[Dict[str, Any]]:
    """Filters out stale tickets from previous runs or invalidated pipeline stages."""
    closing_statuses = {"TAPEOUT_READY", "VERIFIED_PASS"}
    bug_statuses = {"OPEN_BUG", "FAIL", "RTL_FIXED_PENDING_SIM"}

    has_closing_on_current_sha = incoming_status in closing_statuses or any(
        isinstance(t, dict)
        and t.get("rtl_sha256") == current_rtl_sha
        and (
            (str(t.get("status", "")).upper() == "TAPEOUT_READY" and synth_passed_on_current_sha)
            or (str(t.get("status", "")).upper() == "VERIFIED_PASS" and sim_passed_on_current_sha)
        )
        for t in raw_tickets
    )

    kept: List[Dict[str, Any]] = []
    for t in raw_tickets:
        if not isinstance(t, dict):
            continue
        if t.get("project_name") not in (None, "", proj_name):
            continue
        t_sha = t.get("rtl_sha256", "")
        t_status = str(t.get("status", "")).upper()

        # 1. If synthesis is not currently completed (and we aren't posting TAPEOUT_READY right now),
        #    any old TAPEOUT_READY ticket from a prior run is stale!
        if (
            t_status == "TAPEOUT_READY"
            and not synth_passed_on_current_sha
            and incoming_status != "TAPEOUT_READY"
        ):
            continue

        # 2. If simulation is not currently completed (and we aren't posting VERIFIED_PASS right now),
        #    any old VERIFIED_PASS ticket is stale!
        if (
            t_status == "VERIFIED_PASS"
            and not sim_passed_on_current_sha
            and incoming_status != "VERIFIED_PASS"
        ):
            continue

        # 3. Tickets from an older RTL SHA-256:
        if t_sha and current_rtl_sha and t_sha != current_rtl_sha:
            if t_status in closing_statuses:
                continue
            if sim_passed_on_current_sha or synth_passed_on_current_sha or has_closing_on_current_sha:
                continue

        # 4. If the design is now VERIFIED_PASS or TAPEOUT_READY, purge superseded OPEN_BUG tickets
        if has_closing_on_current_sha and t_status in bug_statuses:
            continue

        kept.append(t)

    for idx, item in enumerate(kept, start=1):
        item["ticket_id"] = f"TICKET-{idx:03d}"

    return kept


def post_handoff_ticket(
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
    """Posts or updates an inter-agent handoff ticket in `projects/<name>/build/agent_bus/`."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    bus_file = comp["agent_bus"] / "agent_bus.json"
    active_md_file = comp["agent_bus"] / "active_ticket.md"

    bus_data = atomic_read_json(bus_file) or {"project_name": proj_dir.name, "tickets": []}
    raw_tickets: List[Dict[str, Any]] = list(bus_data.get("tickets", []))
    hashes = compute_project_hashes(proj_dir)
    sess_state = load_project_state(proj_dir)
    sim_passed = (
        "simulation" in sess_state.get("completed_stages", [])
        and "simulation" not in sess_state.get("stale_stages", [])
        and "simulation" not in sess_state.get("failed_stages", [])
    )
    synth_passed = (
        "synthesis" in sess_state.get("completed_stages", [])
        and "synthesis" not in sess_state.get("stale_stages", [])
        and "synthesis" not in sess_state.get("failed_stages", [])
    )
    norm_status = status.strip().upper()

    tickets = _filter_live_tickets(
        raw_tickets,
        proj_name=proj_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed_on_current_sha=sim_passed,
        synth_passed_on_current_sha=synth_passed,
        incoming_status=norm_status,
    )

    resolved_id = (
        ticket_id.strip()
        if ticket_id and ticket_id.strip()
        else f"TICKET-{len(tickets) + 1:03d}"
    )

    now_dt = datetime.datetime.now()
    now_full_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    now_short_time = now_dt.strftime("%H:%M:%S")

    ticket_entry = {
        "ticket_id": resolved_id,
        "project_name": proj_dir.name,
        "status": norm_status,
        "from_agent": from_agent.strip(),
        "to_agent": to_agent.strip(),
        "kb_rule_id": kb_rule_id.strip(),
        "rtl_sha256": hashes["rtl_sha256"],
        "tb_sha256": hashes["tb_sha256"],
        "timestamp": now_full_str,
        "display_time": now_short_time,
        "summary": summary.strip(),
        "anchor_time_ns": anchor_time_ns.strip(),
        "coi_signals": coi_signals.strip(),
        "suspect_rtl_location": suspect_rtl_location.strip(),
        "evidence_and_action": evidence_and_action.strip(),
    }

    updated_existing = False
    for idx, existing in enumerate(tickets):
        if existing.get("ticket_id") == resolved_id or (
            norm_status == "TAPEOUT_READY" and existing.get("status") == "TAPEOUT_READY"
        ):
            tickets[idx] = ticket_entry
            updated_existing = True
            break
    if not updated_existing:
        tickets.append(ticket_entry)

    for idx, item in enumerate(tickets, start=1):
        item["ticket_id"] = f"TICKET-{idx:03d}"
    ticket_entry = tickets[-1]

    bus_data["project_name"] = proj_dir.name
    bus_data["tickets"] = tickets
    bus_data["latest_ticket"] = ticket_entry

    atomic_write_json(bus_file, bus_data)
    md_text = _format_active_ticket_md(ticket_entry)
    active_md_file.write_text(md_text, encoding="utf-8")

    return {
        "status": "SUCCESS",
        "ticket": ticket_entry,
        "active_ticket_path": f"projects/{proj_dir.name}/build/agent_bus/active_ticket.md",
        "agent_guidance": (
            f"Handoff ticket {ticket_entry['ticket_id']} ({norm_status} at {now_short_time}) posted from {from_agent} to {to_agent}."
        ),
    }


def read_handoff_tickets(project_name: str) -> Dict[str, Any]:
    """Reads the active handoff ticket and ticket history for `project_name`, auto-pruning resolved/stale tickets."""
    proj_dir = get_project_dir(project_name, create_if_missing=False)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project not found: {project_name}"}

    comp = ensure_project_structure(proj_dir)
    bus_file = comp["agent_bus"] / "agent_bus.json"
    active_md_file = comp["agent_bus"] / "active_ticket.md"
    hashes = compute_project_hashes(proj_dir)
    sess_state = load_project_state(proj_dir)
    sim_passed = (
        "simulation" in sess_state.get("completed_stages", [])
        and "simulation" not in sess_state.get("stale_stages", [])
        and "simulation" not in sess_state.get("failed_stages", [])
    )
    synth_passed = (
        "synthesis" in sess_state.get("completed_stages", [])
        and "synthesis" not in sess_state.get("stale_stages", [])
        and "synthesis" not in sess_state.get("failed_stages", [])
    )

    bus_data = atomic_read_json(bus_file)
    if not bus_data or not bus_data.get("tickets"):
        return {
            "status": "EMPTY",
            "project_name": proj_dir.name,
            "current_rtl_sha256": hashes["rtl_sha256"],
            "tickets": [],
            "message": "No inter-agent handoff tickets have been posted for this project yet.",
        }

    raw_tickets = list(bus_data.get("tickets", []))
    valid_tickets = _filter_live_tickets(
        raw_tickets,
        proj_name=proj_dir.name,
        current_rtl_sha=hashes["rtl_sha256"],
        sim_passed_on_current_sha=sim_passed,
        synth_passed_on_current_sha=synth_passed,
    )

    if len(valid_tickets) != len(raw_tickets):
        bus_data["tickets"] = valid_tickets
        bus_data["latest_ticket"] = valid_tickets[-1] if valid_tickets else {}
        atomic_write_json(bus_file, bus_data)

    latest = valid_tickets[-1] if valid_tickets else {}
    active_md = (
        active_md_file.read_text(encoding="utf-8", errors="replace")
        if active_md_file.exists() and valid_tickets
        else ""
    )
    rtl_changed_since_ticket = (
        bool(latest) and latest.get("rtl_sha256") != hashes["rtl_sha256"]
    )

    return {
        "status": "SUCCESS" if valid_tickets else "EMPTY",
        "project_name": proj_dir.name,
        "current_rtl_sha256": hashes["rtl_sha256"],
        "rtl_modified_since_latest_ticket": rtl_changed_since_ticket,
        "latest_ticket": latest,
        "active_ticket_md": active_md,
        "all_tickets": valid_tickets,
    }
