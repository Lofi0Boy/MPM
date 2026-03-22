#!/usr/bin/env python3
"""
MPM Phase/Goal CLI — manages project hierarchy.

Usage:
    phase.py add <name> <description>              # Add a new phase
    phase.py remove <phase_id>                     # Remove a phase
    phase.py update <phase_id> <field> <value>     # Update phase field (name, description)
    phase.py activate <phase_id>                   # Set as current phase
    phase.py goal-add <phase_id> <title>           # Add a goal to a phase
    phase.py goal-remove <goal_id>                 # Remove a goal
    phase.py goal-done <goal_id>                   # Mark goal as done
    phase.py goal-undone <goal_id>                 # Mark goal as not done
    phase.py status                                # Show phases, goals, and progress
"""

import json
import sys
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PHASES_PATH = DATA_DIR / "phases.json"
FUTURE_PATH = DATA_DIR / "future.json"
CURRENT_DIR = DATA_DIR / "current"
REVIEW_DIR = DATA_DIR / "review"
PAST_DIR = DATA_DIR / "past"


def _load():
    if not PHASES_PATH.exists():
        return {"current_phase": None, "phases": []}
    return json.loads(PHASES_PATH.read_text(encoding="utf-8"))


def _save(data):
    PHASES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PHASES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _find_phase(data, phase_id):
    for p in data["phases"]:
        if p["id"] == phase_id:
            return p
    return None


def _find_goal(data, goal_id):
    for p in data["phases"]:
        for g in p["goals"]:
            if g["id"] == goal_id:
                return p, g
    return None, None


def _count_tasks_for_goal(goal_id):
    """Count total and completed tasks for a goal across future/current/review/past.
    Discarded tasks are excluded from both total and done."""
    total = 0
    done = 0

    # Future
    if FUTURE_PATH.exists():
        for t in json.loads(FUTURE_PATH.read_text(encoding="utf-8")):
            if t.get("parent_goal") == goal_id:
                total += 1

    # Current
    if CURRENT_DIR.exists():
        for f in CURRENT_DIR.glob("*.json"):
            t = json.loads(f.read_text(encoding="utf-8"))
            if t.get("parent_goal") == goal_id:
                total += 1

    # Review
    if REVIEW_DIR.exists():
        for f in REVIEW_DIR.glob("*.json"):
            t = json.loads(f.read_text(encoding="utf-8"))
            if t.get("parent_goal") == goal_id:
                total += 1

    # Past
    if PAST_DIR.exists():
        for f in PAST_DIR.glob("*.json"):
            for t in json.loads(f.read_text(encoding="utf-8")):
                if t.get("parent_goal") != goal_id:
                    continue
                hr = t.get("human_review") or {}
                verdict = hr.get("verdict", "")
                if verdict == "discard":
                    continue  # excluded
                total += 1
                if verdict == "success":
                    done += 1

    return total, done


def _calc_phase_progress(phase):
    """Calculate phase progress based on task completion across all goals."""
    total = 0
    done = 0
    for g in phase["goals"]:
        t, d = _count_tasks_for_goal(g["id"])
        total += t
        done += d
    if total == 0:
        return 0
    return round(done / total * 100)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(name, description):
    data = _load()
    phase = {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "description": description,
        "goals": [
            {
                "id": uuid.uuid4().hex[:8],
                "title": "Misc",
                "done": False,
            }
        ],
    }
    data["phases"].append(phase)
    # Auto-activate if first phase
    if data["current_phase"] is None:
        data["current_phase"] = phase["id"]
    _save(data)
    print(f"OK: phase added — {phase['id']} ({name})")
    print(f"  default goal: {phase['goals'][0]['id']} (Misc)")


def cmd_remove(phase_id):
    data = _load()
    before = len(data["phases"])
    data["phases"] = [p for p in data["phases"] if p["id"] != phase_id]
    if len(data["phases"]) == before:
        print(f"ERROR: phase {phase_id} not found")
        sys.exit(1)
    if data["current_phase"] == phase_id:
        data["current_phase"] = data["phases"][0]["id"] if data["phases"] else None
    _save(data)
    print(f"OK: phase {phase_id} removed")


