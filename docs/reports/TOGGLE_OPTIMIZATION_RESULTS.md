# RAG Feature Toggle 최적화 테스트 결과

> 테스트 일시: 2026-02-12 17:57 KST
> 테스트 스크립트: `rag/evaluation/toggle_optimization.py`
> 결과 JSON: `rag/evaluation/results/toggle_optimization_20260212_175742.json`

---

## 1. 테스트 개요

### 목적
11개 토글 가능 기능의 최적 조합을 찾기 위한 체계적 테스트 수행.

### 방법
- **Phase 1**: 기본값(all defaults) 기준 Baseline 측정
- **Phase 2**: 개별 토글 영향 측정 (8개 ON→OFF, 3개 OFF→ON) + 벡터 가중치 4종 비교
- **평가 방식**: LLM 평가 (GPT-4o-mini, 100점 만점)
- **테스트 쿼리**: 6개 (도메인별 2개 — startup_funding, finance_tax, hr_labor)

### 테스트 쿼리

| 도메인 | 질문 |
|--------|------|
| startup_funding | 사업자등록 절차를 알려주세요 |
| startup_funding | 법인 설립 시 필요한 서류는 무엇인가요? |
| finance_tax | 부가세 신고 기한은 언제인가요? |
| finance_tax | 법인세 계산 방법을 알려주세요 |
| hr_labor | 퇴직금 계산 방법을 알려주세요 |
| hr_labor | 연차 휴가 발생 기준은? |

### 테스트 환경
- VectorDB: ChromaDB (4 컬렉션, 213,738 문서)
- CrossEncoder Reranking: 비활성 (torch meta tensor 이슈로 fallback)
- MySQL: 미연결 (하드코딩 기본값 사용)

---

## 2. 전체 결과 랭킹

| 순위 | 설정 | 평균 점수 | Baseline 대비 | 평균 응답 시간 |
|:---:|------|:---:|:---:|:---:|
| 1 | **weight=0.3 (BM25 heavy)** | **95.2** | **+1.0** | 57.9s |
| 2 | **Context Compression ON** | **95.0** | **+0.8** | 66.5s |
| 3 | BASELINE (모든 기본값) | 94.2 | — | 46.8s |
| 4 | Cross-Domain Rerank OFF | 93.7 | -0.5 | 41.9s |
| 5 | weight=0.5 (balanced) | 93.2 | -1.0 | 66.1s |
| 6 | Post-Eval Retry OFF | 92.3 | -1.8 | 61.8s |
| 7 | weight=0.7 (현재 기본값) | 91.7 | -2.5 | 67.5s |
| 8 | Dynamic K OFF | 91.5 | -2.7 | 75.0s |
| 9 | Action-Aware Generation OFF | 91.5 | -2.7 | 71.3s |
| 10 | Fixed Doc Limit OFF | 91.0 | -3.2 | 41.3s |
| 11 | Adaptive Search OFF | 91.0 | -3.2 | 58.6s |
| 12 | LLM Domain Classification ON | 91.0 | -3.2 | 64.6s |
| 13 | weight=0.9 (vector heavy) | 91.0 | -3.2 | 70.5s |
| 14 | Legal Supplement OFF | 87.5 | -6.7 | 47.6s |
| 15 | RAGAS Evaluation ON | 78.7 | -15.5 | 102.7s |
| 16 | Graduated Retry OFF* | 75.5 | -18.7 | 55.2s |

> *Graduated Retry OFF는 "퇴직금" 쿼리에서 `MainRouter` attribute 에러(기존 버그) 발생으로 0점 처리됨. 에러 제외 시 약 90.6점 추정.

---

## 3. 상세 분석

### 3-1. Baseline 대비 성능 향상 가능 (2개)

| 설정 | 변경 | 점수 차이 | 분석 |
|------|------|:---:|------|
| `VECTOR_SEARCH_WEIGHT=0.3` | 0.7 → 0.3 | **+1.0** | BM25 비중 증가가 한국어 키워드 매칭에 유리. 법률 용어/세무 용어 등 정확한 키워드 매칭이 중요한 도메인에서 효과적 |
| `ENABLE_CONTEXT_COMPRESSION=true` | OFF → ON | **+0.8** | 검색된 문서를 LLM으로 압축하여 노이즈 제거. 답변 품질 향상되나 응답 시간 +19.7s 증가 (LLM 호출 추가 비용) |

