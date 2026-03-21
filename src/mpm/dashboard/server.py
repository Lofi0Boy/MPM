"""
MPM Dashboard — web server.

Run from the MPM root:
    python dashboard/server.py
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests as http_requests

import markdown as md_lib
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from mpm.gateway.file_watcher import start_file_watcher
from mpm.gateway.session_manager import (
    capture_pane,
    cleanup_all,
    create_session,
    get_all_sessions,
    kill_session,
    reconnect_ttyd,
    send_keys,
)
from mpm.dashboard.projects import (
    get_all_projects, _load_config as load_projects_config,
    load_future, save_future,
    load_current_tasks, save_current_task, delete_current_task,
    load_past, append_past,
    load_project_md,
)

MPM_HOME = Path.home() / ".mpm"
IDEAS_PATH = MPM_HOME / "ideas.json"


def _get_tz():
    """Get timezone from config, default to UTC."""
    try:
        config = load_projects_config()
        return ZoneInfo(config.get("timezone", "UTC"))
    except Exception:
        return timezone.utc

app = Flask(__name__, template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
socketio = SocketIO(app, cors_allowed_origins="*")


@app.after_request
def no_cache(response):
    """Disable browser caching so server code updates reflect immediately."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

_cache: dict = {"data": None, "at": 0.0}
CACHE_TTL = 30


