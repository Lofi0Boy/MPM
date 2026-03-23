#!/usr/bin/env python3
"""
MPM Task System CLI — manages task transitions.

Status flow: future → dev → agent-review → human-review → past
File flow:   future.json → current/{session}.json → review/{task_id}.json → past/YYMMDD.json

Usage:
    task.py pop <session_id>              # future → current (status: dev)
    task.py create <session_id> <title> <prompt>  # → current (direct, status: dev)
    task.py complete <task_id> <verdict> [--comment "..."]  # review → past (human only)
    task.py add <title> <prompt> --goal "..." --verification "..." [--goal-id <id>]  # → future
    task.py update <session_id> <field> <value>  # update current task field
    task.py review <session_id> <verdict> --summary "..." [--evidence "..."]  # agent review
    task.py status                        # show current state
    task.py remove <task_id>              # remove from future queue
    task.py rejected                      # list rejected tasks in past
    task.py recycle <task_id> <new_prompt> # rejected past → future with new prompt
"""

import fcntl
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(__file__).parent.parent / "data"
FUTURE_PATH = DATA_DIR / "future.json"
CURRENT_DIR = DATA_DIR / "current"
REVIEW_DIR = DATA_DIR / "review"
PAST_DIR = DATA_DIR / "past"
DOCS_DIR = Path(__file__).parent.parent / "docs"
FEEDBACK_PATH = DOCS_DIR / "FEEDBACK.md"
CONFIG_PATH = Path.home() / ".mpm" / "config.json"

# Canonical task schema — all fields present from creation, progressively filled
TASK_TEMPLATE = {
    "id": None,
    "title": None,
    "prompt": None,
    "goal": None,
    "approach": None,
    "verification": None,
    "result": None,
    "memo": None,
    "status": "future",
    "agent_reviews": [],
    "human_review": None,
    "created": None,
    "session_id": None,
    "parent_goal": None,
}

VALID_STATUSES = ("future", "dev", "agent-review", "human-review", "past")


def _get_tz():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return ZoneInfo(config.get("timezone", "UTC"))
    except Exception:
        return timezone.utc



def _append_feedback(task, verdict, comment=None):
    """Append human review result to FEEDBACK.md."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(_get_tz()).strftime("%Y-%m-%d %H:%M")
    title = task.get("title", "?")
    goal = task.get("goal", "")
    agent_summary = ""
    reviews = task.get("agent_reviews", [])
    if reviews:
        last = reviews[-1]
        agent_summary = f"- Agent review: {last.get('summary', '')}"

    entry = f"""
### [{verdict.upper()}] {title}
- Date: {date_str}
- Goal: {goal}
{f'- Comment: {comment}' if comment else ''}
{agent_summary}
"""
    with open(FEEDBACK_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


LOCK_PATH = DATA_DIR / ".task.lock"


def _lock():
    """Acquire file lock for concurrent access safety."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_PATH, "w")
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    return lock_fd


def _unlock(lock_fd):
    """Release file lock."""
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    lock_fd.close()


def _load_json(path, default=None):
    if not path.exists():
        return default if default is not None else []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _new_task(title, prompt, parent_goal=None):
    """Create a new task dict with all fields present."""
    task = dict(TASK_TEMPLATE)
    task["id"] = uuid.uuid4().hex[:12]
    task["title"] = title
    task["prompt"] = prompt
    task["agent_reviews"] = []
    task["created"] = datetime.now(_get_tz()).strftime("%y%m%d%H%M")
    task["parent_goal"] = parent_goal
    return task


def _move_to_review(task, current_path):
    """Move task from current/ to review/{task_id}.json with status human-review."""
    task["status"] = "human-review"
    review_path = REVIEW_DIR / f"{task['id']}.json"
    _save_json(review_path, task)
    current_path.unlink()
    return review_path


