#!/usr/bin/env python3
"""MPM Project Progress — structured terminal view."""

import json
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PHASES_PATH = DATA_DIR / "phases.json"
FUTURE_PATH = DATA_DIR / "future.json"
CURRENT_DIR = DATA_DIR / "current"
REVIEW_DIR = DATA_DIR / "review"
PAST_DIR = DATA_DIR / "past"

BOX_W = 62

# Sort order for task categories
CATEGORY_ORDER = {"done": 0, "in_progress": 1, "review": 2, "pending": 3}


def _display_width(s):
    """Calculate display width accounting for wide unicode characters."""
    w = 0
    for ch in s:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("F", "W") else 1
    return w


def _load_phases():
    if not PHASES_PATH.exists():
        return {"current_phase": None, "phases": []}
    return json.loads(PHASES_PATH.read_text(encoding="utf-8"))


def _all_tasks():
    """Collect all tasks with their status category."""
    tasks = []

    if FUTURE_PATH.exists():
        for t in json.loads(FUTURE_PATH.read_text(encoding="utf-8")):
            tasks.append({"task": t, "category": "pending"})

    if CURRENT_DIR.exists():
        for f in CURRENT_DIR.glob("*.json"):
            t = json.loads(f.read_text(encoding="utf-8"))
            status = t.get("status", "dev")
            if status == "agent-review":
                tasks.append({"task": t, "category": "review"})
            else:
                tasks.append({"task": t, "category": "in_progress"})

    if REVIEW_DIR.exists():
        for f in REVIEW_DIR.glob("*.json"):
            t = json.loads(f.read_text(encoding="utf-8"))
            tasks.append({"task": t, "category": "review"})

    if PAST_DIR.exists():
        for f in PAST_DIR.glob("*.json"):
            for t in json.loads(f.read_text(encoding="utf-8")):
                hr = t.get("human_review") or {}
                verdict = hr.get("verdict", "")
                if verdict == "discard":
                    continue
                tasks.append({"task": t, "category": "done"})

    return tasks


def _tasks_for_goal(all_tasks, goal_id):
    """Filter and sort tasks belonging to a goal."""
    goal_tasks = [t for t in all_tasks if t["task"].get("parent_goal") == goal_id]
    goal_tasks.sort(key=lambda t: CATEGORY_ORDER.get(t["category"], 9))
    return goal_tasks


def _calc_progress(task_list):
    total = len(task_list)
    done = sum(1 for t in task_list if t["category"] == "done")
    if total == 0:
        return 0, 0, 0
    return total, done, round(done / total * 100)


def _progress_bar(percent, width=20):
    filled = round(width * percent / 100)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def _status_icon(category):
    icons = {"done": "[x]", "in_progress": "[~]", "review": "[?]", "pending": "[ ]"}
    return icons.get(category, "[ ]")


def _box_top(title):
    inner = f" {title} "
    remaining = BOX_W - 2 - len(inner) - 1
    return f"\u250c\u2500{inner}" + "\u2500" * max(0, remaining) + "\u2510"


def _box_bottom():
    return "\u2514" + "\u2500" * (BOX_W - 2) + "\u2518"


def _box_line(content=""):
    dw = _display_width(content)
    padding = BOX_W - 4 - dw
    if padding < 0:
        # Truncate content to fit
        truncated = ""
        w = 0
        for ch in content:
            cw = 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
            if w + cw > BOX_W - 4:
                break
            truncated += ch
            w += cw
        content = truncated
        padding = BOX_W - 4 - _display_width(content)
    return f"\u2502  {content}" + " " * padding + "\u2502"


def _box_sep():
    return "\u2502  " + "\u2500" * (BOX_W - 6) + "  \u2502"


def render():
    data = _load_phases()
    all_tasks = _all_tasks()
    current_phase = data.get("current_phase")
    phases = data.get("phases", [])

    if not phases:
        print("No phases defined.")
        return

    print(_box_top("MPM Project Progress"))
    print(_box_line())
    print(_box_line("[x] done  [~] in progress  [?] review  [ ] pending"))
    print(_box_line())

    for pi, phase in enumerate(phases):
        is_active = phase["id"] == current_phase
        goals = phase.get("goals", [])

        phase_tasks = []
        for g in goals:
            phase_tasks.extend(_tasks_for_goal(all_tasks, g["id"]))

        total, done, percent = _calc_progress(phase_tasks)
        bar = _progress_bar(percent)

        if is_active:
            print(_box_line(f"Phase {pi+1}. {phase['name']} [active]"))
            print(_box_line(f"{bar}  {percent}%"))
            print(_box_line())

            for gi, goal in enumerate(goals):
                goal_tasks = _tasks_for_goal(all_tasks, goal["id"])
                g_total, g_done, g_percent = _calc_progress(goal_tasks)
                g_bar = _progress_bar(g_percent)

                print(_box_line(f"\u251c\u2500 Goal {gi+1}. {goal['title']}"))
                print(_box_line(f"\u2502  {g_bar}  {g_percent}%"))

                for t in goal_tasks:
                    icon = _status_icon(t["category"])
                    title = t["task"].get("title", "?")
                    print(_box_line(f"\u2502  {icon} {title}"))

                if gi < len(goals) - 1:
                    print(_box_line("\u2502"))
        else:
            if pi == 0 or (pi > 0 and phases[pi - 1]["id"] == current_phase):
                print(_box_sep())
            label = f"Phase {pi+1}. {phase['name']}"
            pad = 24 - _display_width(label)
            if pad < 1:
                pad = 1
            print(_box_line(f"{label}" + " " * pad + f"{bar}  {percent}%"))

    print(_box_line())
    print(_box_bottom())


if __name__ == "__main__":
    render()