def get_projects_cached() -> list[dict]:
    now = time.time()
    if _cache["data"] is None or now - _cache["at"] > CACHE_TTL:
        _cache["data"] = get_all_projects()
        _cache["at"] = now
    return _cache["data"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/terminal/<project>")
def terminal_page(project):
    return render_template("terminal.html", project=project)


@app.route("/api/projects")
def api_projects():
    projects = get_projects_cached()
    return jsonify({"projects": projects, "updated_at": _cache["at"]})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    _cache["data"] = None
    projects = get_projects_cached()
    socketio.emit("project_changed", {"source": "refresh"})
    return jsonify({"projects": projects, "updated_at": _cache["at"]})


@app.route("/api/docs/<project_name>")
def api_docs_list(project_name):
    """List all .md files in a project directory (including .mpm/docs/)."""
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404

    files = []
    for md_path in sorted(d.rglob("*.md")):
        rel = md_path.relative_to(d)
        # Skip node_modules, .git, etc.
        parts = rel.parts
        if any(p.startswith(".") and p != ".mpm" for p in parts):
            continue
        if "node_modules" in parts or "__pycache__" in parts:
            continue
        files.append(str(rel))
    return jsonify({"files": files})


@app.route("/api/docs/<project_name>/<path:file_path>")
def api_doc_read(project_name, file_path):
    """Read a markdown file. Returns raw content and rendered HTML."""
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404

    if ".." in file_path:
        return jsonify({"error": "Invalid path"}), 400

    doc_path = d / file_path
    if not doc_path.exists():
        return jsonify({"error": "File not found"}), 404

    raw = doc_path.read_text(encoding="utf-8")
    html = md_lib.markdown(raw, extensions=["tables", "fenced_code"])
    return jsonify({"raw": raw, "html": html})


@app.route("/api/docs/<project_name>/<path:file_path>", methods=["PUT"])
def api_doc_write(project_name, file_path):
    """Save a markdown file."""
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404

    if ".." in file_path:
        return jsonify({"error": "Invalid path"}), 400

    doc_path = d / file_path
    if not doc_path.exists():
        return jsonify({"error": "File not found"}), 404

    data = request.get_json(force=True)
    content = data.get("content", "")
    doc_path.write_text(content, encoding="utf-8")
    html = md_lib.markdown(content, extensions=["tables", "fenced_code"])
    _cache["data"] = None  # Invalidate project cache
    return jsonify({"ok": True, "html": html})


# ---------------------------------------------------------------------------
# Ideas CRUD
# ---------------------------------------------------------------------------

def _load_ideas() -> list[dict]:
    if not IDEAS_PATH.exists():
        return []
    return json.loads(IDEAS_PATH.read_text(encoding="utf-8"))


def _save_ideas(ideas: list[dict]) -> None:
    IDEAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_PATH.write_text(json.dumps(ideas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@app.route("/api/ideas")
def api_ideas():
    return jsonify(_load_ideas())


@app.route("/api/ideas", methods=["POST"])
def api_create_idea():
    data = request.get_json(force=True)
    now = datetime.now(timezone.utc).isoformat()
    idea = {
        "id": uuid.uuid4().hex[:12],
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "project": data.get("project"),  # null = free memo
        "x": data.get("x", 100),
        "y": data.get("y", 100),
        "color": data.get("color", "yellow"),
        "created_at": now,
        "updated_at": now,
    }
    ideas = _load_ideas()
    ideas.append(idea)
    _save_ideas(ideas)
    return jsonify(idea), 201


@app.route("/api/ideas/<idea_id>", methods=["PUT"])
def api_update_idea(idea_id):
    data = request.get_json(force=True)
    ideas = _load_ideas()
    for idea in ideas:
        if idea["id"] == idea_id:
            for key in ("title", "description", "project", "x", "y", "color"):
                if key in data:
                    idea[key] = data[key]
            idea["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_ideas(ideas)
            return jsonify(idea)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/ideas/<idea_id>", methods=["DELETE"])
def api_delete_idea(idea_id):
    ideas = _load_ideas()
    ideas = [i for i in ideas if i["id"] != idea_id]
    _save_ideas(ideas)
    return jsonify({"ok": True})


@app.route("/api/ideas/<idea_id>/promote", methods=["POST"])
def api_promote_idea(idea_id):
    """Convert an idea into a real project folder with scaffold docs."""
    ideas = _load_ideas()
    idea = next((i for i in ideas if i["id"] == idea_id), None)
    if not idea:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True) if request.is_json else {}
    project_name = data.get("project_name") or idea["title"].strip().replace(" ", "_")
    parent_dir = data.get("parent_dir", "")

    if not project_name or "/" in project_name or ".." in project_name:
        return jsonify({"error": "Invalid project name"}), 400
    if not parent_dir or not Path(parent_dir).is_dir():
        return jsonify({"error": "parent_dir required (existing directory)"}), 400

    project_dir = Path(parent_dir) / project_name
    if project_dir.exists():
        return jsonify({"error": "Project directory already exists"}), 409

    # Scaffold
    project_dir.mkdir()

    # Create .mpm structure
    mpm_data = project_dir / ".mpm" / "data"
    mpm_docs = project_dir / ".mpm" / "docs"
    mpm_data.mkdir(parents=True)
    mpm_docs.mkdir(parents=True)
    (mpm_data / "current").mkdir()
    (mpm_data / "past").mkdir()
    (mpm_data / "future.json").write_text("[]", encoding="utf-8")

    project_md = f"# {idea['title']}\n\n{idea['description'] or 'TBD'}\n"
    (mpm_docs / "PROJECT.md").write_text(project_md, encoding="utf-8")

    # Remove from ideas
    ideas = [i for i in ideas if i["id"] != idea_id]
    _save_ideas(ideas)

    # Register in config
    _add_project_to_config(str(project_dir))

    # Invalidate project cache
    _cache["data"] = None

    return jsonify({"ok": True, "project": project_name})


# ---------------------------------------------------------------------------
# Helper: resolve project directory (validates name)
# ---------------------------------------------------------------------------

def _project_dir(project_name: str):
    """Resolve project name to directory path from registered projects."""
    if "/" in project_name or ".." in project_name:
        return None
    config = load_projects_config()
    for p in config.get("projects", []):
        if Path(p).name == project_name:
            d = Path(p)
            return d if d.is_dir() else None
    return None


# ---------------------------------------------------------------------------
# Task System v2 — future / current / past
# ---------------------------------------------------------------------------

@app.route("/api/v2/future/<project_name>")
def api_v2_get_future(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(load_future(d))


@app.route("/api/v2/future/<project_name>", methods=["POST"])
def api_v2_add_future(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    data = request.get_json(force=True)
    tasks = load_future(d)
    task = {
        "id": uuid.uuid4().hex[:12],
        "title": data.get("title", ""),
        "prompt": data.get("prompt", ""),
        "goal": None,
        "approach": None,
        "verification": None,
        "result": None,
        "memo": None,
        "status": "queued",
        "created": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
        "session_id": None,
        "parent_id": data.get("parent_id"),
    }
    tasks.append(task)  # append to back (lowest priority)
    save_future(d, tasks)
    _cache["data"] = None
    return jsonify(task), 201


@app.route("/api/v2/future/<project_name>/<task_id>", methods=["PUT", "DELETE"])
def api_v2_future_task(project_name, task_id):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    tasks = load_future(d)
    if request.method == "DELETE":
        tasks = [t for t in tasks if t["id"] != task_id]
    else:
        data = request.get_json(force=True)
        for t in tasks:
            if t["id"] == task_id:
                if "title" in data:
                    t["title"] = data["title"]
                if "prompt" in data:
                    t["prompt"] = data["prompt"]
                break
    save_future(d, tasks)
    _cache["data"] = None
    return jsonify({"ok": True})


@app.route("/api/v2/future/<project_name>/reorder", methods=["PUT"])
def api_v2_reorder_future(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    data = request.get_json(force=True)
    order = data.get("order", [])
    tasks = load_future(d)
    task_map = {t["id"]: t for t in tasks}
    reordered = [task_map[tid] for tid in order if tid in task_map]
    seen = set(order)
    for t in tasks:
        if t["id"] not in seen:
            reordered.append(t)
    save_future(d, reordered)
    _cache["data"] = None
    return jsonify(reordered)


@app.route("/api/v2/current/<project_name>")
def api_v2_get_current(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(load_current_tasks(d))


@app.route("/api/v2/past/<project_name>")
def api_v2_get_past(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    date_str = request.args.get("date")
    return jsonify(load_past(d, date_str))


@app.route("/api/v2/past/<project_name>", methods=["POST"])
def api_v2_add_past(project_name):
    """Move a completed task to past."""
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    data = request.get_json(force=True)
    append_past(d, data)
    # Clean up current if session_id provided
    session_id = data.get("session_id")
    if session_id:
        delete_current_task(d, session_id)
    _cache["data"] = None
    return jsonify({"ok": True}), 201


@app.route("/api/v2/project-md/<project_name>")
def api_v2_get_project_md(project_name):
    d = _project_dir(project_name)
    if not d:
        return jsonify({"error": "Project not found"}), 404
    raw = load_project_md(d)
    html = md_lib.markdown(raw, extensions=["tables", "fenced_code"]) if raw else ""
    return jsonify({"raw": raw, "html": html})


# ---------------------------------------------------------------------------
# Autonext state
# ---------------------------------------------------------------------------

@app.route("/api/autonext-state")
def api_autonext_state():
    """Return autonext state if active."""
    config = load_projects_config()
    for project_path in config.get("projects", []):
        d = Path(project_path)
        if not d.is_dir():
            continue
        sf = d / ".mpm" / "data" / "autonext-state.json"
        if sf.exists():
            try:
                data = json.loads(sf.read_text())
                data["project"] = d.name
                return jsonify(data)
            except Exception:
                pass
    return jsonify(None)


# ---------------------------------------------------------------------------
# Hook receiver — Stop/SessionStart notifications from Claude Code
# ---------------------------------------------------------------------------

@app.route("/api/hook/agent-status", methods=["POST"])
def api_hook_agent_status():
    """Receive agent status updates from Claude Code hooks.

    status: "active" | "working" | "waiting" | "offline"
    """
    data = request.get_json(force=True) if request.is_json else {}
    status = data.get("status", "unknown")
    project = data.get("project")
    socketio.emit("agent_status", {
        "project": project,
        "status": status,
    })
    return jsonify({"ok": True})



# ---------------------------------------------------------------------------
# Sessions (tmux gateway)
# ---------------------------------------------------------------------------

@app.route("/api/sessions")
def api_sessions():
    return jsonify(get_all_sessions())


@app.route("/api/sessions", methods=["POST"])
def api_create_session():
    data = request.get_json(force=True)
    project = data.get("project")
    cli_command = data.get("cli_command")
    if not project:
        return jsonify({"error": "project required"}), 400
    try:
        info = create_session(project, cli_command)
        return jsonify({
            "project": info.project,
            "tmux_name": info.tmux_name,
            "state": info.state.value,
        }), 201
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/sessions/<project>/send", methods=["POST"])
def api_send_keys(project):
    data = request.get_json(force=True)
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400
    ok = send_keys(project, text)
    if not ok:
        return jsonify({"error": "Failed to send — session may not exist"}), 404
    return jsonify({"ok": True})


@app.route("/api/sessions/<project>/output")
def api_capture_output(project):
    lines = request.args.get("lines", 200, type=int)
    output = capture_pane(project, lines)
    return jsonify({"output": output})


@app.route("/api/sessions/<project>", methods=["DELETE"])
def api_kill_session(project):
    ok = kill_session(project)
    if not ok:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Project registration
# ---------------------------------------------------------------------------

CLI_CONFIG_PATH = Path.home() / ".mpm" / "config.json"


def _load_cli_config() -> dict:
    return json.loads(CLI_CONFIG_PATH.read_text(encoding="utf-8"))


def _save_cli_config(config: dict) -> None:
    CLI_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _add_project_to_config(project_path: str) -> None:
    config = _load_cli_config()
    projects = config.get("projects", [])
    if project_path not in projects:
        projects.append(project_path)
        config["projects"] = projects
        _save_cli_config(config)


@app.route("/api/init-terminal", methods=["POST"])
def api_init_terminal():
    """Open a terminal in workspace directory for mpm init."""
    config = _load_cli_config()
    workspace = config.get("workspace", str(Path.home() / "MpmWorkspace"))
    Path(workspace).mkdir(parents=True, exist_ok=True)

    # Use a special session name for the init terminal
    project_name = "_mpm-init"
    prefix = config.get("tmux_prefix", "mpm")
    tmux_name = f"{prefix}-{project_name}"

    from mpm.gateway.session_manager import (
        list_tmux_sessions, _run, _start_ttyd, _get_ttyd_port,
        send_keys as sm_send_keys, SessionInfo, SessionState,
    )

    if tmux_name not in list_tmux_sessions():
        rc, _ = _run(["tmux", "new-session", "-d", "-s", tmux_name, "-c", workspace])
        if rc != 0:
            return jsonify({"error": "Failed to create terminal"}), 500
        _run(["tmux", "set-option", "-t", tmux_name, "mouse", "on"])

    port = _start_ttyd(project_name, tmux_name)

    # Auto-type mpm init
    _run(["tmux", "send-keys", "-t", tmux_name, "mpm init", "Enter"])

    return jsonify({"project": project_name, "ttyd_port": port})


@app.route("/api/config/port", methods=["GET"])
def api_get_port():
    config = _load_cli_config()
    return jsonify({"port": config.get("port", 5100)})


@app.route("/api/config/port", methods=["PUT"])
def api_set_port():
    data = request.get_json(force=True)
    port = data.get("port")
    if not isinstance(port, int) or port < 1 or port > 65535:
        return jsonify({"error": "Invalid port number"}), 400
    config = _load_cli_config()
    config["port"] = port
    _save_cli_config(config)
    return jsonify({"port": port, "message": "Restart dashboard to apply"})


@app.route("/api/projects/register", methods=["POST"])
def api_register_project():
    """Register a project directory."""
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if not path or not Path(path).is_dir():
        return jsonify({"error": "Valid directory path required"}), 400
    if not (Path(path) / ".mpm").is_dir():
        return jsonify({"error": "Not an MPM project (missing .mpm/)"}), 400
    _add_project_to_config(path)
    _cache["data"] = None
    return jsonify({"ok": True, "path": path}), 201


@app.route("/api/projects/unregister", methods=["POST"])
def api_unregister_project():
    """Unregister a project directory (does not delete files)."""
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"error": "path required"}), 400
    config = _load_cli_config()
    projects = config.get("projects", [])
    if path in projects:
        projects.remove(path)
        config["projects"] = projects
        _save_cli_config(config)
    _cache["data"] = None
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Saved CLI commands
# ---------------------------------------------------------------------------

@app.route("/api/cli-commands")
def api_cli_commands():
    config = _load_cli_config()
    return jsonify(config.get("saved_commands", []))



@app.route("/api/cli-commands", methods=["POST"])
def api_add_cli_command():
    data = request.get_json(force=True)
    cmd = data.get("command", "").strip()
    if not cmd:
        return jsonify({"error": "command required"}), 400
    config = _load_cli_config()
    commands = config.get("saved_commands", [])
    if cmd not in commands:
        commands.append(cmd)
        config["saved_commands"] = commands
        _save_cli_config(config)
    return jsonify(commands), 201


@app.route("/api/cli-commands", methods=["DELETE"])
def api_delete_cli_command():
    data = request.get_json(force=True)
    cmd = data.get("command", "").strip()
    if not cmd:
        return jsonify({"error": "command required"}), 400
    config = _load_cli_config()
    commands = config.get("saved_commands", [])
    if cmd in commands:
        commands.remove(cmd)
        config["saved_commands"] = commands
        _save_cli_config(config)
    return jsonify(commands)


# ---------------------------------------------------------------------------
# ttyd token proxy (avoids CORS for xterm.js direct connection)
# ---------------------------------------------------------------------------

@app.route("/api/ttyd-token/<project>")
def api_ttyd_token(project):
    sessions = get_all_sessions()
    session = next((s for s in sessions if s["project"] == project), None)
    if not session or not session.get("ttyd_port"):
        return jsonify({"error": "No ttyd session"}), 404
    port = session["ttyd_port"]
    try:
        r = http_requests.get(f"http://127.0.0.1:{port}/ttyd/{project}/token", timeout=3)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 502


def start_server():
    import logging
    import signal as _signal

    # Suppress Flask/Werkzeug dev server warnings
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    config = load_projects_config()
    port = config.get("port", 5100)
    SHUTDOWN_MARKER = MPM_HOME / ".server_shutdown_at"
    GRACE_PERIOD = 60

    should_cleanup = False
    if SHUTDOWN_MARKER.exists():
        try:
            down_since = float(SHUTDOWN_MARKER.read_text().strip())
            elapsed = time.time() - down_since
            if elapsed > GRACE_PERIOD:
                print(f"MPM: server was down {elapsed:.0f}s (>{GRACE_PERIOD}s) — cleaning orphan sessions")
                should_cleanup = True
            else:
                print(f"MPM: server was down {elapsed:.0f}s (<{GRACE_PERIOD}s) — keeping sessions alive")
        except (ValueError, OSError):
            should_cleanup = True
        SHUTDOWN_MARKER.unlink(missing_ok=True)

    if should_cleanup:
        cleanup_all()
    else:
        reconnect_ttyd()

    def _shutdown(signum, frame):
        print(f"\nMPM shutting down (signal {signum}) — sessions kept for {GRACE_PERIOD}s grace period")
        try:
            SHUTDOWN_MARKER.parent.mkdir(parents=True, exist_ok=True)
            SHUTDOWN_MARKER.write_text(str(time.time()))
        except OSError:
            pass
        raise SystemExit(0)

    _signal.signal(_signal.SIGTERM, _shutdown)
    _signal.signal(_signal.SIGINT, _shutdown)

    print(f"MPM Dashboard → http://localhost:{port}")
    start_file_watcher(socketio, cache=_cache)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    start_server()
