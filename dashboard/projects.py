"""
Parse ROADMAP.md and handoff files for each project in MpmWorkspace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

WORKSPACE_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CheckItem:
    text: str
    done: bool


@dataclass
class Phase:
    number: int
    name: str
    goal: str
    items: list[CheckItem] = field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.done)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def is_complete(self) -> bool:
        return self.total_count > 0 and self.done_count == self.total_count

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "goal": self.goal,
            "done_count": self.done_count,
            "total_count": self.total_count,
            "is_complete": self.is_complete,
            "items": [{"text": i.text, "done": i.done} for i in self.items],
        }


@dataclass
class Commit:
    number: int
    timestamp: str
    summary: str
    details: str

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "details": self.details,
        }


@dataclass
class ProjectData:
    name: str
    phases: list[Phase]
    commits: list[Commit]
    next_tasks: list[str]
    error: Optional[str] = None

    def current_phase(self) -> Optional[Phase]:
        for phase in self.phases:
            if not phase.is_complete:
                return phase
        return self.phases[-1] if self.phases else None

    def to_dict(self) -> dict:
        cp = self.current_phase()
        return {
            "name": self.name,
            "phases": [p.to_dict() for p in self.phases],
            "current_phase": cp.to_dict() if cp else None,
            "commits": [c.to_dict() for c in self.commits],
            "next_tasks": self.next_tasks,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_roadmap(path: Path) -> list[Phase]:
    text = path.read_text(encoding="utf-8")
    phases: list[Phase] = []

    # Split by H2 headings
    sections = re.split(r"^## ", text, flags=re.MULTILINE)

    for section in sections:
        # Match "Phase N: Name"
        m = re.match(r"Phase (\d+):\s*(.+)", section)
        if not m:
            continue

        number = int(m.group(1))
        name = m.group(2).strip()

        # Extract goal line
        goal_m = re.search(r"^Goal:\s*(.+)", section, re.MULTILINE)
        goal = goal_m.group(1).strip() if goal_m else ""

        # Extract checklist items
        items: list[CheckItem] = []
        for item_m in re.finditer(r"^- \[(x| )\] (.+)", section, re.MULTILINE):
            done = item_m.group(1) == "x"
            raw_text = item_m.group(2).strip()
            # Strip trailing ✓ markers sometimes added manually
            text = raw_text.rstrip(" ✓").strip()
            items.append(CheckItem(text=text, done=done))

        phases.append(Phase(number=number, name=name, goal=goal, items=items))

    return phases


def parse_handoff(path: Path) -> tuple[list[Commit], list[str]]:
    text = path.read_text(encoding="utf-8")
    commits: list[Commit] = []
    next_tasks: list[str] = []

    # Find "## This Session" section
    session_m = re.search(
        r"^## This Session\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )

    if session_m:
        session_text = session_m.group(1)

        # Split by ### Commit headings
        commit_sections = re.split(r"^### ", session_text, flags=re.MULTILINE)

        for cs in commit_sections:
            cm = re.match(r"Commit (\d+) \((\w+)\) — (.+?)\n(.*)", cs, re.DOTALL)
            if not cm:
                continue
            commits.append(Commit(
                number=int(cm.group(1)),
                timestamp=cm.group(2),
                summary=cm.group(3).strip(),
                details=cm.group(4).strip(),
            ))

    # Find "## Next Tasks" section
    next_m = re.search(
        r"^## Next Tasks\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )

    if next_m:
        for task_m in re.finditer(r"^- \[ \] (.+)", next_m.group(1), re.MULTILINE):
            next_tasks.append(task_m.group(1).strip())

    return commits, next_tasks


def load_project(project_dir: Path) -> ProjectData:
    name = project_dir.name

    roadmap_path = project_dir / "docs" / "ROADMAP.md"
    if not roadmap_path.exists():
        return ProjectData(
            name=name, phases=[], commits=[], next_tasks=[],
            error="ROADMAP.md not found",
        )

    try:
        phases = parse_roadmap(roadmap_path)
    except Exception as e:
        return ProjectData(
            name=name, phases=[], commits=[], next_tasks=[],
            error=f"ROADMAP parse error: {e}",
        )

    handoff_dir = project_dir / "docs" / "handoff"
    commits: list[Commit] = []
    next_tasks: list[str] = []

    if handoff_dir.exists():
        handoff_files = sorted(handoff_dir.glob("*.md"))
        if handoff_files:
            latest = handoff_files[-1]
            try:
                commits, next_tasks = parse_handoff(latest)
            except Exception as e:
                return ProjectData(
                    name=name, phases=phases, commits=[], next_tasks=[],
                    error=f"Handoff parse error: {e}",
                )

    return ProjectData(name=name, phases=phases, commits=commits, next_tasks=next_tasks)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_projects() -> list[dict]:
    projects: list[ProjectData] = []

    for d in sorted(WORKSPACE_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        roadmap = d / "docs" / "ROADMAP.md"
        if not roadmap.exists():
            continue
        projects.append(load_project(d))

    return [p.to_dict() for p in projects]
