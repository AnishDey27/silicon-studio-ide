# =============================================================================
# File Path: backend/core/workspace_manager.py
# =============================================================================
"""Bi-Directional Workspace & Project Manager (`backend/core/workspace_manager.py`).

Solves the Split-Brain Context Problem between the Localhost Web IDE Dropdown
and GitHub Copilot AI Agents:
1. Maintains `.silicon_studio/workspace.json` as the single source of truth for
   `active_project`.
2. Zero-Copy Architecture: Every project keeps its own isolated compartments inside
   `projects/<project_name>/build/{agent_bus,simulation,netlists,reports,views}`.
   No global `active_work/` file copying is needed!
3. When the user switches projects in the browser navbar dropdown, `select_active_project()`
   updates `.silicon_studio/workspace.json` so subsequent AI agent tool calls automatically
   target that project when `project_name` is omitted or defaulted.
4. When an AI agent creates or targets a project in Copilot Chat, `select_active_project()`
   updates `.silicon_studio/workspace.json`, which triggers the FastAPI WebSocket broadcaster
   to switch the browser UI to that project in real time.
"""
import datetime
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

STUDIO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_ROOT = STUDIO_ROOT / "projects"
WORKSPACE_FILE = STUDIO_ROOT / ".silicon_studio" / "workspace.json"
CONFIG_FILE = STUDIO_ROOT / ".silicon_studio" / "studio_config.json"

BUILD_COMPARTMENTS = ("agent_bus", "simulation", "netlists", "reports", "views")


def atomic_read_json(path: Path, retries: int = 8, delay: float = 0.02) -> Optional[Dict[str, Any]]:
    """Reads a JSON dictionary with retry backoff to survive transient Windows file locks."""
    for attempt in range(retries):
        if not path.exists():
            if attempt < 2:
                time.sleep(delay)
                continue
            return None
        try:
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except (PermissionError, OSError, json.JSONDecodeError):
            pass
        time.sleep(delay * (1.0 + 0.5 * attempt))
    return None


