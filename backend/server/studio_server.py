# =============================================================================
# File Path: backend/server/studio_server.py
# =============================================================================
"""Silicon Studio IDE V3.0 — Localhost Web & WebSocket Server (`http://127.0.0.1:8080`).

Serves:
- Modular Frontend Web Application (`frontend/index.html`, `/css/*`, `/js/*`) at `http://127.0.0.1:8080`
- REST API endpoints (`/api/projects`, `/api/workspace/select-project`, `/api/bundle`)
- Real-Time WebSocket Event Stream (`ws://127.0.0.1:8080/ws` AND legacy port `ws://127.0.0.1:8765`
  so both V3 and V2 clients connect seamlessly)
- Watchdog file-system monitor across `.silicon_studio/workspace.json` and `projects/`
  (auto-detecting live source edits or MCP tool completions in <150ms without recursive loops).
"""
import asyncio
import json
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Set

STUDIO_ROOT = Path(__file__).resolve().parents[2]
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backend.core.state_manager import (
    assemble_project_bundle,
    validate_and_invalidate_cache,
)
from backend.core.workspace_manager import (
    CONFIG_FILE,
    PROJECTS_ROOT,
    STUDIO_ROOT,
    WORKSPACE_FILE,
    atomic_read_json,
    get_project_dir,
)
from backend.server.api_routes import register_ws_broadcast_hook, router as api_router

FRONTEND_DIR = STUDIO_ROOT / "frontend"
WS_CLIENTS: Set[WebSocket] = set()
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def broadcast_active_bundle() -> None:
    """Broadcasts the active project's state bundle to all connected WebSocket clients."""
    if not WS_CLIENTS:
        return
    try:
        bundle = assemble_project_bundle()
        payload = json.dumps(bundle)
    except Exception:
        return

    dead: Set[WebSocket] = set()
    for ws in list(WS_CLIENTS):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    WS_CLIENTS.difference_update(dead)


class StudioWorkspaceWatcher(FileSystemEventHandler):
    """Watches `.silicon_studio/` and `projects/` for changes and debounces WebSocket broadcasts."""

    def __init__(self) -> None:
        super().__init__()
        self.last_trigger = 0.0
        self.trailing_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()
        self.last_src_check = 0.0

    def _schedule_broadcast(self) -> None:
        if MAIN_LOOP and WS_CLIENTS:
            asyncio.run_coroutine_threadsafe(broadcast_active_bundle(), MAIN_LOOP)

    def on_any_event(self, event: Any) -> None:
        if event.is_directory:
            return
        src_str = str(event.src_path).replace("\\", "/")
        if src_str.endswith((".tmp", ".crswap", ".lock", ".out", ".exe", ".pyc")):
            return

        now = time.time()
        # If an RTL or testbench source file in `projects/<proj>/src/` or `verif/` was edited directly in VS Code,
        # run a single non-recursive SHA-256 cache check so stale pills update immediately!
        if ("/src/" in src_str or "/verif/" in src_str) and src_str.endswith((".sv", ".v", ".svh", ".vh", ".mem")):
            if now - self.last_src_check > 0.6:
                self.last_src_check = now
                try:
                    parts = src_str.split("/projects/")[-1].split("/")
                    if parts and parts[0]:
                        proj_dir = get_project_dir(parts[0], create_if_missing=False)
                        if proj_dir.exists():
                            validate_and_invalidate_cache(proj_dir)
                except Exception:
                    pass

        with self.lock:
            if self.trailing_timer is not None:
                self.trailing_timer.cancel()
                self.trailing_timer = None

            if now - self.last_trigger > 0.15:
                self.last_trigger = now
                self._schedule_broadcast()

            self.trailing_timer = threading.Timer(0.2, self._on_trailing_edge)
            self.trailing_timer.daemon = True
            self.trailing_timer.start()

    def _on_trailing_edge(self) -> None:
        with self.lock:
            self.trailing_timer = None
            self.last_trigger = time.time()
        self._schedule_broadcast()


def start_watchdog_observer() -> Observer:
    WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

    handler = StudioWorkspaceWatcher()
    observer = Observer()
    observer.schedule(handler, path=str(WORKSPACE_FILE.parent), recursive=False)
    observer.schedule(handler, path=str(PROJECTS_ROOT), recursive=True)
    observer.daemon = True
    observer.start()
    return observer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    register_ws_broadcast_hook(broadcast_active_bundle)
    observer = start_watchdog_observer()
    print("==========================================================================")
    print("  [Silicon Studio IDE V3.0] Localhost Server Active: http://127.0.0.1:8080")
    print("  [Silicon Studio IDE V3.0] WebSocket Stream Active: ws://127.0.0.1:8080/ws")
    print("==========================================================================")
    try:
        yield
    finally:
        observer.stop()


app = FastAPI(
    title="Silicon Studio IDE V3.0",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    WS_CLIENTS.add(websocket)
    try:
        init_bundle = assemble_project_bundle()
        await websocket.send_text(json.dumps(init_bundle))
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("type") == "SELECT_PROJECT" and data.get("project_name"):
                    from backend.core.workspace_manager import select_active_project
                    select_active_project(
                        str(data["project_name"]),
                        switched_by="user_ui_websocket",
                    )
                    await broadcast_active_bundle()
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        WS_CLIENTS.discard(websocket)


# Mount static `/css` and `/js` directories from `frontend/`
if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


@app.get("/", response_class=HTMLResponse)
async def serve_index() -> Any:
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse(
        "<html><body style='background:#09090b;color:#f4f4f5;font-family:monospace;padding:40px;'>"
        "<h2>Silicon Studio IDE V3.0 Server Running</h2>"
        "<p>Populate Batch 5 (`frontend/index.html`) to load the Web IDE UI.</p></body></html>"
    )


def main() -> None:
    cfg = atomic_read_json(CONFIG_FILE) or {}
    srv_cfg = cfg.get("server", {})
    host = srv_cfg.get("host", "127.0.0.1")
    port = int(srv_cfg.get("port", 8080))
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
