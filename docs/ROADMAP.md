# ROADMAP

## Overview
MpmWorkspace를 위한 오케스트레이션 시스템. Phase 1(읽기 전용 대시보드)은 완료. 현재 **Phase 2** — Gateway + 비서 Agent.

---

## Phase 1: 대시보드

Goal: 각 프로젝트의 핸드오프 파일과 ROADMAP을 읽어 모든 프로젝트를 실시간 스레드 스타일 진행 뷰로 나란히 표시하는 웹 대시보드. 읽기 전용 — 아직 에이전트 제어 없음.

- [x] 프로젝트 스캐폴드 (디렉토리 구조, CLAUDE.md, git init)
- [x] 프로젝트별 핸드오프 파일 및 ROADMAP.md 파싱
- [x] 멀티 컬럼 스레드 뷰 (프로젝트당 하나의 컬럼)
- [x] 자동 새로고침 (핸드오프 디렉토리의 새 파일 폴링)
- [x] 기본 웹 서버 (`dashboard/server.py`)
- [x] 포스트잇 노트 — 드래그 가능 아이디어 메모, 프로젝트 소속 감지, 색상 테마

---

## Phase 2: Gateway + 비서 Agent

Goal: tmux 기반 I/O 게이트웨이. 프로젝트별 AI 코딩 CLI 세션의 실시간 출력을 대시보드에서 보고, 명령을 보낼 수 있는 구조. CLI 종류에 비종속 (Claude Code, Codex, OpenCode 등). Telegram 브릿지. 전체 프로젝트 문서를 가진 비서 Agent와 대시보드 안에서 대화.

- [x] tmux 세션 관리 — 프로젝트별 세션 생성/감지, CLI 프로세스 패턴 매칭
- [x] `gateway/multiplexer.py` — tmux capture-pane 폴링 + WebSocket으로 대시보드 전달
- [x] 대시보드 실시간 터미널 뷰 — 프로젝트별 CLI 출력 스트리밍 + 명령 입력
- [ ] 키보드 조작 UX — 키보드만으로 모든 기능 이용 가능
- [ ] 터미널 활성 프로젝트 시각 효과
- [ ] Agent 상태 표시 — 응답 중 / 응답 완료 / 유휴 / 꺼짐 구분, 컬럼 헤더에 상태 인디케이터
- [ ] 응답 완료 인터랙션 — 완료 시 대시보드에서 바로 후속 명령 입력 가능
- [ ] 비서 Agent — `cwd: MpmWorkspace/`의 tmux 세션, 전체 프로젝트 문서 컨텍스트로 대시보드 내 채팅
- [ ] `gateway/telegram.py` — 출력을 Telegram으로 전달, 답장을 tmux send-keys로 주입
- [ ] Telegram 토글 설정

---

## Phase 3: TBD

Goal: 추후 논의

---

## External Connections

**MpmWorkspace** 내 `saksak-kimchi`, `JHomelab_server`, `JHomelab_app`과 함께 위치.
MPM은 이 프로젝트들의 핸드오프, ROADMAP을 읽지만, 해당 프로젝트의 Claude Code 세션을 통해서만 파일을 수정합니다.
