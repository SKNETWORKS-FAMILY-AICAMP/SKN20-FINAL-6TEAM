# Task 3 — Security Audit

> 목표: OWASP Top 10 기준으로 웹 보안 취약점을 식별하고 완화한다.
> 범위: Frontend, Backend, RAG 서비스, Nginx, Docker 설정, 의존성
> 사용자 의견: 제가 보안에 대한 전반적인 지식이 부족하므로 각 Phase를 진행하기 이전에 진행방향에 대해서 상세 설명하고 의견을 묻는 과정이 추가적으로 필요합니다. 그리고 Claude는 해당 Task를 진행함에 있어서 Context7과 Web Search를 필히 사용해야 합니다.

---

## Phase 1 — 민감 정보 노출 점검

### 1.1 Git 추적 파일 점검
| 파일/디렉토리 | 상태 | 조치 |
|-------------|------|------|
| `.env` | `.gitignore`에 포함 → Git 미추적 | ✅ 확인만 |
| `.ssh/bizi-key.pem` | `.gitignore`에 `*.pem`, `.ssh/` 포함 | ✅ 확인만 |
| `chromadb_backup.tar.gz` | `.gitignore`에 포함 | ✅ 확인만 |

### 1.2 Git 히스토리 점검
- `git log --all --diff-filter=A -- '*.pem' '*.env' '*secret*'` 로 과거 커밋에 민감 파일 포함 여부 확인
- 발견 시 `git filter-branch` 또는 `BFG Repo Cleaner` 사용 여부 결정 (사용자 확인 필요)

### 1.3 하드코딩된 시크릿 검색
```bash
# 소스 코드에서 API 키/비밀번호 패턴 검색
grep -rn "sk-" --include="*.py" --include="*.ts" --include="*.tsx" --exclude-dir=node_modules --exclude-dir=.venv
grep -rn "password\s*=" --include="*.py" --exclude-dir=__pycache__ --exclude-dir=.venv
grep -rn "secret" --include="*.py" --include="*.ts" --exclude-dir=node_modules --exclude-dir=.venv
```

### 1.4 프론트엔드 환경변수
- `VITE_` 접두사 변수만 클라이언트에 노출됨 확인
- `VITE_GOOGLE_CLIENT_ID` — OAuth 클라이언트 ID는 공개 가능 ✅
- 기타 `VITE_*` 변수에 민감 정보 없는지 확인

---

## Phase 2 — XSS (Cross-Site Scripting) 점검

### 2.1 React 마크다운 렌더링
- `react-markdown` + `remark-gfm` 사용 — HTML 삽입 여부 확인
- `rehype-raw` 플러그인 사용 여부 확인 (사용 시 HTML 직접 삽입 가능 → 위험)
- `dangerouslySetInnerHTML` 사용 검색

### 2.2 사용자 입력 표시
| 위치 | 점검 내용 |
|------|----------|
| 채팅 메시지 | 사용자 입력이 HTML로 렌더링되지 않는지 |
| 기업명/사업자번호 | 테이블/카드에서 이스케이프 처리 |
| 일정 제목/내용 | 캘린더 뷰에서 이스케이프 |
| 관리자 히스토리 | 사용자 질문 표시 시 이스케이프 |
| URL 파라미터 | 라우팅에서 동적 파라미터 처리 |

### 2.3 RAG 서비스 응답
- LLM 응답에 `<script>` 태그가 포함될 수 있음 → 마크다운 렌더러에서 sanitize 확인
- 출처(Sources) URL 표시 시 `javascript:` 프로토콜 차단 확인 (ActionButtons.tsx에 이미 적용)

---

## Phase 3 — CSRF (Cross-Site Request Forgery) 점검

### 3.1 미들웨어 동작 확인
- `backend/main.py` — `CSRFMiddleware` 존재 확인
- POST/PUT/DELETE 요청에 `Content-Type: application/json` 또는 `X-Requested-With` 헤더 필수 확인
- `frontend/src/lib/api.ts` — `X-Requested-With: XMLHttpRequest` 자동 설정 확인

### 3.2 쿠키 설정
| 속성 | 개발 | 프로덕션 | 점검 |
|------|------|---------|------|
| `HttpOnly` | ✅ | ✅ | JWT 쿠키가 JavaScript 접근 불가 |
| `Secure` | ❌ | ✅ (강제) | HTTPS 전용 |
| `SameSite` | `lax` | `lax` | CSRF 보호 |
| `Domain` | 빈 값 | 설정 필요 | 프로덕션 도메인 확인 |

---

## Phase 4 — 인증/인가 (Authentication & Authorization) 점검

### 4.1 JWT 토큰 관리
| 항목 | 점검 내용 |
|------|----------|
| Access Token 만료 | 5분 — 적절 |
| Refresh Token 만료 | 7일 — 적절 |
| 토큰 블랙리스트 | 로그아웃 시 블랙리스트 추가 확인 |
| 비밀키 강도 | 32자 이상 강제 (settings.py) ✅ |
| 알고리즘 | HS256 — 대칭키. 서비스 간 공유 시 RS256 검토 |

### 4.2 엔드포인트 인증 확인
모든 보호 엔드포인트에 `Depends(get_current_user)` 적용 여부:

