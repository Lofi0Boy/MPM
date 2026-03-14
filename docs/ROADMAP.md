# ROADMAP

## Overview
Orchestration system for MpmWorkspace. Phase 1 focuses on a read-only dashboard that visualizes all project progress and next tasks in a single view. Autonomous agent control and communication gateways come in later phases. Currently in **Phase 1**.

---

## Phase 1: Dashboard

Goal: Web dashboard that reads each project's handoff files and ROADMAP, and displays all projects side-by-side as a live thread-style progress view. Read-only — no agent control yet.

**Layout concept:** One column per project. Each column shows the ROADMAP phase progress and recent handoff entries as a flowing thread (newest at top). At a glance, the user can see where every project stands and what comes next.

- [x] Project scaffold (directory structure, CLAUDE.md, git init)
- [x] Parse handoff files and ROADMAP.md per project
- [x] Multi-column thread view (one column per project)
  - ROADMAP phase + completion status at top
  - Handoff entries as scrollable thread below
  - "Next tasks" (unchecked ROADMAP items) highlighted
- [x] Auto-refresh (poll handoff directory for new files)
- [x] Basic web server (`dashboard/server.py`)

---

## Phase 2: MPM Agent (Autonomous Control)

Goal: MPM daemon spawns and manages Claude Code CLI sessions per project. PM Agent reads ROADMAPs and handoffs, determines next tasks, dispatches to sub-agents, and verifies results — autonomously where possible, escalating to user when needed.

- [ ] `daemon/orchestrator.py` — spawn Claude Code CLI sessions, maintain per-project session IDs
- [ ] `daemon/state.py` — in-memory + disk state store (crash recovery)
- [ ] Parallel task execution (`asyncio.as_completed`)
- [ ] Session reset on compaction event (detect → write handoff → respawn)
- [ ] `daemon/verifier.py` — git log / test run / health check / screenshot verification
- [ ] PM Agent loop — reads ROADMAPs, assigns tasks, evaluates results, updates docs

---

## Phase 3: Gateway (I/O Multiplexer)

Goal: CLI is the base I/O layer. Dashboard renders it live. Telegram bridges it as a toggle.

- [ ] `gateway/multiplexer.py` — route Claude CLI stdout to registered channels
- [ ] Dashboard upgraded to show live agent output (not just static handoff files)
- [ ] `gateway/telegram.py` — forward output to Telegram; inject replies as stdin
- [ ] Telegram toggle setting
- [ ] Pending decisions queue — items awaiting user input surfaced in dashboard + Telegram

---

## External Connections

Part of the **MpmWorkspace** alongside `saksak-kimchi`, `JHomelab_server`, `JHomelab_app`.
MPM reads from these projects (handoffs, ROADMAPs) but does not modify their files except through their own Claude Code sessions.