### 3-2. 절대 끄면 안 되는 기능 (Critical)

| 설정 | OFF 시 영향 | 분석 |
|------|:---:|------|
| `enable_legal_supplement` | **-6.7점** | 세무 질문("부가세 신고 기한")이 70점으로 급락. 법률 보충 검색 없이는 관련 법령 컨텍스트 부족 |
| `enable_graduated_retry` | **-18.7점*** | OFF 시 fallback 경로에서 `MainRouter.rag_chain` 참조 버그 발생. 버그 수정 필요하지만, 기능 자체도 품질에 기여 |

### 3-3. 끄면 품질 저하되는 기능 (Keep ON)

| 설정 | OFF 시 영향 | 분석 |
|------|:---:|------|
| `enable_fixed_doc_limit` | -3.2점 | OFF 시 문서 수 1개로 줄어드는 경우 발생 → 컨텍스트 부족 |
| `enable_adaptive_search` | -3.2점 | 검색 전략 자동 선택 비활성화 → 고정 전략 사용 |
| `enable_dynamic_k` | -2.7점 | 문서 수 동적 조절 비활성화 |
| `enable_action_aware_generation` | -2.7점 | 액션 추천(문서 생성, 지원사업 검색 등) 비활성화 |
| `enable_post_eval_retry` | -1.8점 | 평가 후 재시도 비활성화 → 저품질 답변 그대로 노출 |
| `enable_cross_domain_rerank` | -0.5점 | 복합 도메인 리랭킹 비활성화 (영향 적음) |

### 3-4. 켜지 말아야 할 기능

| 설정 | ON 시 영향 | 분석 |
|------|:---:|------|
| `enable_ragas_evaluation` | **-15.5점** | 첫 쿼리 타임아웃(300s), 응답 시간 2.2배 증가(102.7s). RAGAS LLM 설정 오류도 발생. 프로덕션 부적합, 오프라인 평가 전용 |
| `enable_llm_domain_classification` | -3.2점 | 벡터 분류 대비 이점 없음. 추가 LLM 비용만 발생 |

### 3-5. 벡터 가중치(Vector Search Weight) 비교

| 가중치 | 의미 | 점수 | 시간 |
|:---:|------|:---:|:---:|
| **0.3** | **BM25 70% + Vector 30%** | **95.2** | 57.9s |
| 0.5 | BM25 50% + Vector 50% | 93.2 | 66.1s |
| 0.7 | BM25 30% + Vector 70% (현재 기본값) | 91.7 | 67.5s |
| 0.9 | BM25 10% + Vector 90% | 91.0 | 70.5s |

**결론**: BM25 비중이 높을수록 점수가 높아지는 명확한 경향. 한국어 법률/세무 용어의 정확한 키워드 매칭이 벡터 유사도보다 효과적.

---

## 4. 쿼리별 상세 점수

### Baseline (기본 설정)

| 질문 | 점수 | 시간 | 감지 도메인 |
|------|:---:|:---:|:---:|
| 사업자등록 절차를 알려주세요 | 91 | 130.7s | startup_funding |
| 법인 설립 시 필요한 서류는 무엇인가요? | 95 | 28.2s | startup_funding |
| 부가세 신고 기한은 언제인가요? | 92 | 18.9s | finance_tax |
| 법인세 계산 방법을 알려주세요 | 92 | 26.7s | finance_tax |
| 퇴직금 계산 방법을 알려주세요 | 95 | 37.7s | hr_labor |
| 연차 휴가 발생 기준은? | 100 | 38.7s | hr_labor |
| **평균** | **94.2** | **46.8s** | |

### Legal Supplement OFF (가장 큰 품질 저하)

| 질문 | 점수 | Baseline 대비 | 시간 |
|------|:---:|:---:|:---:|
| 사업자등록 절차를 알려주세요 | 90 | -1 | 186.0s |
| 법인 설립 시 필요한 서류는 무엇인가요? | 91 | -4 | 26.8s |
| **부가세 신고 기한은 언제인가요?** | **70** | **-22** | 12.0s |
| 법인세 계산 방법을 알려주세요 | 87 | -5 | 14.0s |
| 퇴직금 계산 방법을 알려주세요 | 95 | 0 | 23.9s |
| 연차 휴가 발생 기준은? | 92 | -8 | 23.0s |
| **평균** | **87.5** | **-6.7** | |

