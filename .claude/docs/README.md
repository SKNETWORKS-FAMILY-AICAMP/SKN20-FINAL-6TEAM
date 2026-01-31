# Bizi Claude Code 설정 가이드

## 개요

이 문서는 Bizi 프로젝트의 Claude Code 설정을 설명합니다.

## 디렉토리 구조

```
.claude/
├── docs/                    # 설명 문서 (이 폴더)
│   ├── README.md
│   ├── agents/              # 에이전트 사용법
│   └── skills/              # 스킬 사용법
├── rules/                   # 코드 규칙
│   ├── coding-style.md      # 코딩 스타일
│   ├── security.md          # 보안 규칙
│   ├── testing.md           # 테스트 규칙
│   └── git-workflow.md      # Git 워크플로우
├── agents/                  # 에이전트 정의
│   ├── react-form-architect.md
│   ├── code-reviewer.md
│   ├── tdd-guide.md
│   ├── rag-specialist.md
│   └── fastapi-architect.md
├── skills/                  # 스킬 정의
│   ├── feature-planner/
│   ├── rag-agent/
│   ├── pytest-suite/
│   ├── fastapi-endpoint/
│   └── react-component/
├── commands/                # 명령어
│   ├── test-rag.md
│   ├── test-backend.md
│   ├── test-frontend.md
│   ├── lint.md
│   ├── build-vectordb.md
│   ├── cli-test.md
│   └── typecheck.md
├── hooks/                   # 훅 설정
│   ├── hooks.json
│   └── README.md
└── settings.local.json      # 권한 설정
```

## 에이전트

| 에이전트 | 설명 | 사용 시점 |
|---------|------|----------|
| react-form-architect | React 폼 개발 | 폼 컴포넌트 생성/리뷰 |
| code-reviewer | 코드 리뷰 | 코드 품질/보안 검토 |
| tdd-guide | TDD 가이드 | 테스트 작성 안내 |
| rag-specialist | RAG 개발 | LangChain/벡터DB 작업 |
| fastapi-architect | FastAPI 개발 | 백엔드 API 구현 |

## 스킬

| 스킬 | 설명 | 호출 방법 |
|------|------|----------|
| feature-planner | 기능 계획 수립 | `/feature-planner` |
| rag-agent | RAG 에이전트 생성 | `/rag-agent` |
| pytest-suite | pytest 테스트 생성 | `/pytest-suite` |
| fastapi-endpoint | FastAPI 엔드포인트 생성 | `/fastapi-endpoint` |
| react-component | React 컴포넌트 생성 | `/react-component` |

## 명령어

| 명령어 | 설명 |
|--------|------|
| `/test-rag` | RAG 테스트 실행 |
| `/test-backend` | Backend 테스트 실행 |
| `/test-frontend` | Frontend 테스트 실행 |
| `/lint` | 전체 린트 실행 |
| `/typecheck` | 타입 검사 실행 |
| `/build-vectordb` | 벡터 인덱스 빌드 |
| `/cli-test` | RAG CLI 테스트 |

## 규칙

### 코딩 스타일 (`rules/coding-style.md`)
- Python: 타입 힌트, Pydantic 사용
- TypeScript: strict 모드, any 금지
- 환경 변수 사용 필수

### 보안 (`rules/security.md`)
- API 키 하드코딩 금지
- SQL 인젝션 방지 (ORM 사용)
- 입력 검증 필수

### 테스트 (`rules/testing.md`)
- pytest (Python)
- Vitest (TypeScript)
- 커버리지 목표: 75% 이상

### Git 워크플로우 (`rules/git-workflow.md`)
- 브랜치 전략: main/develop/feature
- 커밋 컨벤션: feat/fix/docs 등
- PR 템플릿 준수

## 권한 설정

`settings.local.json`에서 허용된 도구:
- WebSearch, WebFetch (특정 도메인)
- Bash (pip, python, pytest, npm, docker 등)

## 훅

- **PreToolUse**: 도구 실행 전 체크
- **PostToolUse**: 도구 실행 후 분석
- **SessionStart**: 세션 시작 시 정보 표시

## 참고 문서

- [CLAUDE.md](/CLAUDE.md) - 프로젝트 전체 가이드
- [backend/CLAUDE.md](/backend/CLAUDE.md) - Backend 개발 가이드
- [frontend/CLAUDE.md](/frontend/CLAUDE.md) - Frontend 개발 가이드
- [rag/CLAUDE.md](/rag/CLAUDE.md) - RAG 개발 가이드
