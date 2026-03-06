# Task 4 — Refactoring

> 목표: 애플리케이션 동작을 변경하지 않으면서 코드 품질을 개선한다.
> 원칙: **기존 기능 절대 유지**. 동작 보존. 최소 변경. 기존 패턴 재사용. 테스트 통과 필수.
> 검증: 모든 Phase 완료 시 전체 테스트 스위트 실행 + /chrome UI 검증으로 기능 무결성 확인
> 의사결정: 리팩토링 방식이 여러 가지인 경우(예: 컴포넌트 분리 범위, 추상화 수준, 네이밍 컨벤션 등), `AskUserQuestion`으로 사용자에게 선택지를 제시하고 확인을 받은 후 진행한다.

---

## Phase 1 — 코드 품질 현황 분석

### 실행 절차
1. **Frontend 린트**: `cd frontend && npx eslint .` → 경고/에러 목록
2. **Frontend 타입체크**: `cd frontend && npx tsc --noEmit` → 타입 에러 목록
3. **Backend 린트**: `ruff check backend/` → 경고/에러 목록
4. **RAG 린트**: `ruff check rag/` → 경고/에러 목록
5. 결과를 심각도별로 분류

---

## Phase 2 — Frontend 중복 코드 제거

### 2.1 대규모 컴포넌트 분리
| 파일 | 현재 줄수 | 조치 |
|------|----------|------|
| `CompanyForm.tsx` | ~530줄 | 폼 섹션별 서브 컴포넌트 추출 |

분리 전략:
- `CompanyBasicInfo` — 기본 정보 (회사명, 사업자번호, 업종)
- `CompanyAddressInfo` — 주소 정보 (지역 선택)
- `CompanyDetailInfo` — 상세 정보
- `useCompanyForm` — 폼 로직 커스텀 훅

### 2.2 API 호출 패턴 통일
| 현재 | 개선 |
|------|------|
| 컴포넌트 내 직접 axios 호출 산재 | `lib/` 하위 API 모듈로 통합 |
| 에러 핸들링 중복 | `errorHandler.ts` 활용 일관성 |

### 2.3 미사용 코드 제거
- 미사용 import 제거
- 미사용 변수/함수 제거
- `mockResponses.ts` — 실제 사용 여부 확인 후 제거

---

## Phase 3 — 모듈/함수 문서화

> 전략: **모듈 docstring + public API docstring**에 집중. 자명한 코드에는 인라인 주석 불필요.

### 대상 범위

| 레벨 | 대상 | 적용 기준 |
|------|------|----------|
| **모듈 docstring** | 모든 `.py` / `.ts` 파일 최상단 | 파일의 역할을 1~2줄로 설명 |
| **클래스 docstring** | 모든 public 클래스 | 클래스의 책임과 주요 사용처 |
| **함수 docstring** | public 함수, 복잡한 private 함수 | 매개변수, 반환값, 핵심 동작 |
| **인라인 주석** | 비직관적 로직만 | 정규식, 비트 연산, 도메인 특수 로직 등 |

### 실행 절차

#### Python (Backend + RAG)
1. 모듈 docstring 없는 파일 식별: `grep -rL '"""' backend/apps/ rag/agents/ rag/utils/ --include="*.py"`
2. 각 파일 최상단에 1~2줄 docstring 추가
3. public 함수/클래스에 Google style docstring 추가:
   ```python
   def classify_domain(query: str, threshold: float = 0.5) -> DomainResult:
       """사용자 질문을 분석하여 관련 도메인을 분류한다.

       Args:
           query: 사용자 입력 질문
           threshold: 도메인 매칭 최소 신뢰도 (0~1)

       Returns:
           DomainResult: 분류된 도메인과 신뢰도 점수
       """
   ```

#### TypeScript (Frontend)
1. 컴포넌트에 JSDoc 주석 추가:
   ```typescript
   /**
    * 기업 등록/수정 폼 컴포넌트.
    * 사업자번호 검증, 지역 선택, 업종 선택 기능을 포함한다.
    */
   const CompanyForm: React.FC<CompanyFormProps> = ({ ... }) => {
   ```
2. 커스텀 훅에 용도/반환값 설명 추가
3. Zustand 스토어에 상태 구조 설명 추가

### 제외 대상
- `__init__.py` (빈 파일)
- 테스트 파일 (테스트 이름이 곧 문서)
- 설정 파일 (필드명이 자명)
- 이미 docstring이 충분한 파일

