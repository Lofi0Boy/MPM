# MPM — Multi Project Manager

MpmWorkspace의 모든 프로젝트를 관리하기 위한 대시보드 및 오케스트레이션 시스템.

## 목적

여러 AI 코딩 에이전트(Claude Code)를 병렬로 운영할 때, 인간이 컨텍스트를 유지하기 어려운 문제를 해결한다. 각 프로젝트의 진행 상황, 태스크 상태, 에이전트 출력을 하나의 대시보드에서 실시간으로 모니터링하고 제어한다.

## 현재 상태

- 웹 대시보드 (핸드오프/ROADMAP 파싱, 포스트잇, 멀티컬럼 뷰) 완성
- tmux 기반 터미널 뷰 (실시간 CLI 출력, 팝아웃) 완성
- 태스크 시스템 v2 설계 완료, 구현 진행 중

## Phases

### Phase1 - PM 워크플로우 구축 [active] [60%]
PM/Developer/Reviewer 3-tier 워크플로우 구현 및 대시보드 UI 완성
- Phase/PM/Reviewer 시스템 구현
- 대시보드에 Phase 진행률 표시
- Dev/PM 분할 터미널

### Phase2 - 배포 및 패키징 [0%]
pip install로 설치 가능한 상태로 패키징
- README 작성
- PyPI 배포
- CLI 설치 가이드