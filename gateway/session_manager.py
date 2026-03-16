"""
tmux + ttyd session manager for MPM Gateway.

Manages per-project tmux sessions with ttyd for web terminal access.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent.parent / "data" / "cli_patterns.json"

# ttyd ports: base port + project index
TTYD_BASE_PORT = 7680
# Track ttyd processes: project -> Popen
_ttyd_procs: dict[str, subprocess.Popen] = {}


class SessionState(Enum):
    OFF = "off"           # No tmux session
    IDLE = "idle"         # tmux session exists but no AI CLI running
    RUNNING = "running"   # AI CLI process detected


@dataclass
class SessionInfo:
    project: str
    tmux_name: str
    state: SessionState
    cli_name: Optional[str] = None
    pid: Optional[int] = None
    ttyd_port: Optional[int] = None


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"patterns": [], "workspace": "", "tmux_prefix": "mpm"}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return -1, ""


def _tmux_session_name(prefix: str, project: str) -> str:
    return f"{prefix}-{project}"


def _get_ttyd_port(project: str) -> int:
    """Deterministic port for a project based on hash."""
    return TTYD_BASE_PORT + (hash(project) % 100)


# ---------------------------------------------------------------------------
# ttyd management
# ---------------------------------------------------------------------------

def _start_ttyd(project: str, tmux_name: str) -> int:
    """Start ttyd for a tmux session. Returns the port."""
    if project in _ttyd_procs:
        proc = _ttyd_procs[project]
        if proc.poll() is None:  # still running
            return _get_ttyd_port(project)
        # Dead, clean up
        del _ttyd_procs[project]

    port = _get_ttyd_port(project)
    try:
        proc = subprocess.Popen(
            [
                "/usr/bin/ttyd", "--port", str(port),
                "--writable",
                "--base-path", f"/ttyd/{project}",
                "-t", "enableSizeOverlay=false",
                "tmux", "attach-session", "-t", tmux_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _ttyd_procs[project] = proc
        return port
    except FileNotFoundError:
        raise RuntimeError("ttyd not found — install with: snap install ttyd --classic")


def _stop_ttyd(project: str) -> None:
    """Stop ttyd for a project."""
    proc = _ttyd_procs.pop(project, None)
    if proc and proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# tmux operations
# ---------------------------------------------------------------------------

def list_tmux_sessions() -> list[str]:
    rc, out = _run(["tmux", "list-sessions", "-F", "#{session_name}"])
    if rc != 0 or not out:
        return []
    return out.splitlines()


def create_session(project: str, cli_command: Optional[str] = None) -> SessionInfo:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    workspace = config.get("workspace", "")
    name = _tmux_session_name(prefix, project)
    project_dir = os.path.join(workspace, project)

    if not os.path.isdir(project_dir):
        raise ValueError(f"Project directory not found: {project_dir}")

    # Check if session already exists
    if name in list_tmux_sessions():
        # Ensure mouse mode and ttyd are running
        _run(["tmux", "set-option", "-t", name, "mouse", "on"])
        _start_ttyd(project, name)
        return get_session_info(project)

    # Create session
    cmd = ["tmux", "new-session", "-d", "-s", name, "-c", project_dir]
    rc, _ = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"Failed to create tmux session: {name}")

    # Increase scrollback buffer
    _run(["tmux", "set-option", "-t", name, "history-limit", "10000"])

    # Enable mouse mode — allows wheel scrolling through scrollback
    _run(["tmux", "set-option", "-t", name, "mouse", "on"])

    # Start CLI if specified
    if cli_command:
        send_keys(project, cli_command)

    # Start ttyd
    _start_ttyd(project, name)

    return get_session_info(project)


def kill_session(project: str) -> bool:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    name = _tmux_session_name(prefix, project)
    _stop_ttyd(project)
    rc, _ = _run(["tmux", "kill-session", "-t", name])
    return rc == 0


def send_keys(project: str, text: str) -> bool:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    name = _tmux_session_name(prefix, project)
    rc, _ = _run(["tmux", "send-keys", "-t", name, text, "Enter"])
    return rc == 0


def capture_pane(project: str, lines: int = 200) -> str:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    name = _tmux_session_name(prefix, project)
    rc, out = _run(["tmux", "capture-pane", "-t", name, "-p", "-S", f"-{lines}"])
    if rc != 0:
        return ""
    return out


# ---------------------------------------------------------------------------
# Process detection
# ---------------------------------------------------------------------------

def _detect_cli_in_session(tmux_name: str, patterns: list[str]) -> Optional[tuple[str, int]]:
    rc, pane_pid_str = _run([
        "tmux", "list-panes", "-t", tmux_name, "-F", "#{pane_pid}"
    ])
    if rc != 0 or not pane_pid_str:
        return None

    pane_pid = pane_pid_str.splitlines()[0].strip()

    rc, children = _run(["ps", "--ppid", pane_pid, "-o", "pid=,comm=", "--no-headers"])
    if rc != 0 or not children:
        return None

    for line in children.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, comm = parts
        comm_lower = comm.lower()
        for pattern in patterns:
            if pattern.lower() in comm_lower:
                return (pattern, int(pid_str))

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session_info(project: str) -> SessionInfo:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    patterns = config.get("patterns", [])
    name = _tmux_session_name(prefix, project)

    if name not in list_tmux_sessions():
        return SessionInfo(project=project, tmux_name=name, state=SessionState.OFF)

    ttyd_port = None
    if project in _ttyd_procs and _ttyd_procs[project].poll() is None:
        ttyd_port = _get_ttyd_port(project)

    cli = _detect_cli_in_session(name, patterns)
    if cli:
        return SessionInfo(
            project=project, tmux_name=name,
            state=SessionState.RUNNING, cli_name=cli[0], pid=cli[1],
            ttyd_port=ttyd_port,
        )

    return SessionInfo(
        project=project, tmux_name=name, state=SessionState.IDLE,
        ttyd_port=ttyd_port,
    )


def get_all_sessions() -> list[dict]:
    config = _load_config()
    workspace = config.get("workspace", "")
    prefix = config.get("tmux_prefix", "mpm")

    if not workspace or not os.path.isdir(workspace):
        return []

    active_tmux = set(list_tmux_sessions())
    results: list[SessionInfo] = []

    for d in sorted(Path(workspace).iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        name = _tmux_session_name(prefix, d.name)
        if name in active_tmux:
            results.append(get_session_info(d.name))
        else:
            results.append(SessionInfo(
                project=d.name, tmux_name=name, state=SessionState.OFF,
            ))

    return [
        {
            "project": s.project,
            "tmux_name": s.tmux_name,
            "state": s.state.value,
            "cli_name": s.cli_name,
            "pid": s.pid,
            "ttyd_port": s.ttyd_port,
        }
        for s in results
    ]