def cmd_pop(session_id):
    """Pop first task from future → current/{session_id}.json (status: dev)"""
    lock = _lock()
    try:
        future = _load_json(FUTURE_PATH, [])
        if not future:
            print("ERROR: future queue is empty.")
            sys.exit(1)

        current_path = CURRENT_DIR / f"{session_id}.json"
        if current_path.exists():
            existing = _load_json(current_path)
            print(f"ERROR: session already has task: {existing.get('title', '?')}")
            sys.exit(1)

        task = future.pop(0)
        task["status"] = "dev"
        task["session_id"] = session_id

        _save_json(current_path, task)
        _save_json(FUTURE_PATH, future)
    finally:
        _unlock(lock)
    print(f"OK: popped → current/{session_id}.json")
    print(f"  title: {task['title']}")
    print(f"  prompt: {task['prompt']}")


def cmd_complete(task_id, verdict, comment=None):
    """Move review/{task_id}.json → past (human only)."""
    review_path = REVIEW_DIR / f"{task_id}.json"
    if not review_path.exists():
        print(f"ERROR: no task in review with id {task_id}")
        sys.exit(1)

    task = _load_json(review_path)

    if task["status"] != "human-review":
        print(f"ERROR: task status is '{task['status']}', must be 'human-review' to complete")
        sys.exit(1)

    valid_verdicts = ("success", "rejected", "discard")
    if verdict not in valid_verdicts:
        print(f"ERROR: verdict must be one of {valid_verdicts}")
        sys.exit(1)

    lock = _lock()
    try:
        task["human_review"] = {
            "verdict": verdict,
            "comment": comment or "",
            "at": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
        }
        task["status"] = "past"

        # Append to today's past file
        date_str = datetime.now(_get_tz()).strftime("%y%m%d")
        past_path = PAST_DIR / f"{date_str}.json"
        past = _load_json(past_path, [])
        past.append(task)
        _save_json(past_path, past)

        # Append to FEEDBACK.md
        _append_feedback(task, verdict, comment)

        # Remove from review
        review_path.unlink()
    finally:
        _unlock(lock)
    print(f"OK: {task['title']} → past/{date_str}.json ({verdict})")


def cmd_create(session_id, title, prompt):
    """Create a task directly in current (skip future queue)."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if current_path.exists():
        existing = _load_json(current_path)
        # Only allow replacing dev-status tasks
        if existing.get("status") not in ("dev", None):
            print(f"ERROR: current task is in '{existing.get('status')}' status, cannot replace")
            sys.exit(1)
        # Move existing to review as discard
        existing["human_review"] = {
            "verdict": "discard",
            "comment": "auto-replaced by new task",
            "at": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
        }
        existing["status"] = "past"
        date_str = datetime.now(_get_tz()).strftime("%y%m%d")
        past_path = PAST_DIR / f"{date_str}.json"
        past = _load_json(past_path, [])
        past.append(existing)
        _save_json(past_path, past)
        current_path.unlink()
        print(f"  → auto-discarded previous task: {existing.get('title', '?')}")

    task = _new_task(title, prompt)
    task["status"] = "dev"
    task["session_id"] = session_id

    _save_json(current_path, task)
    print(f"OK: created → current/{session_id}.json")
    print(f"  id: {task['id']}")
    print(f"  title: {title}")


def cmd_add(title, prompt, goal_id=None, goal=None, verification=None):
    """Add a new task to the back of future queue."""
    lock = _lock()
    try:
        future = _load_json(FUTURE_PATH, [])
        task = _new_task(title, prompt, parent_goal=goal_id)
        if goal:
            task["goal"] = goal
        if verification:
            task["verification"] = verification
        future.append(task)
        _save_json(FUTURE_PATH, future)
    finally:
        _unlock(lock)
    print(f"OK: added to future ({len(future)} total)")
    print(f"  id: {task['id']}")
    print(f"  title: {title}")


def cmd_review(session_id, verdict, summary=None, evidence=None):
    """Add an agent review entry to the current task."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if not current_path.exists():
        print(f"ERROR: no task for session {session_id}")
        sys.exit(1)

    task = _load_json(current_path)

    if task["status"] != "agent-review":
        print(f"ERROR: task status is '{task['status']}', must be 'agent-review' to review")
        sys.exit(1)

    valid_verdicts = ("pass", "fail", "needs-input", "modified")
    if verdict not in valid_verdicts:
        print(f"ERROR: review verdict must be one of {valid_verdicts}")
        sys.exit(1)

    review_entry = {
        "verdict": verdict,
        "summary": summary or "",
        "evidence": evidence or "",
        "at": datetime.now(_get_tz()).strftime("%y%m%d%H%M"),
    }
    task["agent_reviews"].append(review_entry)

    if verdict in ("pass", "needs-input", "modified"):
        # Move to review/ — dev is free to pick up next task
        review_path = _move_to_review(task, current_path)
        print(f"OK: review added ({verdict}) for {task['title']}")
        print(f"  → task moved to review/{task['id']}.json (human-review)")
    elif verdict == "fail":
        task["status"] = "dev"
        _save_json(current_path, task)
        print(f"OK: review added ({verdict}) for {task['title']}")
        print(f"  → task returned to dev")


