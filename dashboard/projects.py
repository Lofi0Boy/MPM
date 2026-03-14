"""
Parse ROADMAP.md and handoff files for each project in MpmWorkspace.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
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
class Handoff:
    filename: str
    commits: list[Commit]
    next_tasks: list[str]

    @property
    def headline(self) -> str:
        if self.commits:
            return self.commits[0].summary
        return "—"

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "headline": self.headline,
            "commits": [c.to_dict() for c in self.commits],
            "next_tasks": self.next_tasks,
        }


@dataclass
class ProjectData:
    name: str
    phases: list[Phase]
    handoffs: list[Handoff]
    unhandoffed_commits: list[dict] = field(default_factory=list)
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
            "handoffs": [h.to_dict() for h in self.handoffs],
            "unhandoffed_commits": self.unhandoffed_commits,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_roadmap(path: Path) -> list[Phase]:
    text = path.read_text(encoding="utf-8")
    phases: list[Phase] = []

    for section in re.split(r"^## ", text, flags=re.MULTILINE):
        m = re.match(r"Phase (\d+):\s*(.+)", section)
        if not m:
            continue

        number = int(m.group(1))
        name = m.group(2).strip()

        goal_m = re.search(r"^Goal:\s*(.+)", section, re.MULTILINE)
        goal = goal_m.group(1).strip() if goal_m else ""

        items: list[CheckItem] = []
        for item_m in re.finditer(r"^- \[(x| )\] (.+)", section, re.MULTILINE):
            done = item_m.group(1) == "x"
            text = item_m.group(2).strip().rstrip(" ✓").strip()
            items.append(CheckItem(text=text, done=done))

        phases.append(Phase(number=number, name=name, goal=goal, items=items))

    return phases


def parse_handoff(path: Path) -> Handoff:
    text = path.read_text(encoding="utf-8")
    filename = path.stem
    commits: list[Commit] = []
    next_tasks: list[str] = []

    session_m = re.search(
        r"^## This Session\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if session_m:
        for cs in re.split(r"^### ", session_m.group(1), flags=re.MULTILINE):
            cm = re.match(r"Commit (\d+) \((\w+)\) — (.+?)\n(.*)", cs, re.DOTALL)
            if not cm:
                continue
            commits.append(Commit(
                number=int(cm.group(1)),
                timestamp=cm.group(2),
                summary=cm.group(3).strip(),
                details=cm.group(4).strip(),
            ))

    next_m = re.search(
        r"^## Next Tasks\s*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if next_m:
        for task_m in re.finditer(r"^- \[ \] (.+)", next_m.group(1), re.MULTILINE):
            next_tasks.append(task_m.group(1).strip())

    return Handoff(filename=filename, commits=commits, next_tasks=next_tasks)


def parse_handoff_dt(filename: str) -> Optional[datetime]:
    """Convert yymmddhhmm filename to datetime."""
    if len(filename) < 10:
        return None
    try:
        return datetime(
            2000 + int(filename[0:2]),
            int(filename[2:4]),
            int(filename[4:6]),
            int(filename[6:8]),
            int(filename[8:10]),
        )
    except ValueError:
        return None


def get_unhandoffed_commits(project_dir: Path, since: Optional[datetime]) -> list[dict]:
    """Return git commits made after `since` (i.e., not yet captured in a handoff)."""
    cmd = ["git", "-C", str(project_dir), "log", "--format=%h|%s"]
    if since:
        cmd.append(f"--after={since.strftime('%Y-%m-%d %H:%M')}")
    else:
        cmd += ["-n", "5"]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or not r.stdout.strip():
            return []
        commits = []
        for line in r.stdout.strip().splitlines():
            parts = line.split("|", 1)
            if len(parts) == 2:
                commits.append({"hash": parts[0], "summary": parts[1]})
        return commits
    except Exception:
        return []


def load_project(project_dir: Path) -> ProjectData:
    name = project_dir.name

    roadmap_path = project_dir / "docs" / "ROADMAP.md"
    if not roadmap_path.exists():
        return ProjectData(name=name, phases=[], handoffs=[], error="ROADMAP.md not found")

    try:
        phases = parse_roadmap(roadmap_path)
    except Exception as e:
        return ProjectData(name=name, phases=[], handoffs=[], error=f"ROADMAP parse error: {e}")

    handoffs: list[Handoff] = []
    handoff_dir = project_dir / "docs" / "handoff"
    if handoff_dir.exists():
        for hf in sorted(handoff_dir.glob("*.md"), reverse=True):
            try:
                handoffs.append(parse_handoff(hf))
            except Exception as e:
                handoffs.append(Handoff(
                    filename=hf.stem,
                    commits=[],
                    next_tasks=[f"Parse error: {e}"],
                ))

    # Commits not yet captured in any handoff
    since_dt = parse_handoff_dt(handoffs[0].filename) if handoffs else None
    unhandoffed = get_unhandoffed_commits(project_dir, since_dt)

    return ProjectData(
        name=name,
        phases=phases,
        handoffs=handoffs,
        unhandoffed_commits=unhandoffed,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_projects() -> list[dict]:
    projects: list[ProjectData] = []
    for d in sorted(WORKSPACE_ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not (d / "docs" / "ROADMAP.md").exists():
            continue
        projects.append(load_project(d))
    return [p.to_dict() for p in projects]
