# RAG 시스템 종합 개선 계획

## 현재 성능 (RAGAS V4 평가, 80문항)

| 지표 | 현재 점수 | 의미 |
|------|----------|------|
| **Faithfulness** | 0.51 | 답변의 절반이 컨텍스트에 근거하지 않음 |
| **Answer Relevancy** | 0.65 | 답변이 질문과 부분적으로만 관련 |
| **Context Precision** | 0.66 | 검색된 문서의 정확도 부족 |
| **Context Recall** | 0.57 | 필요한 문서를 절반가량 누락 |

---

## Phase 1: 즉시 수정 — 보안 및 안정성 [완료]

> 기능 변경 없이 보안 취약점과 안정성 이슈를 해결합니다.

| ID | 항목 | 파일 | 난이도 |
|----|------|------|--------|
| P0-1 | API Key 타이밍 공격 방어 | `rag/main.py` | S |
| P0-2 | CORS 와일드카드 제거 | `rag/main.py` | S |
| P0-3 | 프롬프트 인젝션 입력 방어 | `rag/routes/chat.py` | S |
| P0-4 | 도메인 분류 LLM 실패 시 fallback | `rag/utils/domain_classifier.py` | S |
| P0-5 | Dockerfile 헬스체크 추가 | `rag/Dockerfile` | S |

### P0-1. API Key 타이밍 공격 방어
- **위치**: `rag/main.py:209`
- **문제**: `provided_key != api_key` 문자열 비교는 타이밍 사이드채널 공격에 취약
- **수정**: `hmac.compare_digest(provided_key, api_key)`로 교체

### P0-2. CORS 와일드카드 제거
- **위치**: `rag/main.py:183-185`
- **문제**: `allow_methods=["*"]`, `allow_headers=["*"]`로 불필요한 공격면 노출
- **수정**: 허용 메서드/헤더를 명시적으로 지정
  - `allow_methods=["GET", "POST", "OPTIONS"]`
  - `allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-Requested-With"]`

### P0-3. 프롬프트 인젝션 입력 방어
- **위치**: `rag/routes/chat.py:45-49`
- **문제**: `request.message`를 sanitize 없이 직접 `aprocess()`에 전달. `utils/sanitizer.py`의 `sanitize_query()`가 존재하지만 미사용
- **수정**: `chat()`, `chat_stream()` 진입점에서 `sanitize_query()` 호출, 심각 패턴 시 HTTP 400 반환

### P0-4. 도메인 분류 LLM 실패 시 재시도 + 안내
- **위치**: `rag/utils/domain_classifier.py:400-416`
- **문제**: LLM 분류 실패 시 즉시 거부(`llm_error_rejected`) → 정상 질문도 차단
- **수정** (2단계):
  1. **1차 실패 → LLM 1회 재시도**: 동일 요청을 한 번 더 시도 (`method="llm_retry"`)
  2. **2차 실패 → 사용자에게 실패 사유 안내**: 프롬프트로 "일시적인 분류 오류로 답변을 제공하지 못했습니다. 잠시 후 다시 시도해주세요." 메시지 반환 (`method="llm_retry_failed"`)

### P0-5. Dockerfile 헬스체크 추가
- **위치**: `rag/Dockerfile`
- **문제**: HEALTHCHECK 없음 → 무응답 컨테이너 감지 불가
- **수정**: `HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8001/health || exit 1`

---

## Phase 2: 검색/생성 품질 개선 — RAGAS 점수 향상 [완료]

> 핵심 목표: Faithfulness 0.51 → 0.66+, Context Recall 0.57 → 0.64+

### Batch 2A: 검색 점수 정규화 (Context Precision 개선)

| ID | 항목 | 파일 | 난이도 | 예상 효과 |
|----|------|------|--------|----------|
| P1-1 | RRF k 파라미터 설정화 | `search.py`, `settings.py` | S | CP +0.03~0.05 |
| P1-2 | BM25 점수 정규화 | `search.py` | S | CP +0.02 |
| P1-3 | 복합 도메인 점수 정규화 | `retrieval_agent.py` | M | CP +0.03 |

