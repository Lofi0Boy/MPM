# MPM — 멀티 프로젝트 매니저

MpmWorkspace의 모든 프로젝트를 관리하기 위한 대시보드 및 오케스트레이션 시스템.

Phase 1은 읽기 전용 웹 대시보드로, 각 프로젝트의 핸드오프 파일과 ROADMAP을 읽어 멀티 컬럼 스레드 뷰에 표시합니다 — 프로젝트당 하나의 컬럼으로 진행 상황과 다음 작업을 한눈에 보여줍니다.

이후 Phase에서는 자율 에이전트 제어(MPM 데몬이 프로젝트별 Claude Code 세션을 생성)와 커뮤니케이션 게이트웨이(Telegram, 실시간 CLI 출력)가 추가됩니다.

---

## 대시보드 (Phase 1)

```
┌─────────────────┬─────────────────┬─────────────────┐
│  saksak-kimchi  │ JHomelab_server │  JHomelab_app   │
│                 │                 │                 │
│ Phase 1 ██░░░░  │ Phase 1 ██████  │ Phase 1 ██████  │
│ 11/16 done      │ complete ✓      │ complete ✓      │
│                 │                 │                 │
│ Next:           │                 │                 │
│ · Live test run │                 │                 │
│ · Return coin   │                 │                 │
│   selector      │                 │                 │
│                 │                 │                 │
│ ── handoff ──   │                 │                 │
│ 26/03/13        │ 26/03/13        │ 26/03/13        │
│ Doc restructure │ Scripts reorg   │ Doc restructure │
│ ...             │ ...             │ ...             │
└─────────────────┴─────────────────┴─────────────────┘
```

---

## 아키텍처 개요

```
[MPM 데몬 — Python 프로세스, 상시 실행]              ← Phase 2
  ├── 프로젝트별 Claude Code 세션 (프로젝트당 하나, 영구)
  ├── 비동기 오케스트레이션 (병렬 서브 에이전트, as_completed)
  ├── 결과 검증 엔진
  ├── ROADMAP + 핸드오프 자동 업데이트
  └── I/O 멀티플렉서                                 ← Phase 3
        ├── 웹 대시보드 (CLI 출력 렌더링)
        └── Telegram 브릿지 (토글 on/off)
```

---

## 관리 대상 프로젝트

| 프로젝트 | 설명 |
|---------|-------------|
| `saksak-kimchi` | 김치 프리미엄 차익거래 봇 |
| `JHomelab_server` | 홈 서버 백엔드 |
| `JHomelab_app` | 홈 랩 Android/웹 앱 |

---

## 구성 요소

| 디렉토리 | Phase | 역할 |
|-----------|-------|------|
| `dashboard/` | 1 | 웹 UI — 읽기 전용 프로젝트 상태 뷰 |
| `daemon/` | 2 | 핵심 오케스트레이션 프로세스 |
| `gateway/` | 3 | I/O 멀티플렉서 (CLI / Telegram 브릿지) |

---

## 주요 설계 결정

| 결정 사항 | 선택 | 이유 |
|----------|--------|--------|
| 에이전트 실행 | Claude Code CLI (`--resume`) | 완전한 로컬 파일 제어, 도구 재구현 불필요 |
| 세션 모델 | 프로젝트당 하나의 영구 세션 | 반복적인 문서 로딩 방지; 압축 시 핸드오프 + 세션 리셋 트리거 |
| PM 에이전트 | Claude Code CLI (cwd: MpmWorkspace/) | 모든 프로젝트 파일에 접근 필요 |
| 상태 관리 | Python 데몬이 상태 보유 | Claude API 호출은 무상태; 데몬이 연속성 제공 |
| 사용자 커뮤니케이션 | CLI가 기본; 대시보드가 출력 렌더링; Telegram이 I/O 브릿지 | 단일 정보 소스, 채널 무관 |
| 병렬 실행 | `asyncio.as_completed` | 서브 에이전트 완료를 순차가 아닌 도착 순으로 처리 |
