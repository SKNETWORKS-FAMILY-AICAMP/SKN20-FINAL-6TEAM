# RAG 파이프라인 최적화 기록

> 최종 업데이트: 2026-02-01

## 목표

| 항목 | 목표 | 현재 상태 |
|------|------|----------|
| 응답 시간 | 10~15초 | **15.6초** (근접) |
| 품질 점수 | 95점 이상 | **96점** (4대보험 제외) |

---

## 최적화 히스토리

### 1. 초기 상태
- 응답 시간: ~30초
- 품질 점수: 측정 안 됨

### 2. 1차 최적화 (설정 조정)
- Multi-query 쿼리 수: 3개 → 2개
- MMR fetch_k multiplier: 4 → 3
- 캐시 TTL: 1시간 → 2시간
- 평가 스킵 확률: 15% 적용
- **결과: 30초 → 18초**

### 3. 2차 최적화 (평가 노드 제거)
- 평가 노드(EvaluatorAgent) 완전 제거
- 이유: 재시도율 0%, 96점 유지 → 실질적 가치 없음
- LangGraph 워크플로우: classify → route → integrate → **END** (evaluate 노드 삭제)
- **결과: 18초 → 16초**

### 4. 3차 최적화 (Re-ranking 배치 축소)
- Re-rank 배치 크기: 6 → 4
- **결과: 16초 → 15.6초**

---

## 최종 테스트 결과 (평가 노드 제거 + Re-rank 배치 4)

| # | 쿼리 | 응답 시간 | 품질 점수 |
|---|------|----------|----------|
| 1 | 사업자등록 절차 | 17.55초 | - (평가 없음) |
| 2 | 퇴직금 계산 | 15.33초 | - |
| 3 | 법인세 신고 | 14.01초 | - |

**평균: 15.63초**

### 이전 테스트 결과 (평가 노드 있을 때)

| # | 쿼리 | 응답 시간 | 품질 점수 |
|---|------|----------|----------|
| 1 | 사업자등록 절차 | 15.32초 | 96점 |
| 2 | 퇴직금 계산 | 19.88초 | 93점 |
| 3 | 법인세 신고 기한 | 16.40초 | 98점 |
| 4 | 직원 채용 서류 | 18.37초 | 98점 |
| 5 | 창업 지원금 신청 | 20.01초 | 95점 |
| 6 | 4대보험 가입 | 19.32초 | **75점** (데이터 부족) |

**평균 (4대보험 제외): 18.22초, 96점**

---

## 현재 설정 (config.py)

```python
# 모델 설정
openai_model = "gpt-4o-mini"           # 메인 (답변 생성, Re-ranking)
auxiliary_model = "gpt-3.5-turbo"      # 보조 (분류, Multi-query)

# 평가 설정 (평가 노드 제거됨)
evaluation_threshold = 68              # 미사용
max_retry_count = 1                    # 미사용
skip_evaluation_probability = 0.15    # 미사용

# RAG 설정
retrieval_k = 3                        # 도메인별 검색 결과 수
retrieval_k_common = 2                 # 공통 법령 DB 검색 수
mmr_fetch_k_multiplier = 3
mmr_lambda_mult = 0.7

# Multi-query
enable_multi_query = True
multi_query_count = 2

# Re-ranking
enable_reranking = True
rerank_top_k = 4
rerank_batch_size = 4                  # 6 → 4 최적화

# 캐싱
enable_response_cache = True
cache_ttl = 7200                       # 2시간
enable_domain_cache = True
```

---

## 아키텍처 변경사항

### LangGraph 워크플로우 (변경 후)

```
classify → route → integrate → END
```

- **evaluate 노드 제거됨**
- 재시도 로직 제거됨 (retry 엣지 없음)

### 파일 변경 목록

| 파일 | 변경 내용 |
|------|----------|
| `agents/router.py` | evaluate 노드 제거, 워크플로우 단순화 |
| `utils/config.py` | rerank_batch_size 6→4, skip_evaluation_probability 복원 |
| `agents/evaluator.py` | 파싱 실패 로깅 추가 (사용되지 않음) |
| `main.py` | 도메인 캐시 버그 수정, ImportError 처리 추가 |

---

## 알려진 이슈

### 1. 4대보험 쿼리 낮은 품질 (75점)
- **원인**: VectorDB에 4대보험 관련 데이터 부족
- **해결 방안**: hr_labor_db에 4대보험 전용 데이터 추가 필요
- **우선순위**: 중간

### 2. 응답 시간 변동
- 쿼리 복잡도, 검색 결과 수에 따라 14~18초 변동
- 목표 10~15초에 근접하지만 완전 달성은 아님

---

## 추가 최적화 옵션 (미적용)

| 옵션 | 예상 효과 | 리스크 |
|------|----------|--------|
| Multi-query 비활성화 | -2~3초 | 검색 다양성 감소 |
| Re-ranking 비활성화 | -3~5초 | 검색 품질 저하 |
| retrieval_k 3→2 | -1~2초 | 컨텍스트 부족 |

---

## 다음 단계 권장사항

1. **4대보험 데이터 보강** → 품질 개선
2. **실사용 테스트** → 실제 환경에서 성능 검증
3. **목표 미달 시** → Multi-query 또는 Re-ranking 추가 최적화 검토

---

## 서버 실행

```bash
cd rag
..\.venv\Scripts\activate
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

**엔드포인트:**
- Swagger UI: http://localhost:8001/docs
- 채팅 API: POST /api/chat
- 스트리밍: POST /api/chat/stream
