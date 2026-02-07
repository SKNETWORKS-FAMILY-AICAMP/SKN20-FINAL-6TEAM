# README.md / RELEASE.md 템플릿

/push 시 docs-agent가 생성할 사람용 문서 형식입니다.

## README.md 템플릿

### 분석 소스
- `.specs/` 스펙 파일 (프로젝트명, 설명, 기능)
- `package.json` (프론트엔드 의존성)
- `requirements.txt` / `build.gradle` (백엔드 의존성)
- `docker-compose.yml` (서비스 구성)
- `docs/` (상세 문서 링크)

### 형식

```markdown
# [프로젝트명]

> [한 줄 설명 - 스펙에서 추출]

## 주요 기능

- [기능 1]: [설명]
- [기능 2]: [설명]
- ...

## 기술 스택

| 구분 | 기술 |
|------|------|
| 프론트엔드 | React, TypeScript, Vite, TailwindCSS |
| 백엔드 | FastAPI (또는 Spring Boot) |
| 데이터베이스 | PostgreSQL, Redis |
| 인프라 | Docker Compose |

## 시작하기

### 사전 요구사항
- Docker & Docker Compose

### 실행

```bash
# 환경 변수 설정
cp .env.example .env

# 전체 서비스 실행
docker compose up -d
```

### 접속
- 프론트엔드: http://localhost:5173
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

## 프로젝트 구조

```
[tree -L 2 결과]
```

## API 개요

[도메인별 엔드포인트 수 요약]

상세: [docs/API-REFERENCE.md](docs/API-REFERENCE.md)

## 문서

- [아키텍처](docs/ARCHITECTURE.md)
- [API 레퍼런스](docs/API-REFERENCE.md)
- [데이터베이스 스키마](docs/DATABASE-SCHEMA.md)
- [프론트엔드 컴포넌트](docs/FRONTEND-COMPONENTS.md)

## 개발 가이드

### 프론트엔드 개발
```bash
cd frontend
npm install
npm run dev
```

### 백엔드 개발
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 라이선스

MIT
```

### 갱신 규칙
- README.md가 이미 있으면 → 구조를 유지하면서 내용만 갱신
- 수동 추가된 섹션(커스텀 배지, 기여 가이드 등) → 보존
- `.specs/` 파일이 없으면 → 코드 분석으로 대체

## RELEASE.md 템플릿

### 신규 생성 (/create 후 첫 push)

```markdown
# Release Notes

## [YYYY-MM-DD] - 초기 릴리즈

### 핵심 기능
- [기능 1]: [설명]
- [기능 2]: [설명]
- ...

### 기술 스택
- 프론트엔드: React + TypeScript + Vite + TailwindCSS
- 백엔드: FastAPI + SQLAlchemy
- 인프라: Docker Compose

### 파일 통계
- 총 파일: N개
- 백엔드: N개
- 프론트엔드: N개
- 테스트: N개
```

### 업데이트 (/fix 후 push)

```markdown
## [YYYY-MM-DD] - [변경 요약 한 줄]

### Features
- [feat 커밋 내용들]

### Bug Fixes
- [fix 커밋 내용들]

### Documentation
- [docs 커밋 내용들]

### Refactoring
- [refactor 커밋 내용들]
```

### 변경 내용 추출 방법

1. 기존 RELEASE.md에서 최근 날짜 확인
2. `git log --oneline` (이전 RELEASE.md 날짜 이후 커밋)
3. Conventional Commit 접두사별 분류 (feat, fix, docs, refactor, chore)
4. `git diff --stat` (변경 파일 수)

### 누적 규칙
- 새 항목은 **파일 상단**에 추가 (`# Release Notes` 바로 아래)
- 기존 항목은 하단에 그대로 보존
- 같은 날짜에 여러 push → 기존 해당 날짜 항목에 병합

### 비어있는 타입 처리
- 해당 타입의 커밋이 없으면 섹션 자체를 생략
- 예: fix 커밋이 없으면 `### Bug Fixes` 섹션 없음