def cmd_update(phase_id, field, value):
    data = _load()
    phase = _find_phase(data, phase_id)
    if not phase:
        print(f"ERROR: phase {phase_id} not found")
        sys.exit(1)
    if field not in ("name", "description"):
        print(f"ERROR: field must be 'name' or 'description'")
        sys.exit(1)
    phase[field] = value
    _save(data)
    print(f"OK: phase {phase_id} {field} updated")


def cmd_activate(phase_id):
    data = _load()
    phase = _find_phase(data, phase_id)
    if not phase:
        print(f"ERROR: phase {phase_id} not found")
        sys.exit(1)
    data["current_phase"] = phase_id
    _save(data)
    print(f"OK: current phase → {phase_id} ({phase['name']})")


def cmd_goal_add(phase_id, title):
    data = _load()
    phase = _find_phase(data, phase_id)
    if not phase:
        print(f"ERROR: phase {phase_id} not found")
        sys.exit(1)
    goal = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "done": False,
    }
    phase["goals"].append(goal)
    _save(data)
    print(f"OK: goal added to {phase['name']} — {goal['id']} ({title})")


def cmd_goal_remove(goal_id):
    data = _load()
    phase, goal = _find_goal(data, goal_id)
    if not goal:
        print(f"ERROR: goal {goal_id} not found")
        sys.exit(1)
    phase["goals"] = [g for g in phase["goals"] if g["id"] != goal_id]
    _save(data)
    print(f"OK: goal {goal_id} removed from {phase['name']}")


def cmd_goal_done(goal_id):
    data = _load()
    _, goal = _find_goal(data, goal_id)
    if not goal:
        print(f"ERROR: goal {goal_id} not found")
        sys.exit(1)
    goal["done"] = True
    _save(data)
    print(f"OK: goal {goal_id} marked done")


def cmd_goal_undone(goal_id):
    data = _load()
    _, goal = _find_goal(data, goal_id)
    if not goal:
        print(f"ERROR: goal {goal_id} not found")
        sys.exit(1)
    goal["done"] = False
    _save(data)
    print(f"OK: goal {goal_id} marked undone")


def cmd_status():
    data = _load()
    current = data.get("current_phase")

    if not data["phases"]:
        print("No phases defined.")
        return

    for p in data["phases"]:
        progress = _calc_phase_progress(p)
        marker = " [active]" if p["id"] == current else ""
        print(f"Phase: {p['name']}{marker} [{progress}%]  (id: {p['id']})")
        if p.get("description"):
            print(f"  {p['description']}")

        for g in p["goals"]:
            check = "x" if g["done"] else " "
            total, done = _count_tasks_for_goal(g["id"])
            task_info = f" ({done}/{total} tasks)" if total > 0 else ""
            print(f"  [{check}] {g['title']}{task_info}  (id: {g['id']})")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add" and len(sys.argv) >= 4:
        cmd_add(sys.argv[2], sys.argv[3])
    elif cmd == "remove" and len(sys.argv) >= 3:
        cmd_remove(sys.argv[2])
    elif cmd == "update" and len(sys.argv) >= 5:
        cmd_update(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "activate" and len(sys.argv) >= 3:
        cmd_activate(sys.argv[2])
    elif cmd == "goal-add" and len(sys.argv) >= 4:
        cmd_goal_add(sys.argv[2], sys.argv[3])
    elif cmd == "goal-remove" and len(sys.argv) >= 3:
        cmd_goal_remove(sys.argv[2])
    elif cmd == "goal-done" and len(sys.argv) >= 3:
        cmd_goal_done(sys.argv[2])
    elif cmd == "goal-undone" and len(sys.argv) >= 3:
        cmd_goal_undone(sys.argv[2])
    elif cmd == "status":
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