> 부가세 질문이 70점으로 급락 — 법률 보충 검색이 세무 관련 법령 컨텍스트를 제공하는 핵심 역할 수행

### weight=0.3 (최고 점수)

| 질문 | 점수 | Baseline 대비 | 시간 |
|------|:---:|:---:|:---:|
| 사업자등록 절차를 알려주세요 | 95 | +4 | 188.4s |
| 법인 설립 시 필요한 서류는 무엇인가요? | 94 | -1 | 24.8s |
| 부가세 신고 기한은 언제인가요? | 100 | +8 | 27.3s |
| 법인세 계산 방법을 알려주세요 | 90 | -2 | 28.2s |
| 퇴직금 계산 방법을 알려주세요 | 92 | -3 | 31.2s |
| 연차 휴가 발생 기준은? | 100 | 0 | 47.7s |
| **평균** | **95.2** | **+1.0** | |

---

## 5. 최적 설정 권장안

### 프로덕션 권장 설정

```env
# ===== 변경 권장 (Baseline 대비 +1~2점 향상 기대) =====
VECTOR_SEARCH_WEIGHT=0.3              # BM25 heavy (기본 0.7 → 0.3)
ENABLE_CONTEXT_COMPRESSION=true       # 컨텍스트 압축 ON (기본 OFF → ON)

# ===== 반드시 ON 유지 =====
ENABLE_FIXED_DOC_LIMIT=true           # OFF 시 -3.2점
ENABLE_CROSS_DOMAIN_RERANK=true       # OFF 시 -0.5점
ENABLE_LEGAL_SUPPLEMENT=true          # OFF 시 -6.7점 (Critical)
ENABLE_ADAPTIVE_SEARCH=true           # OFF 시 -3.2점
ENABLE_DYNAMIC_K=true                 # OFF 시 -2.7점
ENABLE_POST_EVAL_RETRY=true           # OFF 시 -1.8점
ENABLE_GRADUATED_RETRY=true           # OFF 시 에러 발생 (Critical)
ENABLE_ACTION_AWARE_GENERATION=true   # OFF 시 -2.7점

# ===== 반드시 OFF 유지 =====
ENABLE_RAGAS_EVALUATION=false         # ON 시 -15.5점, 타임아웃 발생
ENABLE_LLM_DOMAIN_CLASSIFICATION=false # ON 시 -3.2점, 추가 비용만 발생
```

### 비용 절감 설정 (품질 소폭 하락 허용 시)

```env
VECTOR_SEARCH_WEIGHT=0.3
ENABLE_CONTEXT_COMPRESSION=false      # LLM 호출 1회 절감 (응답 시간 -20s)
ENABLE_POST_EVAL_RETRY=false          # 재시도 비활성화 (비용 절감, -1.8점)
ENABLE_CROSS_DOMAIN_RERANK=false      # 단일 도메인 환경 (-0.5점)
```

---

## 6. 알려진 이슈

| 이슈 | 영향 | 상태 |
|------|------|------|
| CrossEncoder 모델 로딩 실패 (torch meta tensor) | Reranking이 원본 순서 유지로 fallback. 실제 reranking 활성화 시 점수 추가 향상 가능 | 미해결 |
| Graduated Retry OFF 시 `MainRouter.rag_chain` 에러 | fallback 경로 버그. 특정 쿼리에서 0점 처리 | 수정 필요 |
| RAGAS Evaluation 첫 쿼리 타임아웃 (300s) | 전체 처리 시간 초과로 score=0 | RAGAS는 오프라인 전용 |
| BM25 cold start | 각 설정 변경 후 첫 쿼리에서 BM25 인덱스 재빌드 (130~300s) | 정상 동작 |

---

## 7. 후속 작업

- [ ] `VECTOR_SEARCH_WEIGHT=0.3` + `ENABLE_CONTEXT_COMPRESSION=true` 조합 테스트 (개별 효과가 합산되는지 확인)
- [ ] CrossEncoder reranking 정상화 후 재테스트 (점수 추가 향상 기대)
- [ ] Graduated Retry OFF 시 `MainRouter.rag_chain` 버그 수정
- [ ] 더 많은 쿼리(30개 벤치마크 전체)로 재검증
- [ ] `.env` 파일에 최적 설정 반영
