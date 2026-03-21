# Verification Methods

This document records how to verify changes in this project.
Both PLANNER (when writing Task verification) and REVIEWER (when running checks) reference this.

## API

- Server port: 5100
- `curl -s localhost:5100/api/projects | jq .`
- `curl -s localhost:5100/api/sessions | jq .`
- `curl -s localhost:5100/api/v2/future/<project> | jq .`

## UI

- Open `localhost:5100` in Chrome and take screenshot
- Key areas to check: project header, phase display, task cards, terminal panel
- Use Claude in Chrome for interactive UI verification

## Data

- `python3 .mpm/scripts/task.py status`
- `python3 .mpm/scripts/phase.py status`
- Inspect `.mpm/data/` JSON files directly

## Scripts

- `python3 .mpm/scripts/phase.py status` — phase/goal hierarchy and progress
- `python3 .mpm/scripts/task.py status` — task queue state

## User-specified methods

(Accumulated from user conversations — add entries as the user specifies new verification approaches)
