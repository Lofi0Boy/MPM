"""
MPM Dashboard — web server.

Run from the MPM root:
    python dashboard/server.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import markdown as md_lib
from flask import Flask, jsonify, render_template

from projects import WORKSPACE_ROOT, get_all_projects

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


if __name__ == "__main__":
    port = 5100
    print(f"MPM Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
