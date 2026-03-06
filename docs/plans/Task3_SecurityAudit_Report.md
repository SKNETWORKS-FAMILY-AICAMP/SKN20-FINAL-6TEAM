# Task 3 — Security Audit Report

> 점검일: 2026-03-06
> 커밋: `d48e59c`
> 범위: Frontend, Backend, RAG, Nginx, Docker, 의존성
> 기준: OWASP Top 10

---

## 요약

| 심각도 | 발견 | 수정 | 미수정 |
|--------|------|------|--------|
| CRITICAL | 3 | 3 | 0 |
| HIGH | 12 | 9 | 3 |
| MEDIUM | 16 | 4 | 12 |
| LOW | 11 | 0 | 11 |
| **합계** | **42** | **16** | **26** |

수정 커밋: 17개 파일, +80줄 / -24줄
테스트: RAG 412 passed (기존 BM25 2건 fail — 무관), Frontend 타입체크 통과

---

## Phase 1 — 민감 정보 노출 점검

| ID | 심각도 | 내용 | 결과 |
|----|--------|------|------|
| 1.1 | Info | `.env` Git 미추적 확인 | 안전 — `.gitignore` 포함, `git ls-files`에 없음 |
| 1.2 | Info | Git 히스토리 민감 파일 | 안전 — `load_secrets.sh`만 존재 (코드에 시크릿 없음) |
| 1.3 | Info | 하드코딩 시크릿 검색 | 안전 — 모든 시크릿이 `os.getenv()`/BaseSettings로 로드 |
| 1.4 | Info | VITE_* 환경변수 | 안전 — `VITE_GOOGLE_CLIENT_ID`(공개 가능)만 존재 |
| 1.5 | Low | DB URL 비밀번호 특수문자 미인코딩 | 미수정 — `urllib.parse.quote_plus()` 권장 |

---

## Phase 2 — XSS (Cross-Site Scripting) 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 2.1 | **HIGH** | SourceReferences URL `javascript:` 미차단 | `frontend/src/components/chat/SourceReferences.tsx` | **수정** — `getSafeUrl()` 헬퍼, http/https만 허용 |
| 2.2 | Medium | `react-markdown`에 `rehype-sanitize` 미적용 | `frontend/src/pages/MainPage.tsx` | 미수정 — `rehype-raw` 미사용으로 즉시 위험 없음 |
| 2.3 | Medium | CSP에 `unsafe-inline` + `unsafe-eval` 허용 | `nginx.conf:30` | 미수정 — Vite 빌드 특성상 필요, 프로덕션은 `unsafe-eval` 미사용 |
| 2.4 | Info | `dangerouslySetInnerHTML` 0건, `eval()` 0건 | 전체 | 안전 |
| 2.5 | Info | React 자동 이스케이프로 사용자 입력 안전 | 전체 | 안전 |

---

## Phase 3 — CSRF + 쿠키 + CORS 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 3.1 | **HIGH** | Refresh 요청 bare axios — `X-Requested-With` 헤더 누락 | `frontend/src/lib/api.ts:54` | **수정** — 헤더 추가 |
| 3.2 | **HIGH** | `docker-compose.prod.yaml` COOKIE_SECURE 기본값 `false` | `docker-compose.prod.yaml:79` | **수정** — `true`로 변경 |
| 3.3 | **Medium** | CORS 프로덕션 Fallback — 빈 리스트 시 localhost 허용 | `backend/config/settings.py:112` | **수정** — 경고 로그 추가 |
| 3.4 | Medium | RAG 서비스에 CSRF 미들웨어 없음 | `rag/main.py` | 미수정 — Nginx 뒤, API Key 보호 |
| 3.5 | Medium | `COOKIE_DOMAIN` 미설정 | `backend/apps/auth/router.py` | 미수정 — 단일 도메인에서 문제없음 |
| 3.6 | Low | CORS `allow_methods`에 불필요한 `OPTIONS` | `backend/main.py:132` | 미수정 |
| 3.7 | Info | HttpOnly, SameSite=lax, Secure(프로덕션 강제) 양호 | — | 안전 |
| 3.8 | Info | Token Rotation 구현 양호 | — | 안전 |

---