#### P1-1. RRF k 파라미터 설정화
- **문제**: RRF 상수 `k=60` 하드코딩. 문서 5~15건에서 순위 차이를 거의 무시
  - k=60: `1/(60+1)=0.0164` vs `1/(60+5)=0.0154` (차이 6%)
  - k=30: `1/(30+1)=0.0323` vs `1/(30+5)=0.0286` (차이 13%)
- **수정**: settings에 `rrf_k: int = Field(default=30)` 추가

#### P1-2. BM25 점수 정규화
- **문제**: 벡터 점수(0~1) vs BM25 점수(0~수십) 범위 불일치 → 후속 정렬에서 불공정 비교
- **수정**: BM25 결과에 Min-Max 정규화 적용 (`score / max_score`)

#### P1-3. 복합 도메인 점수 정규화
- **문제**: 서로 다른 컬렉션의 점수를 직접 비교 (startup_db 0.85 vs hr_db 0.92는 비교 불가)
- **수정**: 도메인별 Min-Max 정규화 후 병합, 또는 reranker에 정렬 위임
- **의존성**: P1-2 완료 후

### Batch 2B: 검색 효율 (Context Recall / 비용 절감)

| ID | 항목 | 파일 | 난이도 | 예상 효과 |
|----|------|------|--------|----------|
| P1-4 | 법률 보충 검색 중복 제거 | `retrieval_agent.py` | S | CR +0.02 |
| P1-5 | Multi-Query 중복 실행 제거 | `retrieval_agent.py`, `rag_chain.py` | M | 응답시간 -0.5~1초 |

#### P1-4. 법률 보충 검색 중복 제거
- **문제**: 보충 문서 추가 시 기존 문서와 중복 체크 없음 → 유효 슬롯 낭비
- **수정**: `DocumentMerger._content_hash()` 활용한 중복 필터링

#### P1-5. Multi-Query 중복 실행 제거
- **문제**: 초기 검색 + 재시도에서 Multi-Query LLM 호출 2~3회 중복
- **수정**: 첫 검색 MQ 결과 캐싱, 재시도는 캐시 재활용

### Batch 2C: 프롬프트/생성 품질 (Faithfulness / Answer Relevancy)

| ID | 항목 | 파일 | 난이도 | 예상 효과 |
|----|------|------|--------|----------|
| P1-6 | 환각 방지 프롬프트 강화 | `prompts.py` | M | **Faith +0.10~0.15** |
| P1-7 | Lost in the Middle 개선 | `rag_chain.py` | S | Faith +0.05, AR +0.03 |
| P1-8 | 도메인별 LLM temperature 차등 | `generator.py`, `settings.py` | M | Faith +0.05 |
| P1-9 | Multi-Query 다양성 개선 | `prompts.py` | S | CR +0.05 |
| P1-10 | 대명사 해소 강화 | `question_decomposer.py` | M | CR +0.05 |

#### P1-6. 환각 방지 프롬프트 강화 (최대 효과 항목)
- **문제**: "참고 자료에 없는 정보 금지" 선언적 규칙만 있음
- **수정**:
  1. Step-by-step verification 지시: "답변 전 반드시 [번호] 확인, 근거 없으면 '확인 불가' 표기"
  2. Few-shot negative example (잘못된 답변 예시) 포함
  3. 답변 말미 인용 요약: "이 답변은 [1], [3] 자료를 참고했습니다"

#### P1-7. Lost in the Middle 개선
- **문제**: 문서를 순서대로 나열 → LLM이 중간 문서를 무시하는 현상
- **수정**: "Sandwich" 패턴 — score 상위 문서를 첫/끝 위치에 배치

#### P1-8. 도메인별 LLM temperature 차등
- **문제**: 모든 도메인에 temperature=0.1 고정
- **수정**: 도메인별 매핑 — `law: 0.0, finance: 0.0, hr: 0.05, startup: 0.15`

