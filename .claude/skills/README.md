# Claude Code Skills for SKN20 Final Team 6

이 디렉토리에는 프로젝트에서 사용하는 커스텀 Claude Code 스킬들이 포함되어 있습니다.

## 📚 사용 가능한 스킬

### 1. notion-docs.md
**목적:** Notion 워크스페이스에 문서를 생성하고 관리합니다.

**주요 기능:**
- Notion 페이지 생성
- 프로젝트 문서 구조화
- 워크스페이스 검색
- 태스크 생성 및 관리

**사용 예시:**
```
"Notion에 프로젝트 개요 페이지를 만들어주세요"
"skn final HQ 페이지를 찾아서 하위에 문서를 추가해주세요"
```

### 2. notion-project-sync.md
**목적:** 로컬 마크다운 파일과 Notion 워크스페이스 간 자동 동기화

**주요 기능:**
- PRD.md, AGENTS.md, SETUP.md, CLAUDE.md 자동 동기화
- 양방향 동기화 (로컬 ↔ Notion)
- 메타데이터 자동 추가
- 충돌 감지 및 해결

**사용 예시:**
```
"프로젝트 문서를 Notion에 동기화해주세요"
"PRD.md 변경사항을 Notion에 반영해주세요"
```

## 🚀 스킬 사용 방법

### 방법 1: 직접 요청
Claude Code와 대화할 때 직접 요청:
```
"Notion에 팀 회의 노트를 작성해주세요"
```

### 방법 2: 스킬 참조
특정 스킬을 참조하여 요청:
```
"@notion-docs 스킬을 사용해서 프로젝트 문서를 만들어주세요"
```

### 방법 3: 자동 실행
Claude Code가 문맥을 보고 자동으로 적절한 스킬 선택

## 📝 스킬 추가 방법

새로운 스킬을 추가하려면:

1. `.claude/skills/` 디렉토리에 새 마크다운 파일 생성
2. 다음 구조를 따라 작성:

```markdown
# [스킬 이름]

## Overview
스킬의 목적과 기능 설명

## Usage
사용 방법과 예시

## Examples
구체적인 사용 예시

## Best Practices
모범 사례 및 팁

## Troubleshooting
문제 해결 가이드
```

3. README.md에 새 스킬 추가

## 🔧 현재 프로젝트에서 활용

### Notion 통합
이 프로젝트는 Notion MCP 서버와 통합되어 있습니다:
- `notion-docs.md`: 기본 Notion 문서 작업
- `notion-project-sync.md`: 자동 동기화

### 사용 가능한 Notion 스킬
- `Notion:notion-create-page` - 페이지 생성
- `Notion:notion-search` - 워크스페이스 검색
- `Notion:notion-find` - 제목으로 페이지 찾기
- `Notion:notion-create-task` - 태스크 생성
- `Notion:notion-database-query` - 데이터베이스 쿼리

## 💡 팁

### 효과적인 스킬 사용
1. **구체적으로 요청**: "문서 만들어줘" → "PRD 문서를 Notion에 한글로 만들어줘"
2. **컨텍스트 제공**: 어떤 프로젝트인지, 어디에 만들지 명확히 설명
3. **기존 패턴 참조**: 이전에 만든 문서 구조를 따르도록 요청

### 한글 문서 작성
Notion 페이지는 항상 한글로 작성하도록 명시:
```
"Notion에 한글로 팀 역할 문서를 만들어주세요"
```

### 동기화 워크플로우
1. 로컬에서 .md 파일 수정
2. Git commit
3. "Notion에 동기화해주세요" 요청
4. 팀원들이 Notion에서 확인

## 🔗 관련 문서

- [PRD.md](../../PRD.md) - 제품 요구사항
- [AGENTS.md](../../AGENTS.md) - 팀 역할 및 작업
- [SETUP.md](../../SETUP.md) - 환경 설정
- [CLAUDE.md](../../CLAUDE.md) - Claude Code 가이드

## ❓ 문제 해결

### 스킬이 인식되지 않을 때
1. `.claude/skills/` 디렉토리 위치 확인
2. 파일이 `.md` 확장자인지 확인
3. Claude Code 재시작

### Notion 연결 문제
1. Notion MCP 서버가 설정되어 있는지 확인
2. API 키가 올바른지 확인
3. 워크스페이스 권한 확인

### 동기화 실패
1. 로컬 파일이 올바른 형식인지 확인
2. Notion 페이지 권한 확인
3. 네트워크 연결 확인

## 📚 추가 리소스

- [Claude Code 공식 문서](https://docs.anthropic.com/claude-code)
- [Notion API 문서](https://developers.notion.com/)
- [MCP 서버 가이드](https://github.com/anthropics/mcp-servers)

---

**Last Updated:** 2026-01-14
**Maintainer:** Team Lead
**Version:** 1.0