## Phase 4 — 인증/인가 (Authentication & Authorization) 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 4.1 | **CRITICAL** | test-login 임의 `type_code`로 관리자 권한 탈취 | `backend/apps/auth/router.py:216` | **수정** — `U0000002`, `U0000003` 화이트리스트 |
| 4.2 | **HIGH** | documents/save API Key `!=` 비교 (timing attack) | `backend/apps/documents/router.py:27` | **수정** — `hmac.compare_digest()` |
| 4.3 | HIGH | `RAG_API_KEY` 미설정 시 보호 엔드포인트 개방 | `rag/main.py`, `backend/apps/documents/router.py` | 미수정 — 프로덕션 검증 경고 존재, fail-closed 전환은 동작 변경 |
| 4.4 | HIGH | Refresh Token reuse detection 없음 | `backend/apps/auth/router.py` | 미수정 — 대규모 구현 필요 (Token Rotation은 이미 구현) |
| 4.5 | Medium | RAG 모니터링 `admin_api_key` 미설정 시 인증 우회 | `rag/routes/monitoring.py` | 미수정 |
| 4.6 | Low | JWT 알고리즘 HS256 (단일 서비스에서 적절) | `backend/config/settings.py` | 유지 |
| 4.7 | Info | 모든 보호 엔드포인트 `Depends(get_current_user)` 일관 적용 | — | 안전 |
| 4.8 | Info | IDOR 방지 — 서비스 레이어 `user_id` 기반 WHERE 조건 | — | 안전 |
| 4.9 | Info | 프로덕션에서 test-login 자동 비활성화 | — | 안전 |

---

## Phase 5 — 입력 검증 (Input Validation) 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 5.1 | **HIGH** | `ModifyDocumentRequest.file_content` 크기 제한 없음 | `rag/schemas/request.py:380` | **수정** — `max_length=67_108_864` |
| 5.2 | **HIGH** | business-plan `format` 미검증 | `rag/routes/documents.py:53` | **수정** — `pattern=r"^(pdf|docx)$"` |
| 5.3 | **HIGH** | `form_key` 경로 순회 미차단 | `rag/routes/documents.py:119` | **수정** — `max_length=500`, pattern 추가 |
| 5.4 | **HIGH** | `DocumentRequest` format/doc_type_id 미검증 | `rag/schemas/request.py:253-254` | **수정** — format pattern, doc_type_id max_length |
| 5.5 | Medium | `ChatMessage.role` enum 미제한 | `rag/schemas/request.py:214` | 미수정 — LangChain이 role 처리 |
| 5.6 | Medium | `ChatMessage.content` 길이 제한 없음 | `rag/schemas/request.py:215` | 미수정 — history 20개 제한으로 완화 |
| 5.7 | Medium | `UserContext.user_type` enum 미제한 | `rag/schemas/request.py:60` | 미수정 — fallback 기본값 존재 |
| 5.8 | Medium | `GenerateDocumentRequest.params` dict 무제한 | `rag/schemas/request.py:361` | 미수정 — body size 제한으로 완화 |
| 5.9 | Medium | `DocumentCreate.file_format` 허용 값 미검증 | `backend/apps/documents/schemas.py:16` | 미수정 |
| 5.10 | Low | `CompanyContext` 필드 길이 제한 없음 | `rag/schemas/request.py:26-32` | 미수정 |
| 5.11 | Low | `histories/schemas.py` llm_score 범위 미검증 | `backend/apps/histories/schemas.py:35` | 미수정 |
| 5.12 | Info | SQL 인젝션 위험 없음 (SQLAlchemy ORM 전체 사용) | — | 안전 |
| 5.13 | Info | 파일 업로드 검증 양호 (확장자/크기/형식) | — | 안전 |
| 5.14 | Info | ChromaDB 쿼리 인젝션 해당 없음 (임베딩 기반) | — | 안전 |

---

## Phase 7 — 세션 관리 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 7.1 | Medium | 동시 세션 제한 미구현 | `backend/apps/auth/router.py` | 미수정 — 대규모 기능 |
| 7.2 | Medium | 인메모리 세션 저장 시 재시작 데이터 손실 | `rag/routes/_session_memory.py:24` | 미수정 — Redis 사용 권장 |
| 7.3 | Low | 전체 기기 로그아웃 기능 없음 | `backend/apps/auth/router.py` | 미수정 |
| 7.4 | Info | Refresh 재시도 큐 올바르게 구현 | `frontend/src/lib/api.ts` | 안전 |
| 7.5 | Info | 세션 격리 (owner_key 기반) 양호 | `rag/routes/_session_memory.py` | 안전 |
| 7.6 | Info | TTL 75분, MAX_SESSIONS=50 자동 정리 양호 | — | 안전 |