def cmd_escalate(session_id):
    """Escalate task from agent-review to human-review (used by hook after 3x fail)."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if not current_path.exists():
        print(f"ERROR: no task for session {session_id}")
        sys.exit(1)

    task = _load_json(current_path)
    if task["status"] != "agent-review":
        print(f"ERROR: task status is '{task['status']}', must be 'agent-review' to escalate")
        sys.exit(1)

    review_path = _move_to_review(task, current_path)
    print(f"OK: {task['title']} escalated to review/{task['id']}.json (human-review)")



def cmd_rejected():
    """List rejected tasks in past that haven't been recycled."""
    past_files = sorted(PAST_DIR.glob('*.json'), reverse=True) if PAST_DIR.exists() else []
    found = []
    for pf in past_files:
        tasks = _load_json(pf, [])
        for t in tasks:
            hr = t.get('human_review') or {}
            if hr.get('verdict') == 'rejected':
                found.append(t)
    if not found:
        print('No rejected tasks found in past.')
        return
    print(f'Rejected tasks: {len(found)}')
    for t in found:
        hr = t.get('human_review', {})
        print(f"  {t['id']}: {t['title']}")
        print(f"    rejected at: {hr.get('at', '?')}")
        print(f"    comment: {hr.get('comment', '(none)')}")
        print()


def cmd_recycle(task_id, new_prompt):
    """Move a rejected task from past back to future with a new prompt.
    Preserves history in prompt, clears work fields for fresh start."""
    lock = _lock()
    try:
        # Find task in past files
        past_files = sorted(PAST_DIR.glob('*.json'), reverse=True) if PAST_DIR.exists() else []
        found_task = None
        found_past_path = None
        for pf in past_files:
            tasks = _load_json(pf, [])
            for i, t in enumerate(tasks):
                if t.get('id') == task_id:
                    hr = t.get('human_review') or {}
                    if hr.get('verdict') != 'rejected':
                        print(f"ERROR: task {task_id} is not rejected (verdict: {hr.get('verdict', '?')})")
                        sys.exit(1)
                    found_task = t
                    found_past_path = pf
                    # Remove from past
                    tasks.pop(i)
                    if tasks:
                        _save_json(pf, tasks)
                    else:
                        pf.unlink()
                    break
            if found_task:
                break

        if not found_task:
            print(f'ERROR: rejected task {task_id} not found in past')
            sys.exit(1)

        # Create fresh task with new prompt, preserving parent_goal + goal + verification
        new_task = _new_task(
            found_task['title'],
            new_prompt,
            parent_goal=found_task.get('parent_goal'),
        )
        # Preserve planner-set fields from the original task
        if found_task.get('goal'):
            new_task['goal'] = found_task['goal']
        if found_task.get('verification'):
            new_task['verification'] = found_task['verification']

        future = _load_json(FUTURE_PATH, [])
        future.append(new_task)
        _save_json(FUTURE_PATH, future)
    finally:
        _unlock(lock)
    print(f"OK: recycled {task_id} → future ({len(future)} total)")
    print(f"  new id: {new_task['id']}")
    print(f"  title: {new_task['title']}")


