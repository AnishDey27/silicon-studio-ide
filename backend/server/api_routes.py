# =============================================================================
# File Path: backend/server/api_routes.py
# =============================================================================
"""FastAPI REST Routes for Silicon Studio IDE (`backend/server/api_routes.py`).

Exposes:
- `GET  /api/projects`                  -> Lists all projects in `projects/` + active project
- `POST /api/workspace/select-project`  -> Switches `.silicon_studio/workspace.json` to the
                                           requested project (or creates a new project skeleton)
                                           and returns its full state bundle immediately.
- `GET  /api/bundle`                    -> Returns the live state bundle for the active project
- `GET  /api/bundle/{project_name}`     -> Returns the live state bundle for a specific project
"""
import sys
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from fastapi import APIRouter, Body
from backend.core.state_manager import (
    assemble_project_bundle,
    validate_and_invalidate_cache,
)
from backend.core.workspace_manager import (
    get_project_dir,
    list_all_projects,
    load_workspace_context,
    select_active_project,
)

router = APIRouter(prefix="/api", tags=["silicon-studio-api"])

# Injected by studio_server.py so REST project switches immediately broadcast over WebSockets
_WS_BROADCAST_HOOK: Optional[Callable[[], Coroutine[Any, Any, None]]] = None


def register_ws_broadcast_hook(
    hook: Callable[[], Coroutine[Any, Any, None]]
) -> None:
    global _WS_BROADCAST_HOOK
    _WS_BROADCAST_HOOK = hook


@router.get("/projects")
async def api_list_projects() -> Dict[str, Any]:
    """Returns all available projects in `projects/` and the current `workspace.json` context."""
    ws_ctx = load_workspace_context()
    return {
        "status": "SUCCESS",
        "active_project": ws_ctx.get("active_project"),
        "workspace_context": ws_ctx,
        "projects": list_all_projects(),
    }


@router.post("/workspace/select-project")
async def api_select_project(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Switches the active project in `.silicon_studio/workspace.json` (or creates a new one).

    Synchronizes both the Browser UI Dropdown and GitHub Copilot AI Agents!
    """
    project_name = str(payload.get("project_name", "")).strip()
    create_new = bool(payload.get("create_if_missing", False))
    if not project_name:
        return {"status": "ERROR", "message": "project_name is required."}

    proj_dir = get_project_dir(project_name, create_if_missing=create_new)
    if not proj_dir.exists():
        return {"status": "ERROR", "message": f"Project '{project_name}' does not exist."}

    validate_and_invalidate_cache(proj_dir)
    select_active_project(
        proj_dir.name,
        switched_by="user_ui_dropdown",
        create_if_missing=create_new,
        is_executing=False,
    )
    bundle = assemble_project_bundle(proj_dir.name)

    if _WS_BROADCAST_HOOK is not None:
        await _WS_BROADCAST_HOOK()

    return {
        "status": "SUCCESS",
        "active_project": proj_dir.name,
        "bundle": bundle,
    }


@router.get("/bundle")
async def api_get_active_bundle() -> Dict[str, Any]:
    """Returns the zero-copy state bundle for the currently active project."""
    return assemble_project_bundle()


@router.get("/bundle/{project_name}")
async def api_get_project_bundle(project_name: str) -> Dict[str, Any]:
    """Returns the zero-copy state bundle for `project_name`."""
    return assemble_project_bundle(project_name)