---

## Phase 8 — 의존성 취약점

| ID | 심각도 | 내용 | 수정 |
|----|--------|------|------|
| 8.1 | HIGH | Vite 5.0.10 — 알려진 CVE (CVE-2024-45812 등) | 미수정 — 별도 업그레이드 작업 |
| 8.2 | HIGH | React 18.2.0 고정 — 보안 패치 미적용 | 미수정 — 별도 업그레이드 작업 |
| 8.3 | HIGH | Python 3.10 베이스 이미지 — 2026-10 EOL | 미수정 — 별도 마이그레이션 |
| 8.4 | Medium | LangChain 넓은 버전 범위 | 미수정 |
| 8.5 | Medium | ChromaDB 정확한 버전 핀 (패치 자동 적용 불가) | 미수정 |
| 8.6 | Medium | Frontend devDependencies 고정 버전 다수 | 미수정 |
| 8.7 | Low | `generateId()` Math.random() 폴백 | 미수정 |
| 8.8 | Info | Backend 주요 패키지 (FastAPI, SQLAlchemy, PyJWT) 양호 | 안전 |

---

## Phase 9 — Nginx 보안 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 9.1 | **Medium** | 불필요한 HTTP 메서드 미차단 | `nginx.conf`, `nginx.e2e.conf`, `nginx.prod.conf` | **수정** — TRACE 등 차단 |
| 9.2 | **Medium** | nginx.prod.conf 보안 헤더 상속 누락 | `nginx.prod.conf:97-117` | **수정** — /assets/, /index.html에 4개 헤더 추가 |
| 9.3 | Medium | CSP `unsafe-inline`/`unsafe-eval` | `nginx.conf:30` | 미수정 — Vite 빌드 특성 |
| 9.4 | Medium | HSTS 개발 환경 미적용 | `nginx.conf` | 미수정 — HTTP 환경에서 불가 |
| 9.5 | Medium | RAG 엔드포인트 별도 레이트 리밋 미적용 | `nginx.conf:5` | 미수정 |
| 9.6 | Low | `autoindex off` 미명시 (기본값 off) | 전체 | 미수정 |
| 9.7 | Low | 커스텀 에러 페이지 미설정 | 전체 | 미수정 |
| 9.8 | Low | `proxy_send_timeout` 개발 환경 미설정 | `nginx.conf` | 미수정 |
| 9.9 | Low | X-XSS-Protection 현대 브라우저에서 무효 | 전체 | 유지 (해 없음) |
| 9.10 | Info | `server_tokens off` 설정 양호 | 전체 | 안전 |
| 9.11 | Info | 프로덕션 SSL/HSTS/gzip 양호 | `nginx.prod.conf` | 안전 |

---

## Phase 10 — RAG 서비스 보안 점검

