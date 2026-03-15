# MPM — 아키텍처

---

## 1. 시스템 개요

MPM은 관리 대상 프로젝트마다 하나씩 여러 Claude Code CLI 세션을 오케스트레이션하는 Python 데몬입니다. MpmWorkspace 전체의 컨트롤 플레인 역할을 합니다.

```
사용자
  ↕ (CLI / 웹 대시보드 / Telegram)
[MPM 데몬]
  ↕ (stdin/stdout, --resume 세션)
[PM 에이전트 — Claude Code, cwd: MpmWorkspace/]
  ↕ (생성/통신)
[서브 프로젝트 에이전트 — Claude Code, cwd: ./project/]
  ↕ (로컬 파일 시스템)
[프로젝트 파일, git, 로그]
```

---

## 2. 디렉토리 구조

```
MPM/
├── README.md
├── CLAUDE.md
├── docs/
│   ├── ARCHITECTURE.md         # 이 문서
│   ├── ROADMAP.md
│   └── handoff/
├── daemon/                     # 핵심 오케스트레이션 프로세스
│   ├── main.py                 # 진입점
│   ├── orchestrator.py         # 서브 에이전트 라이프사이클 관리
│   ├── verifier.py             # 작업 결과 검증
│   └── state.py                # 인메모리 + 디스크 상태 저장소
├── data/
│   └── ideas.json              # 포스트잇 노트 저장소 (위치, 색상, 프로젝트)
├── dashboard/                  # 웹 UI
│   ├── server.py               # Flask 서버 — 프로젝트 + 아이디어 API
│   ├── projects.py             # ROADMAP/핸드오프 파서
│   └── templates/index.html    # 보드 UI + 포스트잇 노트 오버레이
└── gateway/                    # I/O 멀티플렉서
    ├── telegram.py             # Telegram 브릿지
    └── multiplexer.py          # CLI I/O를 채널로 라우팅
```

---

## 3. 에이전트 세션 모델

### 프로젝트당 하나의 세션
각 관리 대상 프로젝트는 정확히 하나의 Claude Code CLI 세션을 가지며, 데몬 시작 시 생성되어 유지됩니다.

```python
sessions = {
    "saksak-kimchi": ClaudeSession(cwd="./saksak-kimchi", session_id="..."),
    "JHomelab_server": ClaudeSession(cwd="./JHomelab_server", session_id="..."),
    "JHomelab_app": ClaudeSession(cwd="./JHomelab_app", session_id="..."),
}
```

### 세션 라이프사이클
```
데몬 시작
  → claude 생성 (cwd: project/)    ← CLAUDE.md + docs 읽기 (최초 1회)
  → --resume 를 통해 작업 수행
  → 컨텍스트 압축 트리거
      → 핸드오프 자동 작성 (CLAUDE.md 규칙에 따라)
      → 세션 종료
      → 새 세션 생성          ← 핸드오프 읽기, 컨텍스트 이어받기
  → 계속
```

컨텍스트 압축이 자연스러운 세션 리셋 트리거입니다. 별도의 타이머나 카운터가 필요하지 않습니다 — Claude Code 자체의 압축 이벤트가 사이클을 구동합니다.

---

## 4. PM 에이전트

PM 에이전트도 Claude Code CLI 세션으로, `cwd: MpmWorkspace/`에서 실행됩니다. 모든 프로젝트 파일과 문서에 접근할 수 있습니다.

역할:
- 모든 프로젝트의 ROADMAP.md를 읽어 다음 작업 결정
- 어떤 서브 프로젝트 에이전트를 어떤 지시로 생성할지 결정
- 서브 에이전트 결과를 평가하고 다음 행동 결정
- 결과가 명확할 때 핸드오프 작성 및 ROADMAP.md 자율 업데이트
- 사용자 입력이 필요할 때 에스컬레이션

PM 에이전트가 항상 호출되는 것은 아닙니다 — Python 데몬이 상태를 관리합니다. PM 에이전트는 판단이 필요할 때(작업 계획, 결과 평가, 에스컬레이션 결정) 참조됩니다.

---

## 5. 병렬 서브 에이전트 실행

서브 프로젝트 에이전트는 병렬로 실행됩니다. 데몬은 완료되는 대로 처리합니다.

```python
async def orchestrate(tasks: dict[str, str]):
    futures = {
        project: asyncio.create_task(session.send(task))
        for project, task in tasks.items()
    }
    for coro in asyncio.as_completed(futures.values()):
        project, result = await coro
        await evaluate_and_dispatch(project, result)
```

`evaluate_and_dispatch`:
- 명확한 성공 → ROADMAP/핸드오프 자율 업데이트 → 다음 작업 큐잉
- 모호함 → PM 에이전트에 판단 에스컬레이션
- 사용자 입력 필요 → 설정된 채널로 알림

---

## 6. 작업 결과 검증

검증 방법은 작업 유형에 따라 다릅니다:

| 작업 유형 | 검증 방법 |
|-----------|-------------------|
| 코드 변경 | `git log`, `git diff`, 테스트 실행 출력 |
| API 통합 | 실시간 API 호출 + 응답 로그 |
| UI 변경 | 헤드리스 Chrome 스크린샷 (Playwright) |
| 서비스 실행 | 헬스 체크 엔드포인트, 로그 테일 |
| 빌드 | 종료 코드 + stdout 파싱 |

---

## 7. 사용자 커뮤니케이션 채널

CLI가 단일 정보 소스입니다. 다른 채널은 CLI 위에 뷰 또는 I/O 브릿지 역할을 합니다.

```
Claude CLI stdout
      ↓
[I/O 멀티플렉서]
  ↙              ↘
웹 대시보드      Telegram 브릿지
(출력 렌더링)    (출력 → Telegram 메시지)
                 (Telegram 답장 → stdin 주입)
```

채널 라우팅:
- Telegram 토글 (사용자 설정에 따라 on/off)
- 웹 대시보드 항상 활성 (모든 CLI 출력 렌더링)
- Telegram 브릿지는 토글 on일 때만 활성

---

## 8. 상태 관리

Python 데몬이 모든 런타임 상태를 소유합니다. 상태는 메모리에 유지되고 충돌 복구를 위해 디스크에 저장됩니다.

```python
@dataclass
class DaemonState:
    sessions: dict[str, SessionInfo]     # 프로젝트별 세션 ID 및 상태
    running_tasks: dict[str, TaskInfo]   # 프로젝트별 활성 작업
    pending: list[PendingDecision]       # 사용자 입력 대기 항목
```

모든 상태 변경 시 `daemon/state.json`에 저장됩니다.
