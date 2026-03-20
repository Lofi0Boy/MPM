"""
tmux + ttyd session manager for MPM Gateway.

Manages per-project tmux sessions with ttyd for web terminal access.
"""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from shutil import which
from typing import Optional

IS_MACOS = platform.system() == "Darwin"

CONFIG_PATH = Path.home() / ".mpm" / "config.json"

# ttyd ports: base port + project index
TTYD_BASE_PORT = 7680
# Track ttyd processes: project -> Popen | int (PID for reconnected processes)
_ttyd_procs: dict[str, subprocess.Popen | int] = {}


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
        return {"patterns": [], "projects": [], "tmux_prefix": "mpm"}
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
    """Deterministic port for a project (stable across restarts)."""
    import hashlib
    h = int(hashlib.md5(project.encode()).hexdigest(), 16)
    return TTYD_BASE_PORT + (h % 100)


# ---------------------------------------------------------------------------
# ttyd management
# ---------------------------------------------------------------------------

def _is_ttyd_alive(project: str) -> bool:
    """Check if tracked ttyd process is still running."""
    entry = _ttyd_procs.get(project)
    if entry is None:
        return False
    if isinstance(entry, int):
        # Reconnected PID — check via kill(0)
        try:
            os.kill(entry, 0)
            return True
        except OSError:
            del _ttyd_procs[project]
            return False
    else:
        # Popen object
        if entry.poll() is None:
            return True
        del _ttyd_procs[project]
        return False


def _kill_orphan_ttyd(tmux_name: str, port: int) -> None:
    """Kill any orphan ttyd processes for this tmux session or port."""
    import time as _time

    # 1) Kill ttyd processes attached to the same tmux session (any port)
    #    Skip PIDs we currently manage (they're being replaced intentionally)
    our_pids = set()
    for entry in _ttyd_procs.values():
        our_pids.add(entry if isinstance(entry, int) else entry.pid)
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"ttyd.*{tmux_name}"],
            capture_output=True, text=True, timeout=3,
        )
        for pid_str in result.stdout.strip().splitlines():
            pid = int(pid_str.strip())
            if pid in our_pids:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    except Exception:
        pass

    # 2) Kill anything still on the target port
    try:
        if IS_MACOS:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=3
            )
            for pid_str in result.stdout.strip().splitlines():
                try:
                    os.kill(int(pid_str.strip()), signal.SIGTERM)
                except (OSError, ValueError):
                    pass
        else:
            result = subprocess.run(
                ["fuser", f"{port}/tcp"], capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                subprocess.run(["fuser", "-k", f"{port}/tcp"],
                               capture_output=True, timeout=3)
    except Exception:
        pass

    _time.sleep(0.3)


def _start_ttyd(project: str, tmux_name: str) -> int:
    """Start ttyd for a tmux session. Returns the port."""
    if _is_ttyd_alive(project):
        return _get_ttyd_port(project)

    port = _get_ttyd_port(project)
    _kill_orphan_ttyd(tmux_name, port)

    try:
        proc = subprocess.Popen(
            [
                which("ttyd") or "ttyd", "--port", str(port),
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
        hint = "brew install ttyd" if IS_MACOS else "snap install ttyd --classic"
        raise RuntimeError(f"ttyd not found — install with: {hint}")


def _stop_ttyd(project: str) -> None:
    """Stop ttyd for a project."""
    entry = _ttyd_procs.pop(project, None)
    if entry is None:
        return
    pid = entry if isinstance(entry, int) else entry.pid
    try:
        os.kill(pid, signal.SIGTERM)
        if isinstance(entry, subprocess.Popen):
            entry.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.kill(pid, signal.SIGKILL)
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


def _base_project(project: str) -> str:
    """Strip role suffix (e.g., 'MyApp--pm' → 'MyApp')."""
    return project.split("--")[0] if "--" in project else project


def _find_project_dir(config: dict, project: str) -> Optional[str]:
    """Find the full path for a project name from the config projects list."""
    base = _base_project(project)
    for p in config.get("projects", []):
        if Path(p).name == base:
            return p
    return None


def create_session(project: str, cli_command: Optional[str] = None) -> SessionInfo:
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")
    name = _tmux_session_name(prefix, project)
    project_dir = _find_project_dir(config, project)

    if not project_dir or not os.path.isdir(project_dir):
        raise ValueError(f"Project directory not found: {project}")

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

    if IS_MACOS:
        # macOS ps doesn't support --ppid; use pgrep -P to find children
        rc_pg, child_pids = _run(["pgrep", "-P", pane_pid])
        if rc_pg != 0 or not child_pids:
            return None
        pids_csv = ",".join(child_pids.splitlines())
        rc, children = _run(["ps", "-o", "pid=,comm=", "-p", pids_csv])
    else:
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
    if _is_ttyd_alive(project):
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


def cleanup_all() -> None:
    """Kill all MPM-managed ttyd processes and tmux sessions."""
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")

    # Stop all ttyd processes
    for project in list(_ttyd_procs.keys()):
        _stop_ttyd(project)

    # Kill all mpm-prefixed tmux sessions
    for name in list_tmux_sessions():
        if name.startswith(f"{prefix}-"):
            _run(["tmux", "kill-session", "-t", name])

    print("MPM cleanup: all sessions terminated")


def reconnect_ttyd() -> None:
    """Reconnect to surviving tmux sessions after a server restart.

    For each mpm-prefixed tmux session, kill any orphan ttyd on the
    expected port and start a fresh ttyd.  tmux sessions are the
    important state — ttyd is just a disposable web bridge.
    """
    config = _load_config()
    prefix = config.get("tmux_prefix", "mpm")

    for name in list_tmux_sessions():
        if not name.startswith(f"{prefix}-"):
            continue
        project = name[len(prefix) + 1:]
        if project in _ttyd_procs:
            continue
        try:
            port = _start_ttyd(project, name)
            print(f"MPM reconnect: ttyd for {project} on port {port}")
        except RuntimeError as e:
            print(f"MPM reconnect: failed for {project} — {e}")


def get_all_sessions() -> list[dict]:
    config = _load_config()
    projects = config.get("projects", [])
    prefix = config.get("tmux_prefix", "mpm")

    active_tmux = set(list_tmux_sessions())
    results: list[SessionInfo] = []

    for project_path in projects:
        d = Path(project_path)
        if not d.is_dir():
            continue
        project_name = d.name
        # Check both dev (default) and pm sessions
        for suffix in ("", "--pm"):
            key = f"{project_name}{suffix}"
            name = _tmux_session_name(prefix, key)
            if name in active_tmux:
                results.append(get_session_info(key))
            elif not suffix:
                # Only show "off" for the default (dev) session
                results.append(SessionInfo(
                    project=project_name, tmux_name=name, state=SessionState.OFF,
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