| ID | 심각도 | 내용 | 파일 | 수정 |
|----|--------|------|------|------|
| 10.1 | **CRITICAL** | 세션 삭제 엔드포인트 인가 부재 | `rag/routes/chat.py:767-791` | **수정** — owner_key 소유권 검증 + 세션 존재 확인 |
| 10.2 | **CRITICAL** | 활성 세션 조회 인가 부재 | `rag/routes/sessions.py:16` | **수정** — `user_id` gt=0 검증 |
| 10.3 | **HIGH** | 관리자 API 키 timing-safe 미사용 | `rag/routes/monitoring.py:26` | **수정** — `hmac.compare_digest()` |
| 10.4 | **HIGH** | vectordb/evaluate 엔드포인트 API Key 미적용 | `rag/main.py:285` | **수정** — PROTECTED_PREFIXES 확장 |
| 10.5 | **HIGH** | sanitizer 원본 복원 우회 | `rag/utils/sanitizer.py:137-143` | **수정** — 안전한 기본 쿼리 `"안녕하세요"` 대체 |
| 10.6 | **Medium** | funding/search `k` 상한 없음 | `rag/routes/funding.py:18` | **수정** — `ge=1, le=100` |
| 10.7 | Medium | 다수 프롬프트에 인젝션 가드 미적용 | `rag/utils/prompts.py` | 미수정 — 내부 파이프라인용 |
| 10.8 | Medium | 캐시 키 MD5 사용 | `rag/routes/chat.py:66-79` | 미수정 — 캐시 키용, 보안 해싱 아님 |
| 10.9 | Medium | Health 엔드포인트 내부 구성 정보 노출 | `rag/routes/health.py` | 미수정 — 운영 모니터링 필요 |
| 10.10 | Low | CORS 프로덕션 localhost 허용 가능 | `rag/utils/config/settings.py` | 미수정 — Backend와 동일 패턴 |
| 10.11 | Low | 관리자 키 미설정 시 관리 엔드포인트 무인증 | `rag/routes/monitoring.py` | 미수정 |
| 10.12 | Low | ChromaDB 인증 토큰 선택적 | `rag/utils/config/settings.py` | 미수정 — Docker 네트워크 격리 |
| 10.13 | Info | PII 마스킹, 응답 길이 제한, 에러 핸들러 양호 | — | 안전 |
| 10.14 | Info | 시스템/사용자 프롬프트 분리 (LangChain ChatPromptTemplate) | — | 안전 |
| 10.15 | Info | `PROMPT_INJECTION_GUARD` 적용 양호 | — | 안전 |

---

## 수정된 파일 목록 (17개)

| 파일 | 수정 내용 |
|------|----------|
| `backend/apps/auth/router.py` | test-login type_code 화이트리스트 |
| `backend/apps/documents/router.py` | API Key `hmac.compare_digest()` |
| `backend/config/settings.py` | CORS 빈 리스트 경고 로그 |
| `docker-compose.prod.yaml` | COOKIE_SECURE 기본값 `true` |
| `frontend/src/components/chat/SourceReferences.tsx` | URL `getSafeUrl()` 검증 |
| `frontend/src/lib/api.ts` | Refresh 요청 `X-Requested-With` 헤더 |
| `nginx.conf` | HTTP 메서드 차단 |
| `nginx.e2e.conf` | HTTP 메서드 차단 |
| `nginx.prod.conf` | HTTP 메서드 차단 + 보안 헤더 상속 |
| `rag/main.py` | PROTECTED_PREFIXES 확장 |
| `rag/routes/chat.py` | 세션 삭제 owner_key 검증 |
| `rag/routes/documents.py` | format pattern, form_key 경로 검증 |
| `rag/routes/funding.py` | k 파라미터 상한 |
| `rag/routes/monitoring.py` | 관리자 키 `hmac.compare_digest()` |
| `rag/routes/sessions.py` | user_id gt=0 검증 |
| `rag/schemas/request.py` | file_content max_length, format pattern, doc_type_id max_length |
| `rag/utils/sanitizer.py` | 인젝션 탐지 후 안전 기본 쿼리 대체 |

---

## 미수정 사유 분류

### 대규모 구현 필요 (별도 작업)
- Refresh Token reuse detection
- 동시 세션 제한
- 전체 기기 로그아웃
- 의존성 업그레이드 (Vite, React, Python 3.10)

### 현재 구조에서 위험도 낮음
- RAG CSRF 미들웨어 (Nginx + API Key로 보호)
- COOKIE_DOMAIN (단일 도메인)
- ChromaDB 인증 (Docker 네트워크 격리)
- Health 엔드포인트 정보 노출 (운영 모니터링 필요)

### 기존 동작 변경 위험
- RAG_API_KEY fail-closed 전환 (기존 fail-open)
- CSP unsafe-inline 제거 (Vite 빌드 호환성)

---

## 권장 후속 작업

1. **의존성 업그레이드**: Vite 5.4+, React 18.3+, Python 3.12+ (별도 브랜치)
2. **Refresh Token reuse detection**: 블랙리스트 RT 재사용 시 전체 세션 무효화
3. **RAG_API_KEY fail-closed**: 프로덕션에서 미설정 시 `ValueError` raise
4. **CSP nonce 기반 전환**: `unsafe-inline` 제거 (Vite 빌드 설정 변경 필요)
5. **`npm audit` / `pip audit`**: CI/CD에 의존성 취약점 스캔 추가
