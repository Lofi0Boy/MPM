"""
MPM Dashboard — web server.

Run from the MPM root:
    python dashboard/server.py
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import markdown as md_lib
from flask import Flask, jsonify, render_template, request

from projects import WORKSPACE_ROOT, get_all_projects

IDEAS_PATH = Path(__file__).parent.parent / "data" / "ideas.json"

app = Flask(__name__, template_folder="templates")

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


if __name__ == "__main__":
    port = 5100
    print(f"MPM Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
