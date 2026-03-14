"""
MPM Dashboard — web server.

Run from the MPM root:
    python dashboard/server.py

Or from within the dashboard directory:
    python server.py
"""

import sys
import time
from pathlib import Path

# Make sibling imports work regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, jsonify, render_template

from projects import get_all_projects

app = Flask(__name__, template_folder="templates")

# ---------------------------------------------------------------------------
# Simple TTL cache — avoids re-parsing files on every request
# ---------------------------------------------------------------------------

_cache: dict = {"data": None, "at": 0.0}
CACHE_TTL = 30  # seconds


def get_projects_cached() -> list[dict]:
    now = time.time()
    if _cache["data"] is None or now - _cache["at"] > CACHE_TTL:
        _cache["data"] = get_all_projects()
        _cache["at"] = now
    return _cache["data"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/projects")
def api_projects():
    projects = get_projects_cached()
    return jsonify({
        "projects": projects,
        "updated_at": _cache["at"],
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Force cache invalidation."""
    _cache["data"] = None
    projects = get_projects_cached()
    return jsonify({
        "projects": projects,
        "updated_at": _cache["at"],
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = 5100
    print(f"MPM Dashboard → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
