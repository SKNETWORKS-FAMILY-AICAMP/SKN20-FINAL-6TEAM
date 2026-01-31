# Git Workflow Rules

## 브랜치 전략

### 브랜치 종류
| 브랜치 | 용도 | 예시 |
|--------|------|------|
| `main` | 프로덕션 배포 가능 | - |
| `develop` | 개발 통합 | - |
| `feature/*` | 기능 개발 | `feature/user-auth` |
| `hotfix/*` | 긴급 버그 수정 | `hotfix/login-fix` |
| `release/*` | 릴리즈 준비 | `release/v1.0.0` |

### 브랜치 네이밍
```bash
# 형식
feature/<짧은-설명>
hotfix/<이슈번호>-<설명>
release/v<버전>

# Examples
feature/google-oauth
feature/rag-evaluation
hotfix/123-fix-token-expiry
release/v0.1.0
```

---

## 커밋 메시지 컨벤션

### 형식
```
<type>: <subject>

[optional body]

[optional footer]
```

### Type 종류
| Type | 설명 | 예시 |
|------|------|------|
| `feat` | 새 기능 | `feat: 구글 로그인 기능 추가` |
| `fix` | 버그 수정 | `fix: JWT 만료 처리 오류 수정` |
| `docs` | 문서 수정 | `docs: API 문서 업데이트` |
| `refactor` | 리팩토링 | `refactor: 인증 로직 모듈화` |
| `test` | 테스트 | `test: 사용자 서비스 단위 테스트 추가` |
| `chore` | 빌드/설정 | `chore: Docker 설정 업데이트` |
| `style` | 포맷팅 | `style: import 정렬` |
| `perf` | 성능 개선 | `perf: 쿼리 최적화` |

### Subject 규칙
- 50자 이내
- 한글 또는 영어 사용 (혼용 지양)
- 마침표 없이
- 명령형으로 작성 ("추가", "수정", "삭제")

### Body (선택)
- 72자에서 줄바꿈
- "무엇을", "왜" 설명
- 빈 줄로 subject와 구분

### Footer (선택)
- 이슈 참조: `Fixes #123`, `Closes #456`
- 호환성 변경: `BREAKING CHANGE: ...`

### 예시
```
feat: 기업 프로필 CRUD API 구현

- 기업 생성/조회/수정/삭제 엔드포인트 추가
- Pydantic 스키마로 입력 검증
- 사업자등록번호 중복 체크 로직 포함

Closes #45
```

---

## Pull Request 규칙

### PR 제목
- 70자 이내
- 커밋 메시지와 동일한 컨벤션

```
feat: 구글 OAuth2 로그인 구현
fix: 채팅 이력 저장 오류 수정
```

### PR 본문 템플릿
```markdown
## Summary
- 변경 사항 요약 (1-3 bullet points)

## Test plan
- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 수동 테스트 완료

Generated with Claude Code
```

### PR 체크리스트
- [ ] 코드 리뷰 요청
- [ ] CI/CD 파이프라인 통과
- [ ] 커버리지 유지/개선
- [ ] 관련 문서 업데이트

---

## 금지 사항 (CRITICAL)

### 절대 금지 명령어
```bash
# 강제 푸시 (main/develop)
git push --force origin main     # 절대 금지
git push --force origin develop  # 절대 금지

# 하드 리셋
git reset --hard  # 주의 필요

# 작업 내용 삭제
git checkout .    # 주의 필요
git clean -f      # 주의 필요
```

### 예외 상황
- feature 브랜치에서 rebase 후 force push는 허용
- 단, 다른 사람과 공유 중인 브랜치는 금지

---

## 작업 흐름

### 새 기능 개발
```bash
# 1. develop에서 분기
git checkout develop
git pull origin develop
git checkout -b feature/new-feature

# 2. 작업 및 커밋
git add <files>
git commit -m "feat: 새 기능 구현"

# 3. PR 생성
git push -u origin feature/new-feature
# GitHub에서 PR 생성

# 4. 리뷰 후 머지 (GitHub에서)
```

### 긴급 버그 수정
```bash
# 1. main에서 분기
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# 2. 수정 및 커밋
git commit -m "fix: 긴급 버그 수정"

# 3. main과 develop에 머지
git push -u origin hotfix/critical-bug
# PR 생성 후 main에 머지
# develop에도 체리픽 또는 머지
```

---

## Claude Code Co-Author

### 커밋 서명
Claude Code로 작성된 코드는 Co-Author 추가:

```
feat: RAG 에이전트 구현

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

---

## 리뷰 가이드라인

### 리뷰어 체크리스트
- [ ] 코드 품질 (가독성, 유지보수성)
- [ ] 보안 취약점 없음
- [ ] 테스트 충분함
- [ ] 문서화 적절함
- [ ] 성능 이슈 없음

### 리뷰 코멘트 작성
```
# 필수 수정 (blocking)
[MUST] SQL 인젝션 취약점 있음. 파라미터 바인딩 사용 필요.

# 권장 수정 (non-blocking)
[SHOULD] 이 함수는 별도 모듈로 분리하면 재사용성이 높아집니다.

# 제안 (optional)
[COULD] 캐싱을 추가하면 성능이 개선될 수 있습니다.

# 질문
[Q] 이 로직의 의도가 명확하지 않습니다. 설명 부탁드립니다.
```