def cmd_status():
    """Show current task system state."""
    future = _load_json(FUTURE_PATH, [])
    print(f"Future: {len(future)} tasks")
    for i, t in enumerate(future):
        goal = f" (goal: {t['parent_goal']})" if t.get('parent_goal') else ""
        print(f"  [{i}] {t['title']}{goal}")

    print()
    current_files = list(CURRENT_DIR.glob("*.json")) if CURRENT_DIR.exists() else []
    print(f"Current: {len(current_files)} tasks")
    for f in current_files:
        t = _load_json(f)
        status = t.get('status', '?')
        reviews = t.get('agent_reviews', [])
        review_info = f" [{len(reviews)} reviews]" if reviews else ""
        print(f"  {f.stem}: {t.get('title', '?')} ({status}){review_info}")

    print()
    review_files = list(REVIEW_DIR.glob("*.json")) if REVIEW_DIR.exists() else []
    print(f"Review: {len(review_files)} tasks")
    for f in review_files:
        t = _load_json(f)
        last_review = (t.get('agent_reviews') or [{}])[-1]
        verdict = last_review.get('verdict', '?')
        print(f"  {t.get('id', '?')}: {t.get('title', '?')} (agent: {verdict})")

    print()
    past_files = sorted(PAST_DIR.glob("*.json"), reverse=True) if PAST_DIR.exists() else []
    total_past = sum(len(_load_json(f, [])) for f in past_files)
    print(f"Past: {total_past} tasks across {len(past_files)} days")


def cmd_remove(task_id):
    """Remove a task from future queue by ID."""
    lock = _lock()
    try:
        future = _load_json(FUTURE_PATH, [])
        before = len(future)
        future = [t for t in future if t.get("id") != task_id]
        if len(future) == before:
            print(f"ERROR: task {task_id} not found in future queue")
            sys.exit(1)
        _save_json(FUTURE_PATH, future)
    finally:
        _unlock(lock)
    print(f"OK: removed {task_id} from future ({len(future)} remaining)")


def cmd_update_field(session_id, field, value):
    """Update a specific field in current task."""
    current_path = CURRENT_DIR / f"{session_id}.json"
    if not current_path.exists():
        print(f"ERROR: no task for session {session_id}")
        sys.exit(1)

    valid_fields = ("title", "goal", "approach", "verification", "result", "memo")  # goal/verification set by planner at creation, dev can override if needed
    if field not in valid_fields:
        print(f"ERROR: field must be one of {valid_fields}")
        sys.exit(1)

    task = _load_json(current_path)
    task[field] = value

    # When result is filled, auto-transition to agent-review
    if field == "result" and value and task["status"] == "dev":
        task["status"] = "agent-review"
        print(f"  → status: dev → agent-review")

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
        comment = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--comment" and i + 1 < len(sys.argv):
                comment = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_complete(sys.argv[2], sys.argv[3], comment=comment)
    elif cmd == "add" and len(sys.argv) >= 4:
        goal_id = None
        goal = None
        verification = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--goal-id" and i + 1 < len(sys.argv):
                goal_id = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--goal" and i + 1 < len(sys.argv):
                goal = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--verification" and i + 1 < len(sys.argv):
                verification = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_add(sys.argv[2], sys.argv[3], goal_id=goal_id, goal=goal, verification=verification)
    elif cmd == "review" and len(sys.argv) >= 4:
        summary = None
        evidence = None
        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--summary" and i + 1 < len(sys.argv):
                summary = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--evidence" and i + 1 < len(sys.argv):
                evidence = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        cmd_review(sys.argv[2], sys.argv[3], summary=summary, evidence=evidence)
    elif cmd == "escalate" and len(sys.argv) >= 3:
        cmd_escalate(sys.argv[2])
    elif cmd == "rejected":
        cmd_rejected()
    elif cmd == "recycle" and len(sys.argv) >= 4:
        cmd_recycle(sys.argv[2], sys.argv[3])
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
