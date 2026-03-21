#!/usr/bin/env python3
"""
MPM Task System CLI — manages task transitions.

Usage:
    task.py pop <session_id>              # future → current
    task.py create <session_id> <title> <prompt>  # → current (direct, skip future)
    task.py complete <session_id> <status> [--memo "..."]  # current → past
    task.py add <title> <prompt>          # → future (append to back)
    task.py update <session_id> <field> <value>  # update current task field
    task.py status                        # show current state
"""

import json
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).parent.parent / "data"
FUTURE_PATH = DATA_DIR / "future.json"
CURRENT_DIR = DATA_DIR / "current"
PAST_DIR = DATA_DIR / "past"
CONFIG_PATH = Path.home() / ".mpm" / "config.json"


def _get_tz():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return ZoneInfo(config.get("timezone", "UTC"))
    except Exception:
        return timezone.utc


def _load_json(path, default=None):
    if not path.exists():
        return default if default is not None else []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_pop(session_id):
    """Pop first task from future → current/{session_id}.json"""
    future = _load_json(FUTURE_PATH, [])
    if not future:
        print("ERROR: future queue is empty.")
        sys.exit(1)

    current_path = CURRENT_DIR / f"{session_id}.json"
    if current_path.exists():
        existing = _load_json(current_path)
        print(f"ERROR: session already has active task: {existing.get('title', '?')}")
        sys.exit(1)

    task = future.pop(0)
    task["status"] = "active"
    task["session_id"] = session_id

    _save_json(current_path, task)
    _save_json(FUTURE_PATH, future)
    print(f"OK: popped → current/{session_id}.json")
    print(f"  title: {task['title']}")
    print(f"  prompt: {task['prompt']}")


def cmd_complete(session_id, status, memo=None, result=None):
    """Move current/{session_id}.json → past/YYMMDD.json"""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if not current_path.exists():
        print(f"ERROR: no active task for session {session_id}")
        sys.exit(1)

    valid_statuses = ("success", "fail", "postpone", "modified", "discard")
    if status not in valid_statuses:
        print(f"ERROR: status must be one of {valid_statuses}")
        sys.exit(1)

    task = _load_json(current_path)
    task["status"] = status
    if result:
        task["result"] = result
    if memo:
        task["memo"] = memo

    # Append to today's past file
    date_str = datetime.now(_get_tz()).strftime("%y%m%d")
    past_path = PAST_DIR / f"{date_str}.json"
    past = _load_json(past_path, [])
    past.append(task)
    _save_json(past_path, past)

    # Remove from current
    current_path.unlink()
    print(f"OK: {task['title']} → past/{date_str}.json ({status})")

    # If postpone/modified, create new card in future
    if status in ("postpone", "modified"):
        new_task = {
            "id": uuid.uuid4().hex[:12],
            "title": task["title"],
            "prompt": f"[Retry] {task['prompt']}\n\nPrevious result: {task.get('result', 'N/A')}\nMemo: {memo or 'N/A'}",
            "goal": None,
            "approach": None,
            "verification": None,
            "result": None,
            "memo": None,
            "status": "queued",
            "created": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
            "session_id": None,
            "parent_id": task["id"],
        }
        future = _load_json(FUTURE_PATH, [])
        future.append(new_task)
        _save_json(FUTURE_PATH, future)
        print(f"  + new card added to future: {new_task['id']}")


def cmd_create(session_id, title, prompt):
    """Create a task directly in current (skip future queue).
    If a current task already exists, auto-complete it to past first."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if current_path.exists():
        existing = _load_json(current_path)
        existing["status"] = "success"
        if not existing.get("result"):
            existing["result"] = "(auto-completed: replaced by new task)"
        # Move to past
        date_str = datetime.now(_get_tz()).strftime("%y%m%d")
        past_path = PAST_DIR / f"{date_str}.json"
        past = _load_json(past_path, [])
        past.append(existing)
        _save_json(past_path, past)
        current_path.unlink()
        print(f"  → auto-completed previous task: {existing.get('title', '?')}")

    task = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "prompt": prompt,
        "goal": None,
        "approach": None,
        "verification": None,
        "result": None,
        "memo": None,
        "status": "active",
        "created": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
        "session_id": session_id,
        "parent_id": None,
    }
    _save_json(current_path, task)
    print(f"OK: created → current/{session_id}.json")
    print(f"  id: {task['id']}")
    print(f"  title: {title}")


def cmd_add(title, prompt):
    """Add a new task to the back of future queue."""
    future = _load_json(FUTURE_PATH, [])
    task = {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "prompt": prompt,
        "goal": None,
        "approach": None,
        "verification": None,
        "result": None,
        "memo": None,
        "status": "queued",
        "created": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
        "session_id": None,
        "parent_id": None,
    }
    future.append(task)
    _save_json(FUTURE_PATH, future)
    print(f"OK: added to future ({len(future)} total)")
    print(f"  id: {task['id']}")
    print(f"  title: {title}")


def cmd_status():
    """Show current task system state."""
    future = _load_json(FUTURE_PATH, [])
    print(f"Future: {len(future)} tasks")
    for i, t in enumerate(future):
        print(f"  [{i}] {t['title']}")

    print()
    current_files = list(CURRENT_DIR.glob("*.json")) if CURRENT_DIR.exists() else []
    print(f"Current: {len(current_files)} active")
    for f in current_files:
        t = _load_json(f)
        print(f"  {f.stem}: {t.get('title', '?')} ({t.get('status', '?')})")

    print()
    past_files = sorted(PAST_DIR.glob("*.json"), reverse=True) if PAST_DIR.exists() else []
    total_past = sum(len(_load_json(f, [])) for f in past_files)
    print(f"Past: {total_past} tasks across {len(past_files)} days")


def cmd_remove(task_id):
    """Remove a task from future queue by ID."""
    future = _load_json(FUTURE_PATH, [])
    before = len(future)
    future = [t for t in future if t.get("id") != task_id]
    if len(future) == before:
        print(f"ERROR: task {task_id} not found in future queue")
        sys.exit(1)
    _save_json(FUTURE_PATH, future)
    print(f"OK: removed {task_id} from future ({len(future)} remaining)")


def cmd_update_field(session_id, field, value):
    """Update a specific field in current task."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if not current_path.exists():
        print(f"ERROR: no active task for session {session_id}")
        sys.exit(1)

    valid_fields = ("title", "goal", "approach", "verification", "result", "memo")
    if field not in valid_fields:
        print(f"ERROR: field must be one of {valid_fields}")
        sys.exit(1)

    task = _load_json(current_path)
    task[field] = value
    _save_json(current_path, task)
    print(f"OK: {field} updated for {task['title']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "pop" and len(sys.argv) >= 3:
        cmd_pop(sys.argv[2])
    elif cmd == "create" and len(sys.argv) >= 5:
        cmd_create(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "complete" and len(sys.argv) >= 4:
        memo = None
        result = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--memo" and i + 1 < len(sys.argv):
                memo = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--result" and i + 1 < len(sys.argv):
                result = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_complete(sys.argv[2], sys.argv[3], memo=memo, result=result)
    elif cmd == "add" and len(sys.argv) >= 4:
        cmd_add(sys.argv[2], sys.argv[3])
    elif cmd == "status":
        cmd_status()
    elif cmd == "remove" and len(sys.argv) >= 3:
        cmd_remove(sys.argv[2])
    elif cmd == "update" and len(sys.argv) >= 5:
        cmd_update_field(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
