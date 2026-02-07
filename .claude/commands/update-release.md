README.md와 RELEASE.md를 자동으로 갱신합니다.

## 대상 디렉토리

backend, frontend, rag, scripts

## 절차

### 1. 변경 분석

각 디렉토리의 RELEASE.md에서 최근 날짜(`## [YYYY-MM-DD]`)를 추출합니다.
해당 날짜 이후의 커밋을 수집합니다:

```
git log --oneline --after="YYYY-MM-DD" -- <dir>/
```

커밋이 없는 디렉토리는 건너뜁니다.

### 2. RELEASE.md 갱신

수집된 커밋을 Conventional Commit 타입별로 분류합니다:

| 타입 | 섹션 | 매칭 패턴 |
|------|------|----------|
| feat | Features | `feat:` 또는 `[feat]` |
| fix | Bug Fixes | `fix:` 또는 `[fix]` |
| docs | Documentation | `docs:` 또는 `[docs]` |
| refactor | Refactoring | `refactor:` 또는 `[refactor]` |
| perf | Performance | `perf:` 또는 `[perf]` |
| test | Tests | `test:` 또는 `[test]` |
| chore | Chores | `chore:` 또는 `[chore]` |

새 항목은 `# Release Notes` 바로 아래에 추가합니다.
같은 날짜의 기존 항목이 있으면 병합합니다.
해당 타입의 커밋이 없으면 섹션을 생략합니다.

형식:
```markdown
## [YYYY-MM-DD] - [변경 요약 한 줄]

### Features
- [feat 커밋 내용]

### Bug Fixes
- [fix 커밋 내용]
```

### 3. README.md 갱신 확인

커밋 내용을 분석하여 다음 변경이 있는지 확인합니다:
- 새 API 엔드포인트 추가
- 새 페이지/컴포넌트 추가
- 환경 변수 변경
- 의존성 변경 (requirements.txt, package.json)

해당 변경이 있으면 README.md의 관련 섹션만 갱신합니다.
수동 추가된 커스텀 섹션은 보존합니다.

### 4. 보고

갱신된 파일 목록과 변경 요약을 보고합니다.
변경이 불필요한 경우 "문서가 최신 상태입니다"라고 알립니다.

## 출력 형식

```
=== RELEASE.md 갱신 결과 ===
- backend/RELEASE.md: [N]개 커밋 추가
- rag/RELEASE.md: 변경 없음
- ...

=== README.md 갱신 결과 ===
- backend/README.md: API 엔드포인트 섹션 업데이트
- ...
```