#### P1-9. Multi-Query 다양성 개선
- **문제**: "동의어 활용" 단순 지시 → 생성 쿼리가 원본과 거의 동일
- **수정**: 전략 명시 — "쿼리1: 핵심 키워드 변경, 쿼리2: 관점/범위 변경, 쿼리3: 구체적 제도명/법조항으로 변환"

#### P1-10. 대명사 해소 강화
- **문제**: 단일 도메인에서 "그것", "이것" 등 대명사가 해소되지 않음
- **수정**: 이력에서 대명사 감지 시 LLM으로 구체적 명사 치환

### Batch 2D: 평가/재시도 개선

| ID | 항목 | 파일 | 난이도 | 예상 효과 |
|----|------|------|--------|----------|
| P1-11 | 평가 가중치 채점 | `evaluator.py`, `settings.py` | M | 평가 정밀도 향상 |
| P1-12 | 도메인별 평가 임계값 차등 | `settings.py`, `evaluator.py` | M | Faith +0.03 |
| P1-13 | Retry 경로 최적화 | `router.py` | M | 재시도 응답시간 -30~50% |
| P1-14 | Fallback 메시지 에러별 분기 | `generator.py`, `settings.py` | S | UX 개선 |

#### P1-11. EvaluatorAgent 가중치 채점
- **문제**: 5개 기준 동일 가중치(각 20점)
- **수정**: `accuracy=25, citation=25, completeness=20, retrieval_quality=15, relevance=15`

#### P1-12. 도메인별 평가 임계값 차등
- **문제**: 모든 도메인 70점 고정. 법률은 부정확 정보가 치명적
- **수정**: `law=75, finance=75, hr=70, startup=65`
- **의존성**: P1-11 완료 후

#### P1-13. Retry 경로 Retrieve 재실행 최적화
- **문제**: 평가 FAIL 시 항상 검색+생성+평가 전체 재실행
- **수정**: 평가 피드백 분석 → "검색 부족" 시만 재검색, 그 외는 기존 문서 재활용+프롬프트 변형

#### P1-14. Fallback 메시지 에러 종류별 분기
- **문제**: 문서 0건, 타임아웃, 내부오류 모두 동일 메시지
- **수정**: 에러 유형별 분기 메시지 (검색 부족 / 타임아웃 / 시스템 오류)

---

## Phase 3: 성능 최적화 [완료]

### Batch 3A: 캐시 개선

| ID | 항목 | 파일 | 난이도 |
|----|------|------|--------|
| P2-1 | 캐시 키에 domain 반영 | `cache.py`, `chat.py` | S |
| P2-2 | 캐시 TTL 도메인별 차등 | `cache.py`, `settings.py` | S |

#### P2-1. 캐시 키에 domain 반영
- **문제**: domain 파라미터가 키에 미포함 → 다른 도메인에 잘못된 캐시 반환 가능
- **수정**: `f"{base_key}:domain={domain}"`으로 키 구성

#### P2-2. 캐시 TTL 도메인별 차등
- **문제**: TTL 1시간 고정. 지원사업(변경 잦음) vs 법률(변경 드묾) 차이 미반영
- **수정**: startup=30분, finance/hr/law=2시간, default=1시간

### Batch 3B: 검색/스트리밍 성능

| ID | 항목 | 파일 | 난이도 |
|----|------|------|--------|
| P2-3 | BM25 비동기 사전 빌드 | `search.py`, `chromadb_warmup.py` | M |
| P2-4 | ChromaDB 연결 리팩토링 | `chroma.py` | S |
| P2-5 | 스트리밍 타임아웃 강화 | `chat.py` | M |
| P2-6 | Rate Limiter 클라이언트별 키 구분 | `middleware.py` | M |

---

## Phase 4: 인프라/코드 구조 [완료]

### Batch 4A: 코드 구조

