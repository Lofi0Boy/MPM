"""
Parse project data and load .mpm/ task system for each registered project.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".mpm" / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"projects": []}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Task system v2 — .mpm/data/{future,current,past}
# ---------------------------------------------------------------------------

def _data_path(project_dir: Path) -> Path:
    return project_dir / ".mpm" / "data"


def load_future(project_dir: Path) -> list:
    return _load_json(_data_path(project_dir) / "future.json", default=[])


def save_future(project_dir: Path, data: list) -> None:
    _save_json(_data_path(project_dir) / "future.json", data)


def load_current_tasks(project_dir: Path) -> list:
    """Load all active tasks from current/ directory."""
    current_dir = _data_path(project_dir) / "current"
    if not current_dir.exists():
        return []
    tasks = []
    for f in current_dir.glob("*.json"):
        task = _load_json(f)
        if task:
            tasks.append(task)
    return tasks


def save_current_task(project_dir: Path, session_id: str, data: dict) -> None:
    _save_json(_data_path(project_dir) / "current" / f"{session_id}.json", data)


def delete_current_task(project_dir: Path, session_id: str) -> bool:
    path = _data_path(project_dir) / "current" / f"{session_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def load_past(project_dir: Path, date_str: str | None = None) -> list:
    """Load past tasks. If date_str given, load that day only. Otherwise load all."""
    past_dir = _data_path(project_dir) / "past"
    if not past_dir.exists():
        return []
    if date_str:
        return _load_json(past_dir / f"{date_str}.json", default=[])
    # Load all past files, sort by created timestamp (oldest first)
    # Frontend reverses for display (newest on top)
    tasks = []
    for f in sorted(past_dir.glob("*.json")):
        day_tasks = _load_json(f, default=[])
        tasks.extend(day_tasks)
    tasks.sort(key=lambda t: t.get("created", ""))
    return tasks


def _get_tz():
    try:
        config = _load_config()
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.get("timezone", "UTC"))
    except Exception:
        from datetime import timezone as _tz
        return _tz.utc


def append_past(project_dir: Path, task: dict) -> None:
    """Append a completed task to today's past file."""
    from datetime import datetime
    date_str = datetime.now(_get_tz()).strftime("%y%m%d")
    past_dir = _data_path(project_dir) / "past"
    path = past_dir / f"{date_str}.json"
    existing = _load_json(path, default=[])
    existing.append(task)
    _save_json(path, existing)


# ---------------------------------------------------------------------------
# PROJECT.md
# ---------------------------------------------------------------------------

def load_project_md(project_dir: Path) -> str:
    path = project_dir / ".mpm" / "docs" / "PROJECT.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_project_md(project_dir: Path) -> tuple[str, str]:
    """Extract project name and description from PROJECT.md.

    Required structure:
        # Project Name
        ...
        ## Description
        Description text...

    Returns (project_name, description). Falls back to dir name and empty string.
    """
    text = load_project_md(project_dir)
    if not text:
        return project_dir.name, ""

    # Extract project name from first H1
    project_name = project_dir.name
    m = re.match(r"^#\s+(.+)", text, re.MULTILINE)
    if m:
        project_name = m.group(1).strip()

    # Extract description: first non-empty line after # heading (before any ## section)
    description = ""
    lines = text.splitlines()
    past_h1 = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            past_h1 = True
            continue
        if past_h1:
            if stripped.startswith("## "):
                break
            if stripped:
                description = stripped
                break

    return project_name, description


def parse_phases_from_md(project_dir: Path) -> list[dict]:
    """Parse phases from PROJECT.md's ## Phases section.

    Format:
        ## Phases
        ### Phase Name [active] [60%]
        Description text

        ### Another Phase [0%]
        Description text
    """
    text = load_project_md(project_dir)
    if not text:
        return []

    # Find ## Phases section
    lines = text.splitlines()
    in_phases = False
    phases: list[dict] = []
    current_phase = None

    for line in lines:
        stripped = line.strip()

        # Detect start of ## Phases section
        if re.match(r"^##\s+Phases\s*$", stripped, re.IGNORECASE):
            in_phases = True
            continue

        # Exit on next ## section
        if in_phases and re.match(r"^##\s+", stripped) and not re.match(r"^###", stripped):
            break

        if not in_phases:
            continue

        # Parse ### heading
        m = re.match(r"^###\s+(.+)", stripped)
        if m:
            if current_phase:
                phases.append(current_phase)

            heading = m.group(1).strip()
            # Extract [active] tag
            is_active = "[active]" in heading.lower()
            heading = re.sub(r"\[active\]", "", heading, flags=re.IGNORECASE).strip()

            # Extract [N%] progress
            progress = 0.0
            pm = re.search(r"\[(\d+)%\]", heading)
            if pm:
                progress = int(pm.group(1)) / 100.0
                heading = re.sub(r"\[\d+%\]", "", heading).strip()

            current_phase = {
                "name": heading,
                "description": "",
                "goals": [],
                "status": "active" if is_active else ("done" if progress >= 1.0 else "planned"),
                "progress": progress,
            }
            continue

        # Bullet points → goals list
        if current_phase and stripped.startswith("- "):
            current_phase["goals"].append(stripped[2:])
            continue

        # Non-bullet text → description
        if current_phase and stripped:
            if current_phase["description"]:
                current_phase["description"] += " " + stripped
            else:
                current_phase["description"] = stripped

    if current_phase:
        phases.append(current_phase)

    return phases


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ProjectData:
    name: str
    project_name: str = ""
    description: str = ""
    current_tasks: list[dict] = field(default_factory=list)
    future_tasks: list[dict] = field(default_factory=list)
    past_tasks: list[dict] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    project_md: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "project_name": self.project_name,
            "description": self.description,
            "current_tasks": self.current_tasks,
            "future_tasks": self.future_tasks,
            "past_tasks": self.past_tasks,
            "phases": self.phases,
            "project_md": self.project_md,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_phases(project_dir: Path) -> list:
    return parse_phases_from_md(project_dir)


def load_project(project_dir: Path) -> ProjectData:
    name = project_dir.name
    project_name, description = parse_project_md(project_dir)

    # Task system v2
    current_tasks = load_current_tasks(project_dir)
    future_tasks = load_future(project_dir)
    past_tasks = load_past(project_dir)
    phases = load_phases(project_dir)
    project_md = load_project_md(project_dir)

    return ProjectData(
        name=name,
        project_name=project_name,
        description=description,
        current_tasks=current_tasks,
        future_tasks=future_tasks,
        past_tasks=past_tasks,
        phases=phases,
        project_md=project_md,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_projects() -> list[dict]:
    config = _load_config()
    project_paths = config.get("projects", [])
    projects: list[ProjectData] = []
    for p in project_paths:
        d = Path(p)
        if not d.is_dir():
            continue
        if not (d / ".mpm").is_dir():
            continue
        projects.append(load_project(d))
    return [p.to_dict() for p in projects]
