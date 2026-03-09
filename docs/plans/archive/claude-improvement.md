# Claude Code 설정 개선 태스크

> 근거: `Bizi_Claude_Code_improvement.md` 분석 결과
> 완료일: 2026-02-26

## 진행 상황

- [x] **Step 1** — agents/ 모델 최적화 + rules/agents.md 삭제
- [x] **Step 2** — rules/patterns.md, testing.md → skills/ 이전 + git-workflow.md 축약
- [x] **Step 3** — rules/coding-style.md, security.md, performance.md 축약
- [x] **Step 4** — commit-lint.sh 훅 추가
- [x] **Step 5** — CLAUDE.md 정리

**전체 완료 ✅**

---

## 최종 결과 요약

| 항목 | 개선 전 | 개선 후 | 변화 |
|------|--------|--------|------|
| CLAUDE.md | 239줄 | 153줄 | -36% |
| rules/ 총 줄 수 | 998줄 (7개) | 140줄 (4개) | -86% |
| skills/ | 6개 | 8개 | +code-patterns, +test-guide |
| hooks/ | 4개 | 5개 | +commit-lint.sh |
| agents/ opus 사용 | 7개 전부 | 3개만 | 4개 → sonnet |
| 매 세션 고정 토큰 (추정) | ~3,500+ | ~600 | -83% |

---

## Step 1 — agents/ 모델 최적화 + rules/agents.md 삭제

### agents/ 모델 변경 (opus → sonnet)
| 에이전트 | 변경 전 | 변경 후 | 이유 |
|---------|--------|--------|------|
| code-reviewer | opus | sonnet | 체크리스트 기반 절차적 작업 |
| docker-tester | opus | sonnet | 절차적 빌드/테스트 |
| react-form-architect | opus | sonnet | Skills 보일러플레이트 보완 |
| tdd-guide | opus | sonnet | Red-Green-Refactor 절차적 |
| pm-orchestrator | opus | opus 유지 | 복합 판단, 최상위 조율 |
| fastapi-architect | opus | opus 유지 | 아키텍처 판단 필요 |
| rag-specialist | opus | opus 유지 | 복잡한 파이프라인 설계 |

### rules/ 정리
| 파일 | 조치 | 이유 |
|------|------|------|
| rules/agents.md | 삭제 | agents/ 폴더와 100% 중복 (48줄 제거) |

---

## Step 2 — skills/ 이전 + git-workflow.md 축약

| 파일 | 조치 | 결과 |
|------|------|------|
| rules/patterns.md (150줄) | → skills/code-patterns/SKILL.md | 삭제 |
| rules/testing.md (236줄) | → skills/test-guide/SKILL.md (pytest-suite 중복 제거) | 삭제 |
| rules/git-workflow.md (208줄) | 핵심만 축약 | 24줄 |

---

## Step 3 — rules/ 3개 파일 축약

| 파일 | 전 | 후 | 제거 내용 |
|------|----|----|-----------|
| coding-style.md | 163줄 | 53줄 | docstring 예시, 포맷팅 규칙 (린터 처리) |
| security.md | 157줄 | 39줄 | 파일 업로드, 의존성 감사, 긴 예시 |
| performance.md | 36줄 | 24줄 | Model Selection 표 (agents/ model로 대체) |

---

## Step 4 — commit-lint.sh 훅 추가

- `.claude/hooks/commit-lint.sh` 신규 생성 (실행 권한 포함)
- `settings.json` PostToolUse Bash 훅에 등록
- 동작: `git commit` 성공 시 `[feat|fix|docs|...]` 접두사 확인 → 미준수 시 경고 출력 (차단 없음)

---

## Step 5 — CLAUDE.md 정리

| 조치 | 내용 |
|------|------|
| 239줄 → 153줄 | -36% |
| 프로젝트 구조 트리 축약 | 75줄 → 9줄 (서브디렉토리 상세 제거) |
| 개발 컨벤션 섹션 업데이트 | 현재 rules/ 4개 + skills/ 2개 구조로 정확히 반영 |
| 핵심 정보 유지 | 기술 스택, 포트, 아키텍처 다이어그램, RAG 환경변수 테이블 |

---

## 현재 .claude/ 구조

```
.claude/
├── settings.json
├── settings.local.json
├── agents/    (7개 — pm/fastapi/rag: opus, 나머지 4개: sonnet)
├── commands/  (9개 — 변경 없음)
├── hooks/     (5개 — commit-lint.sh 추가)
├── rules/     (4개, 140줄 — 매 세션 로딩)
│   ├── coding-style.md
│   ├── git-workflow.md
│   ├── performance.md
│   └── security.md
├── skills/    (8개 — 필요 시 로딩)
│   ├── code-patterns/   ← 신규 (rules/patterns.md 이전)
│   ├── test-guide/      ← 신규 (rules/testing.md 이전)
│   ├── fastapi-endpoint/
│   ├── feature-planner/
│   ├── implement/
│   ├── pytest-suite/
│   ├── rag-agent/
│   └── react-component/
└── docs/      (변경 없음)
```
