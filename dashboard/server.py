"""
MPM Dashboard — web server.

Run from the MPM root:
    python dashboard/server.py
"""

import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests as http_requests

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import markdown as md_lib
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit

from gateway.file_watcher import start_file_watcher
from gateway.multiplexer import start_polling, subscribe, unsubscribe
from gateway.session_manager import (
    capture_pane,
    create_session,
    get_all_sessions,
    kill_session,
    send_keys,
)
from projects import WORKSPACE_ROOT, get_all_projects

IDEAS_PATH = Path(__file__).parent.parent / "data" / "ideas.json"

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*")

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


@app.route("/api/projects")
def api_projects():
    projects = get_projects_cached()
    return jsonify({"projects": projects, "updated_at": _cache["at"]})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    _cache["data"] = None
    projects = get_projects_cached()
    return jsonify({"projects": projects, "updated_at": _cache["at"]})


@app.route("/api/doc/<project_name>/<doc_type>")
def api_doc(project_name, doc_type):
    if "/" in project_name or ".." in project_name:
        return jsonify({"error": "Invalid project name"}), 400

    doc_map = {
        "roadmap": "docs/ROADMAP.md",
        "readme": "README.md",
        "architecture": "docs/ARCHITECTURE.md",
    }
    rel_path = doc_map.get(doc_type.lower())
    if not rel_path:
        return jsonify({"error": "Unknown doc type"}), 400

    project_dir = WORKSPACE_ROOT / project_name
    if not project_dir.is_dir():
        return jsonify({"error": "Project not found"}), 404

    doc_path = project_dir / rel_path
    if not doc_path.exists():
        return jsonify({"error": "File not found"}), 404

    raw = doc_path.read_text(encoding="utf-8")
    html = md_lib.markdown(raw, extensions=["tables", "fenced_code"])
    return jsonify({"html": html})


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

    if not project_name or "/" in project_name or ".." in project_name:
        return jsonify({"error": "Invalid project name"}), 400

    project_dir = WORKSPACE_ROOT / project_name
    if project_dir.exists():
        return jsonify({"error": "Project directory already exists"}), 409

    # Scaffold
    project_dir.mkdir()
    (project_dir / "docs").mkdir()
    (project_dir / "docs" / "handoff").mkdir()

    readme = f"# {idea['title']}\n\n{idea['description']}\n"
    (project_dir / "README.md").write_text(readme, encoding="utf-8")

    roadmap = (
        f"## Overview\n{idea['title']}\n\n"
        f"## Phase 1: Planning\n"
        f"Goal: {idea['description'] or 'TBD'}\n\n"
        f"- [ ] Define scope and requirements\n"
    )
    (project_dir / "docs" / "ROADMAP.md").write_text(roadmap, encoding="utf-8")

    # Remove from ideas
    ideas = [i for i in ideas if i["id"] != idea_id]
    _save_ideas(ideas)

    # Invalidate project cache
    _cache["data"] = None

    return jsonify({"ok": True, "project": project_name})


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
# Saved CLI commands
# ---------------------------------------------------------------------------

CLI_CONFIG_PATH = Path(__file__).parent.parent / "data" / "cli_patterns.json"


def _load_cli_config() -> dict:
    return json.loads(CLI_CONFIG_PATH.read_text(encoding="utf-8"))


def _save_cli_config(config: dict) -> None:
    CLI_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@app.route("/api/cli-commands")
def api_cli_commands():
    config = _load_cli_config()
    return jsonify(config.get("saved_commands", []))


@app.route("/api/config")
def api_config():
    config = _load_cli_config()
    return jsonify({
        "ssh_host": config.get("ssh_host", ""),
        "tmux_prefix": config.get("tmux_prefix", "mpm"),
    })


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


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

@socketio.on("subscribe")
def ws_subscribe(data):
    project = data.get("project")
    if project:
        output = subscribe(project)
        emit("terminal_output", {"project": project, "output": output})


@socketio.on("unsubscribe")
def ws_unsubscribe(data):
    project = data.get("project")
    if project:
        unsubscribe(project)


@socketio.on("send_input")
def ws_send_input(data):
    project = data.get("project")
    text = data.get("text", "")
    if project and text:
        send_keys(project, text)




# Open tmux session in native terminal emulator
@app.route("/api/sessions/<project>/open-terminal", methods=["POST"])
def api_open_terminal(project):
    config = json.loads(CLI_CONFIG_PATH.read_text(encoding="utf-8"))
    prefix = config.get("tmux_prefix", "mpm")
    tmux_name = f"{prefix}-{project}"

    # Try common terminal emulators in order
    terminals = [
        ["gnome-terminal", "--", "tmux", "attach-session", "-t", tmux_name],
        ["konsole", "-e", "tmux", "attach-session", "-t", tmux_name],
        ["xfce4-terminal", "-e", f"tmux attach-session -t {tmux_name}"],
        ["x-terminal-emulator", "-e", f"tmux attach-session -t {tmux_name}"],
        ["xterm", "-e", "tmux", "attach-session", "-t", tmux_name],
    ]

    for cmd in terminals:
        try:
            subprocess.Popen(cmd, start_new_session=True)
            return jsonify({"ok": True, "terminal": cmd[0]})
        except FileNotFoundError:
            continue

    return jsonify({"error": "No terminal emulator found", "command": f"tmux attach-session -t {tmux_name}"}), 404


if __name__ == "__main__":
    port = 5100
    print(f"MPM Dashboard → http://localhost:{port}")
    start_polling(socketio)
    start_file_watcher(socketio)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