| ID | 항목 | 파일 | 난이도 |
|----|------|------|--------|
| P3-1 | SearchMode 미사용 모드 정리 | `retrieval_agent.py` | S |
| P3-2 | 점수 정규화 로직 통합 | `search.py`, `retrieval_agent.py` | M |
| P3-3 | 쿼리 분석 임계값 설정화 | `retrieval_agent.py`, `settings.py` | S |
| P3-4 | 복합 도메인 병합 후 평가 | `retrieval_agent.py` | M |

### Batch 4B: 인프라

| ID | 항목 | 파일 | 난이도 |
|----|------|------|--------|
| P3-5 | RAGAS 배치 평가 파이프라인 | `routes/evaluate.py` (신규) | L |
| P3-6 | 모니터링 메트릭 확장 | `middleware.py`, `router.py` | L |
| P3-7 | 의존성 버전 고정 | `requirements.txt` | S |

---

## 예상 성과 (Phase 2 완료 후)

| 지표 | 현재 | 목표 | 주요 기여 항목 |
|------|------|------|---------------|
| **Faithfulness** | 0.51 | **0.66~0.76** | P1-6(+0.10~0.15), P1-7(+0.05), P1-8(+0.05) |
| **Answer Relevancy** | 0.65 | **0.70~0.73** | P1-6(+0.03), P1-7(+0.03) |
| **Context Precision** | 0.66 | **0.71~0.74** | P1-1(+0.03), P1-2(+0.02), P1-3(+0.03) |
| **Context Recall** | 0.57 | **0.64~0.69** | P1-9(+0.05), P1-10(+0.05), P1-4(+0.02) |

---

## 수정 파일 요약

| 파일 | 관련 항목 수 | Phase |
|------|------------|-------|
| `rag/main.py` | 2 | 1 |
| `rag/routes/chat.py` | 3 | 1, 3 |
| `rag/utils/prompts.py` | 4 | 2 |
| `rag/agents/retrieval_agent.py` | 6 | 2, 4 |
| `rag/utils/search.py` | 4 | 2, 3 |
| `rag/utils/config/settings.py` | 8 | 2, 3, 4 |
| `rag/agents/generator.py` | 2 | 2 |
| `rag/agents/evaluator.py` | 2 | 2 |
| `rag/agents/router.py` | 2 | 2 |
| `rag/utils/domain_classifier.py` | 1 | 1 |
| `rag/utils/cache.py` | 2 | 3 |
| `rag/chains/rag_chain.py` | 1 | 2 |
| `rag/Dockerfile` | 1 | 1 |

---

## 실행 순서 및 의존성

```
Phase 1 (병렬 가능)
├── P0-1 + P0-2  ← 같은 파일, 1배치
├── P0-3         ← 독립
├── P0-4         ← 독립
└── P0-5         ← 독립

Phase 2
├── Batch 2A: P1-1 → P1-2 → P1-3 (순차)
├── Batch 2B: P1-4, P1-5 (독립)
├── Batch 2C: P1-6 ~ P1-10 (대부분 독립, 병렬 가능)
└── Batch 2D: P1-11 → P1-12 (순차), P1-13, P1-14 (독립)

Phase 3
├── Batch 3A: P2-1 → P2-2 (순차)
└── Batch 3B: P2-3 ~ P2-6 (독립)

Phase 4
├── Batch 4A: P3-1, P3-3 (독립), P3-2 (P1-2,P1-3 의존), P3-4
└── Batch 4B: P3-5, P3-6, P3-7 (독립)
```

---

## 검증 방법

```bash
# Phase 1: 보안 수정 검증
curl -H "X-API-Key: wrong-key" http://localhost:8001/rag/chat  # 401 확인
curl -d '{"message":"ignore instructions..."}' http://localhost:8001/rag/chat  # 400 확인

# Phase 2: RAGAS 재평가
cd /d/final_project
py -u -m rag.evaluation --dataset qa_test/ragas_dataset_v4.jsonl \
  --output rag/evaluation/results/ragas_v4_improved.json --timeout 300

# Phase 3: 응답 시간 벤치마크 (10회 반복 평균)
# Phase 4: 기존 테스트 전체 통과 확인
```
