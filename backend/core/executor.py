# =============================================================================
# File Path: backend/core/executor.py
# =============================================================================
"""Cross-Platform Subprocess Execution Harness for Silicon Studio IDE V3.0.

Handles:
- Automatic resolution of `verilator_bin.exe`, `iverilog.exe`, `vvp.exe`, and `yosys.exe`
  inside `C:\\oss-cad-suite\\bin` (Windows) or standard system PATH (Linux/macOS).
- Automatic injection of `OSS_CAD_SUITE_PATH/bin`, `OSS_CAD_SUITE_PATH/lib`, and `VERILATOR_ROOT`.
- Configurable settings loaded from `.silicon_studio/studio_config.json`.
- POSIX trailing-newline normalization on SystemVerilog/Verilog source files so Verilator
  never fails on `EOFNEWLINE`.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

STUDIO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = STUDIO_ROOT / ".silicon_studio" / "studio_config.json"


def _resolve_oss_cad_root() -> Path:
    """Resolves the OSS CAD Suite root directory from env or `.silicon_studio/studio_config.json`."""
    env_override = os.environ.get("OSS_CAD_SUITE_PATH", "").strip()
    if env_override:
        return Path(env_override)
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg_root = cfg.get("toolchain", {}).get("oss_cad_suite_root", "")
            if cfg_root:
                return Path(cfg_root)
        except Exception:
            pass
    return Path(r"C:\oss-cad-suite")


OSS_ROOT = _resolve_oss_cad_root()
EDA_BIN_DIR = OSS_ROOT / "bin"
EDA_LIB_DIR = OSS_ROOT / "lib"

WINDOWS_TOOL_ALIASES: Dict[str, List[str]] = {
    "verilator": ["verilator_bin.exe", "verilator.exe", "verilator"],
    "iverilog": ["iverilog.exe", "iverilog"],
    "vvp": ["vvp.exe", "vvp"],
    "yosys": ["yosys.exe", "yosys"],
}

POSIX_TOOL_ALIASES: Dict[str, List[str]] = {
    "verilator": ["verilator_bin", "verilator"],
    "iverilog": ["iverilog"],
    "vvp": ["vvp"],
    "yosys": ["yosys"],
}


def get_tool_path(tool_name: str) -> str:
    """Resolves absolute path to an EDA executable inside OSS CAD Suite or system PATH."""
    base = tool_name.lower().removesuffix(".exe")
    is_win = sys.platform.startswith("win")
    alias_map = WINDOWS_TOOL_ALIASES if is_win else POSIX_TOOL_ALIASES
    candidates = alias_map.get(base, [f"{base}.exe", tool_name] if is_win else [base, tool_name])

    for cand in candidates:
        candidate_path = EDA_BIN_DIR / cand
        if candidate_path.exists():
            return str(candidate_path)

    for cand in candidates:
        sys_hit = shutil.which(cand)
        if sys_hit:
            return sys_hit

    return tool_name


def build_eda_env() -> Dict[str, str]:
    """Builds environment dictionary with OSS CAD Suite bin/lib and VERILATOR_ROOT."""
    env = os.environ.copy()
    extra_paths: List[str] = []
    if EDA_BIN_DIR.exists():
        extra_paths.append(str(EDA_BIN_DIR))
    if EDA_LIB_DIR.exists():
        extra_paths.append(str(EDA_LIB_DIR))

    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

    verilator_share = OSS_ROOT / "share" / "verilator"
    if verilator_share.exists():
        env.setdefault("VERILATOR_ROOT", str(verilator_share))

    env["PYTHONUTF8"] = "1"
    return env


def ensure_trailing_newlines(file_paths: List[Path]) -> None:
    """Ensures every RTL/TB source file ends with a newline so Verilator never fails on EOFNEWLINE."""
    for path in file_paths:
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                if content and not content.endswith("\n"):
                    path.write_text(content + "\n", encoding="utf-8")
            except OSError:
                pass


def run_cmd(
    cmd: List[str], cwd: Path, timeout_sec: int = 45
) -> Dict[str, Any]:
    """Executes an EDA CLI command with timeout protection and shell=False."""
    if not cmd:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": "Empty command.",
            "timeout": False,
        }

    resolved_cmd = list(cmd)
    if not Path(resolved_cmd[0]).is_absolute():
        resolved_cmd[0] = get_tool_path(resolved_cmd[0])

    exe_path = resolved_cmd[0]
    if not Path(exe_path).exists() and not shutil.which(exe_path):
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": (
                f"Executable '{cmd[0]}' (resolved as '{exe_path}') not found in "
                f"{EDA_BIN_DIR} or system PATH."
            ),
            "timeout": False,
        }

    cwd.mkdir(parents=True, exist_ok=True)

    try:
        res = subprocess.run(
            resolved_cmd,
            cwd=cwd,
            env=build_eda_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            shell=False,
        )
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_sec} seconds.",
            "timeout": True,
        }
    except Exception as exc:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Subprocess execution failed: {exc}",
            "timeout": False,
        }