def atomic_write_json(path: Path, payload: Any, retries: int = 6, delay: float = 0.02) -> None:
    """Writes JSON atomically via a temporary sibling file and `os.replace()`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2) + "\n"
    tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    for attempt in range(retries):
        try:
            tmp_path.write_text(serialized, encoding="utf-8")
            os.replace(tmp_path, path)
            return
        except (PermissionError, OSError):
            time.sleep(delay * (1.0 + 0.5 * attempt))
    try:
        path.write_text(serialized, encoding="utf-8")
    except OSError:
        pass
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def ensure_project_structure(project_dir: Path) -> Dict[str, Path]:
    """Ensures `src/`, `verif/`, and all 5 `build/` compartments exist for a project.

    Also migrates legacy V2 `work/` artifacts into `build/` automatically if `build/` is empty.
    """
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "verif").mkdir(parents=True, exist_ok=True)

    build_dir = project_dir / "build"
    legacy_work_dir = project_dir / "work"

    compartments: Dict[str, Path] = {"build": build_dir}
    for comp in BUILD_COMPARTMENTS:
        c_path = build_dir / comp
        c_path.mkdir(parents=True, exist_ok=True)
        compartments[comp] = c_path

    # Seamless V2 -> V3 artifact migration if `work/` exists and `build/` has not been populated yet
    if legacy_work_dir.exists() and not (build_dir / "agent_bus" / "session_state.json").exists():
        import shutil
        for comp in BUILD_COMPARTMENTS:
            src_comp = legacy_work_dir / comp
            dst_comp = build_dir / comp
            if src_comp.exists():
                for item in src_comp.rglob("*"):
                    if item.is_file() and item.suffix.lower() not in {".out", ".exe", ".tmp", ".lock"}:
                        rel = item.relative_to(src_comp)
                        target = dst_comp / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            try:
                                shutil.copy2(item, target)
                            except OSError:
                                pass

    return compartments


def get_project_dir(project_name: str, create_if_missing: bool = False) -> Path:
    """Resolves a project name or path to `projects/<project_name>`."""
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    clean_name = project_name.strip().replace("\\", "/").split("/")[-1]
    if not clean_name:
        clean_name = get_active_project_name()

    candidate = PROJECTS_ROOT / clean_name
    if candidate.exists():
        ensure_project_structure(candidate)
        return candidate

    # Fuzzy case-insensitive or substring match against existing projects
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if d.is_dir() and (d.name.lower() == clean_name.lower() or clean_name.lower() in d.name.lower()):
            ensure_project_structure(d)
            return d

    if create_if_missing and clean_name:
        ensure_project_structure(candidate)
    return candidate


def list_all_projects() -> List[Dict[str, Any]]:
    """Returns metadata for all hardware projects inside `projects/`."""
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    active_proj = get_active_project_name()
    results: List[Dict[str, Any]] = []

    for d in sorted(PROJECTS_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        ensure_project_structure(d)
        src_dir = d / "src"
        verif_dir = d / "verif"
        rtl_files = sorted(
            [f.name for f in src_dir.rglob("*") if f.is_file() and f.suffix.lower() in (".sv", ".v", ".svh", ".vh")]
        )
        tb_files = sorted(
            [f.name for f in verif_dir.rglob("*") if f.is_file() and f.suffix.lower() in (".sv", ".v")]
        )
        results.append(
            {
                "project_name": d.name,
                "is_active": d.name == active_proj,
                "rtl_files_count": len(rtl_files),
                "tb_files_count": len(tb_files),
                "rtl_files": rtl_files,
                "tb_files": tb_files,
                "project_root": f"projects/{d.name}",
            }
        )
    return results


def load_workspace_context() -> Dict[str, Any]:
    """Reads `.silicon_studio/workspace.json` or initializes it to the first available project."""
    ctx = atomic_read_json(WORKSPACE_FILE)
    if ctx and ctx.get("active_project"):
        proj_name = str(ctx["active_project"]).strip()
        if (PROJECTS_ROOT / proj_name).exists():
            return ctx

    # Fallback: pick first project in `projects/`
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    existing = sorted([d.name for d in PROJECTS_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")])
    default_proj = existing[0] if existing else "polar_scl_decoder"
    default_ctx = {
        "active_project": default_proj,
        "project_root": f"projects/{default_proj}",
        "active_agent": "@eda-lead",
        "is_executing": False,
        "last_action": "workspace_initialized",
        "rtl_sha256": None,
        "tb_sha256": None,
        "last_switched_by": "auto_discovery",
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    atomic_write_json(WORKSPACE_FILE, default_ctx)
    return default_ctx


def get_active_project_name(project_hint: str = "") -> str:
    """Resolves the target project name from an explicit hint or `.silicon_studio/workspace.json`."""
    if project_hint and project_hint.strip():
        clean = project_hint.strip().replace("\\", "/").split("/")[-1]
        return clean
    ctx = load_workspace_context()
    return str(ctx.get("active_project", "polar_scl_decoder")).strip()


def select_active_project(
    project_name: str,
    switched_by: str = "user_ui_dropdown",
    create_if_missing: bool = False,
    active_agent: Optional[str] = None,
    is_executing: Optional[bool] = None,
    last_action: Optional[str] = None,
    rtl_sha256: Optional[str] = None,
    tb_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Updates `.silicon_studio/workspace.json` to point to `project_name`.

    Called both by:
    - `POST /api/workspace/select-project` when the user switches projects in the browser dropdown.
    - `state_manager.py` when an AI agent starts or completes a tool on a project.
    """
    proj_dir = get_project_dir(project_name, create_if_missing=create_if_missing)
    ctx = load_workspace_context()
    prev_proj = ctx.get("active_project")

    ctx["active_project"] = proj_dir.name
    ctx["project_root"] = f"projects/{proj_dir.name}"
    ctx["project_switched"] = prev_proj != proj_dir.name
    ctx["last_switched_by"] = switched_by
    if active_agent is not None:
        ctx["active_agent"] = active_agent
    if is_executing is not None:
        ctx["is_executing"] = is_executing
    if last_action is not None:
        ctx["last_action"] = last_action
    if rtl_sha256 is not None:
        ctx["rtl_sha256"] = rtl_sha256
    if tb_sha256 is not None:
        ctx["tb_sha256"] = tb_sha256
    ctx["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    atomic_write_json(WORKSPACE_FILE, ctx)
    return ctx