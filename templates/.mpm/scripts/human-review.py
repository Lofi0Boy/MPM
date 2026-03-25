#!/usr/bin/env python3
"""MPM Human Review — structured view of review queue."""

import json
import sys
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
REVIEW_DIR = DATA_DIR / "review"

BOX_W = 55


def _dw(s):
    """Display width accounting for wide chars."""
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return w


def _center_label(label):
    """Create a line like ├──── Label ─────┤"""
    inner = f" {label} "
    side = (BOX_W - 2 - len(inner)) // 2
    rem = BOX_W - 2 - side - len(inner)
    return "\u251c" + "\u2500" * side + inner + "\u2500" * rem + "\u2524"


def _top_label(label):
    """Create top line like ┌──── Label ─────┐"""
    inner = f" {label} "
    side = (BOX_W - 2 - len(inner)) // 2
    rem = BOX_W - 2 - side - len(inner)
    return "\u250c" + "\u2500" * side + inner + "\u2500" * rem + "\u2510"


def _bottom():
    return "\u2514" + "\u2500" * (BOX_W - 2) + "\u2518"


def _line(content=""):
    dw = _dw(content)
    padding = BOX_W - 4 - dw
    if padding < 0:
        truncated = ""
        w = 0
        for ch in content:
            cw = 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
            if w + cw > BOX_W - 4:
                break
            truncated += ch
            w += cw
        content = truncated
        padding = BOX_W - 4 - _dw(content)
    return f"\u2502 {content}" + " " * (padding + 1) + "\u2502"


def _load_review_queue():
    tasks = []
    if not REVIEW_DIR.exists():
        return tasks
    for f in sorted(REVIEW_DIR.glob("*.json")):
        tasks.append(json.loads(f.read_text(encoding="utf-8")))
    return tasks


def render_queue():
    tasks = _load_review_queue()
    if not tasks:
        print("No tasks waiting for review.")
        return

    print(f"Review queue: {len(tasks)} task(s)")
    print()
    for i, t in enumerate(tasks):
        reviews = t.get("agent_reviews", [])
        last = reviews[-1] if reviews else {}
        verdict = last.get("verdict", "?")
        title = t.get("title", "?")
        is_ui = last.get("is_ui", False)
        ui_tag = " [UI]" if is_ui else ""
        what = last.get("what", "")
        print(f"  [{i+1}] [{verdict}] {title}{ui_tag}")
        if what:
            print(f"      {what}")
    print()


def render_detail(index):
    """Render detail view by 1-based index."""
    tasks = _load_review_queue()
    idx = int(index) - 1
    if idx < 0 or idx >= len(tasks):
        print(f"ERROR: index {index} out of range (1-{len(tasks)})")
        return

    task = tasks[idx]
    reviews = task.get("agent_reviews", [])
    last = reviews[-1] if reviews else {}

    title = task.get("title", "?")
    is_ui = last.get("is_ui", False)
    verdict = last.get("verdict", "?")
    what = last.get("what", "")
    result = last.get("result", "")
    evidence = last.get("evidence", {})
    screenshots = evidence.get("screenshots", [])
    logs = evidence.get("logs", [])

    verdict_label = f"Agent: {verdict.title()}"
    if verdict == "needs-input":
        verdict_label = "Agent: Needs Input"

    ui_tag = " [UI]" if is_ui else ""

    # Header
    print(_top_label(verdict_label))
    print(_line())
    print(_line(f"{title}{ui_tag}"))
    if what:
        print(_line(what))
    print(_line())

    # Result
    print(_center_label("Result"))
    print(_line())
    if result:
        for r in result.split("\n"):
            print(_line(r))
    print(_line())

    # Evidence
    if screenshots or logs:
        print(_center_label("Evidence"))
        print(_line())
        for s in screenshots:
            print(_line(f">> {s}"))
        for log in logs:
            cmd = log.get("command", "")
            out = log.get("output", "")
            print(_line(f"$ {cmd}"))
            if out:
                print(_line(f"> {out}"))
        print(_line())

    print(_bottom())

    # Print task_id for the skill to use
    print(f"\ntask_id: {task.get('id', '?')}")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        render_detail(sys.argv[1])
    else:
        render_queue()
