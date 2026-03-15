# ROADMAP

## 개요
MpmWorkspace를 위한 오케스트레이션 시스템. Phase 1(읽기 전용 대시보드)은 완료. 현재 **Phase 2** — Claude Code CLI 세션을 통한 자율 에이전트 제어 진행 중.

---

## Phase 1: 대시보드

목표: 각 프로젝트의 핸드오프 파일과 ROADMAP을 읽어 모든 프로젝트를 실시간 스레드 스타일 진행 뷰로 나란히 표시하는 웹 대시보드. 읽기 전용 — 아직 에이전트 제어 없음.

**레이아웃 컨셉:** 프로젝트당 하나의 컬럼. 각 컬럼은 ROADMAP Phase 진행 상황과 최근 핸드오프 항목을 흐르는 스레드 형태로 보여줌 (최신이 상단). 한눈에 모든 프로젝트의 현재 위치와 다음 할 일을 파악 가능.

- [x] 프로젝트 스캐폴드 (디렉토리 구조, CLAUDE.md, git init)
- [x] 프로젝트별 핸드오프 파일 및 ROADMAP.md 파싱
- [x] 멀티 컬럼 스레드 뷰 (프로젝트당 하나의 컬럼)
  - 상단에 ROADMAP Phase + 완료 상태
  - 아래에 스크롤 가능한 핸드오프 항목 스레드
  - "다음 작업" (미체크 ROADMAP 항목) 강조 표시
- [x] 자동 새로고침 (핸드오프 디렉토리의 새 파일 폴링)
- [x] 기본 웹 서버 (`dashboard/server.py`)
- [x] 포스트잇 노트 — 프로젝트 소속 감지, 색상 테마, `data/ideas.json` 영구 저장이 가능한 드래그 가능 아이디어 메모

---

## Phase 2: MPM 에이전트 (자율 제어)

목표: MPM 데몬이 프로젝트별 Claude Code CLI 세션을 생성하고 관리. PM 에이전트가 ROADMAP과 핸드오프를 읽고, 다음 작업을 결정하고, 서브 에이전트에 배분하고, 결과를 검증 — 가능한 한 자율적으로, 필요시 사용자에게 에스컬레이션.

- [ ] `daemon/orchestrator.py` — Claude Code CLI 세션 생성, 프로젝트별 세션 ID 유지
- [ ] `daemon/state.py` — 인메모리 + 디스크 상태 저장소 (충돌 복구)
- [ ] 병렬 작업 실행 (`asyncio.as_completed`)
- [ ] 압축 이벤트 시 세션 리셋 (감지 → 핸드오프 작성 → 재생성)
- [ ] `daemon/verifier.py` — git log / 테스트 실행 / 헬스 체크 / 스크린샷 검증
- [ ] PM 에이전트 루프 — ROADMAP 읽기, 작업 할당, 결과 평가, 문서 업데이트

---

## Phase 3: 게이트웨이 (I/O 멀티플렉서)

목표: CLI가 기본 I/O 레이어. 대시보드가 실시간으로 렌더링. Telegram이 토글로 브릿지.

- [ ] `gateway/multiplexer.py` — Claude CLI stdout를 등록된 채널로 라우팅
- [ ] 대시보드를 실시간 에이전트 출력 표시로 업그레이드 (정적 핸드오프 파일이 아닌)
- [ ] `gateway/telegram.py` — 출력을 Telegram으로 전달; 답장을 stdin으로 주입
- [ ] Telegram 토글 설정
- [ ] 보류 중 결정 큐 — 사용자 입력 대기 항목을 대시보드 + Telegram에 표시

---

## 외부 연결

**MpmWorkspace** 내 `saksak-kimchi`, `JHomelab_server`, `JHomelab_app`과 함께 위치.
MPM은 이 프로젝트들의 핸드오프, ROADMAP을 읽지만, 해당 프로젝트의 Claude Code 세션을 통해서만 파일을 수정합니다.