| 모듈 | 엔드포인트 | 인증 필요 |
|------|----------|----------|
| companies | CRUD | ✅ |
| schedules | CRUD | ✅ |
| histories | 조회/생성 | ✅ |
| admin | 대시보드/로그 | ✅ (관리자) |
| documents | 생성 | ✅ |
| auth | 로그인/회원가입 | ❌ (공개) |
| rag/chat | 질문 | ❌ (게스트 허용) |
| health | 상태 확인 | ❌ (공개) |

### 4.3 권한 분리
- 관리자 전용 엔드포인트: `U0000001` 체크 확인
- 일반 사용자 데이터 격리: 자신의 기업/일정만 접근 가능 확인
- IDOR (Insecure Direct Object Reference) 점검: 타 사용자 ID로 접근 시도

---

## Phase 5 — 입력 검증 (Input Validation) 점검

### 5.1 Backend Pydantic 스키마
| 모듈 | 점검 내용 |
|------|----------|
| `companies/schemas.py` | 사업자번호 형식 검증 ✅ (이미 구현) |
| `schedules/schemas.py` | 날짜 범위 검증 ✅ (이미 구현) |
| `admin/schemas.py` | domain 정규식 검증, llm_score 범위 검증 ✅ |
| `auth/schemas.py` | 이메일/비밀번호 형식 |
| `rag/schemas/request.py` | message 길이 제한, history 크기 제한 |

### 5.2 RAG 입력 Sanitization
- `utils/sanitizer.py` — Unicode NFC 정규화, 전각→반각 변환, zero-width 제거 ✅
- SQL 인젝션: SQLAlchemy ORM 사용 → parametrized query ✅
- ChromaDB 쿼리: 직접 쿼리 인젝션 가능성 점검

### 5.3 파일 업로드
- 문서 생성 엔드포인트: 파일 형식 검증, 크기 제한
- PDF 생성: `xml_escape()` 인젝션 방지 ✅ (이미 구현)

---

## Phase 6 — CORS 설정 점검

### 현재 설정
```python
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
# 프로덕션: localhost 자동 제거 (enforce_production_security)
```

### 점검 항목
| 항목 | 상태 | 조치 |
|------|------|------|
| 프로덕션 Origins | 자동 제거 | 프로덕션 도메인 명시 필요 |
| `allow_origins=["*"]` | 사용 안 함 ✅ | — |
| `allow_credentials` | `True` (쿠키 인증) | Origins와 함께 확인 |
| RAG CORS | 별도 설정 | Backend 프록시 경유이므로 제한적 |

---

## Phase 7 — 세션 관리 점검

### 7.1 JWT 세션
| 항목 | 점검 |
|------|------|
| 동시 세션 제한 | 미구현 → 위험도 Medium |
| 세션 하이재킹 | HttpOnly + Secure + SameSite로 완화 |
| 토큰 갱신 경쟁 | `api.ts` 재시도 큐 구현 확인 |

### 7.2 RAG 세션 메모리
| 항목 | 점검 |
|------|------|
| 세션 ID 생성 | UUID 사용 여부 |
| 세션 격리 | 타 사용자 세션 접근 불가 확인 |
| TTL | 75분 만료 설정 확인 |
| 메모리 상한 | `MAX_SESSIONS=50` 자동 정리 확인 |

---

## Phase 8 — 의존성 취약점 스캔

### 실행 절차
```bash
# Python 의존성 (Backend + RAG)
pip audit --requirement backend/requirements.txt
pip audit --requirement rag/requirements.txt

# Node.js 의존성 (Frontend)
cd frontend && npm audit

# Docker 이미지 (선택적)
docker scout cves <image-name>
```

### 점검 기준
- Critical/High 취약점: 즉시 수정
- Medium: 수정 계획 수립
- Low: 문서화

---

## Phase 9 — Nginx 보안 점검

### 현재 설정 (nginx.conf)
- 보안 헤더 5종 ✅ (이미 구현)
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy`
- 레이트 리밋 ✅ (api:10r/s, rag:5r/s)

### 추가 점검
| 항목 | 점검 |
|------|------|
| TLS/HTTPS | 프로덕션 SSL 인증서 설정 |
| 서버 헤더 | `server_tokens off` 확인 |
| 업로드 크기 제한 | `client_max_body_size` 확인 |
| 프록시 헤더 | `X-Real-IP`, `X-Forwarded-For` 전달 |

---

## Phase 10 — RAG 서비스 보안 점검

### API 키 인증
| 항목 | 점검 |
|------|------|
| `X-API-Key` 인증 | RAG 직접 호출 시 필수 |
| HMAC 비교 | `hmac.compare_digest()` 사용 (timing-safe) 확인 |
| Backend 프록시 인증 | Backend → RAG 호출 시 키 전달 확인 |

### 프롬프트 인젝션
- 사용자 입력이 LLM 프롬프트에 삽입되는 경로 확인
- 시스템 프롬프트와 사용자 입력 분리 확인
- `utils/prompts.py`에서 입력 이스케이프 여부

---

## Phase 11 — 결과 정리

### 산출물
- 취약점 보고서 (심각도, 위치, 설명, 완화 조치)
- 수정 완료 항목 목록
- 미수정 항목 + 완화 계획
- 의존성 감사 보고서