---

## Phase 4 — Backend 코드 개선

### 4.1 서비스 레이어 일관성
| 현재 상태 | 개선 |
|----------|------|
| 일부 router에 비즈니스 로직 혼재 | service 레이어로 분리 |
| 에러 응답 형식 불일관 | 통일된 에러 응답 스키마 |

### 4.2 타입 힌트 보강
- `service.py` 파일들의 반환 타입 명시
- `Optional` vs `| None` 통일 (Python 3.10+)

### 4.3 매직 넘버/문자열 상수화
- 이미 상당 부분 완료 (Phase 5, 7, 8에서)
- 잔여 매직 넘버 검색 및 상수화

---

## Phase 5 — RAG 코드 개선

### 5.1 모듈 구조
| 현재 | 개선 |
|------|------|
| `utils/` 에 31개 파일 | 관련 모듈 그룹핑 (이미 `config/` 분리됨) |
| `utils/prompts.py` 매우 큼 | 도메인별 프롬프트 분리 검토 |

### 5.2 에러 핸들링 구조화
| 현재 | 개선 |
|------|------|
| 개별 try-catch 산재 | 공통 예외 클래스 활용 확대 |
| 로깅 레벨 불일관 | ERROR/WARNING/INFO 기준 통일 |

### 5.3 중복 제거
- retrieval 로직에서 반복되는 패턴 추출
- 도메인별 에이전트의 공통 로직 BaseAgent로 통합 확인

---

## Phase 6 — 명명 일관성

### Frontend
| 현재 | 개선 |
|------|------|
| 파일명: PascalCase 컴포넌트, camelCase 훅 | 확인 및 통일 |
| 변수명: 혼재 | camelCase 통일 |
| API 응답 필드: snake_case → camelCase 매핑 | 일관성 확인 |

### Backend
| 현재 | 개선 |
|------|------|
| 함수명: snake_case | ✅ PEP 8 준수 확인 |
| 클래스명: PascalCase | ✅ 확인 |
| 상수: UPPER_SNAKE_CASE | 확인 및 통일 |

---

## Phase 7 — 미사용 의존성 제거

### Frontend
```bash
# 미사용 패키지 검색
cd frontend && npx depcheck
```

### Backend / RAG
```bash
# requirements.txt 에서 실제 import되지 않는 패키지 검색
# 각 패키지가 실제 코드에서 사용되는지 grep으로 확인
```

---

## Phase 8 — 에러 핸들링 구조 개선

### Frontend
| 현재 | 개선 |
|------|------|
| `ErrorBoundary` 최상위만 | 페이지별 ErrorBoundary 검토 |
| `axios.isAxiosError()` 일부만 적용 | 전체 통일 |
| `Promise.allSettled` 일부만 적용 | 병렬 호출 전체 적용 |

### Backend
| 현재 | 개선 |
|------|------|
| HTTPException 직접 throw | 공통 예외 핸들러 확인 |
| 에러 메시지 한국어 통일 | 잔여 영어 메시지 확인 |

---

## Phase 9 — 검증 (기능 무결성 최우선)

> **원칙**: 리팩토링 후 기존 기능이 하나라도 깨지면 해당 변경을 즉시 롤백한다.

### 9.1 자동 테스트
- [ ] `.venv/bin/pytest rag/tests/ -v` — 전체 통과 (391+ tests)
- [ ] `.venv/bin/pytest backend/tests/ -v` — 전체 통과
- [ ] `cd frontend && npm run test` — 전체 통과
- [ ] `cd frontend && npx tsc --noEmit` — 타입 에러 없음
- [ ] `ruff check backend/ rag/` — 린트 통과

### 9.2 /chrome UI 기능 검증 (Phase별 수행)
각 리팩토링 Phase 완료 후 `/chrome`으로 핵심 기능을 검증한다:
- [ ] 채팅: 질문 전송 → 스트리밍 응답 → 출처 표시
- [ ] 인증: 로그인 → 보호 라우트 접근 → 로그아웃
- [ ] 기업: 등록 → 수정 → 삭제
- [ ] 일정: 생성 → 캘린더 표시

### 9.3 롤백 기준
- 테스트 1개라도 실패 → 해당 Phase 변경 롤백
- UI 기능 1개라도 깨짐 → 해당 Phase 변경 롤백
- 롤백 후 원인 분석 → 수정 범위 축소하여 재시도
