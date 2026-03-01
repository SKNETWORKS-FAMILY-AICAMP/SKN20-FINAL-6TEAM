# RAG 개선 계획 (v2)

> 작성일: 2026-03-01 (v1) / 수정일: 2026-03-01 (v2)<br>
> 기준: RAGAS 4-State 평가 결과 (80문항, eval_0301)<br>
> 목표: Faithfulness 0.60+, Context Recall 0.50+, 거부 정확도 100%, 타임아웃 0건

---

## 1. 현황 분석

### 1.1 현재 성능 수치 (State D, 현재 main)

| 메트릭 | 점수 | 목표 | 갭 |
|--------|------|------|-----|
| Faithfulness | 0.4577 | 0.60 | -0.14 |
| Answer Relevancy | 0.5812 | 0.65 | -0.07 |
| Context Precision | 0.5343 | 0.60 | -0.07 |
| Context Recall | 0.3558 | 0.50 | -0.14 |
| Context F1 | 0.4272 | 0.55 | -0.12 |
| 거부 정확도 | 70% (7/10) | 100% | -30% |
| 타임아웃 | 2건 | 0건 | -2건 |

### 1.2 4-State 추이 핵심 관찰

1. **VectorDB 개선(A→B)이 가장 효과적**: Faithfulness +0.14, CR +0.07, CP +0.06
2. **RAG 파이프라인 개선(B→D)은 트레이드오프**: CP +0.01, CR +0.00 vs Faithfulness -0.04
3. **거부 정확도 퇴행**: B(100%) → C(80%) → D(70%)
4. **타임아웃 신규 발생**: State A/B에서는 없던 S03, T02 타임아웃이 C/D에서 발생

### 1.3 핵심 문제점 (코드 레벨)

#### 문제 1: Context Recall 낮음 (0.3558)
- `retrieval_agent.py` SearchStrategySelector가 쿼리 특성에 따라 K=3~7로 제한
- `search.py` HybridSearcher가 `fetch_k = k * 3`으로 후보 풀이 제한적
- BM25 토크나이저(kiwipiepy 기반)가 복합명사 분리 부족 (예: "통신판매업신고" → 단일 토큰)
- startup 도메인 CP=0.2244 (최저): 관련 문서가 분산되고 시의성이 낮음

#### 문제 2: Faithfulness 하락 (B: 0.4950 → D: 0.4577)
- `prompts.py`의 "자체 지식 사용 금지" 지시가 프롬프트 하단에 위치 → LLM이 생성 완료 후 검증 건너뜀
- `enable_context_compression=False` 기본값 → 관련 없는 문서 내용이 noise로 작용
- `generation_max_tokens=2048`로 불필요한 부연 설명 허용

#### 문제 3: 거부 실패 (R02 주식투자, R03 부동산투자, R08 앱개발)
- `domain_classifier.py`의 `_keyword_classify()`에서 "투자" 키워드가 startup_funding과 부분 매칭
- LLM 분류 모드(`ENABLE_LLM_DOMAIN_CLASSIFICATION`)에서도 경계 케이스 few-shot 예시 부족
- **현재 구조**: LLM 분류 → 키워드 오버라이드 guardrail → rejection (이미 존재)
- **실제 원인**: LLM 분류 프롬프트의 경계 케이스(주식투자/창업투자, 앱개발/연구개발) 예시 부재

#### 문제 4: 타임아웃 (S03, T02)
- **BM25 사전 빌드는 이미 구현됨** (`rag/utils/chromadb_warmup.py`의 `warmup_chromadb()` — Phase 2에서 4개 도메인 병렬 빌드)
- **실제 원인**: GraduatedRetryHandler의 다단계 재시도(L1→L2→L3) 누적 시간 + LLM 처리 복잡도
- **원래 의도**: GraduatedRetryHandler는 "답변 평가 FAIL 시 재시도"용이었으나, 검색 실패 시에도 개입하면서 타임아웃 유발
- TOTAL_TIMEOUT=300초 안에서 재시도 누적이 핵심 병목

---

## 2. 사전 조사 결과 반영 사항

### 2.1 Semantic Chunking vs Contextual Retrieval — 명확한 차이

두 기법은 **완전히 다른 레이어**에서 동작한다.

| 기법 | 동작 레이어 | 핵심 동작 |
|------|-----------|-----------|
| **Semantic Chunking** | 청킹 단계 | 문장 임베딩 유사도 기반으로 분할점 결정 (고정 문자 수 → 의미 단위) |
| **Contextual Retrieval** | 임베딩 전 처리 | 청크는 그대로 두고, 각 청크에 문서 맥락 설명 prefix만 추가 |

**Semantic Chunking 판단** (arxiv 2410.13070, Vectara 연구):
- 고정 청크 대비 통계적으로 유의미한 개선이 없음
- 오히려 의미 경계가 불명확한 법령 데이터에서 청크 품질이 저하될 수 있음
- **사용자 의견 맞음** → 고려하지 않음

**Contextual Retrieval 판단** (Anthropic 연구):
- Semantic Chunking과 달리 기존 청크를 건드리지 않음
- 실패 검색 49% 감소, reranking 병행 시 67% 감소 (Anthropic 측정)
- 벡터DB 재빌드 필요하지만 청크 크기/구조는 유지
- **사용자 우려와 무관** → P2-2로 유지

### 2.2 Adaptive RAG vs Agentic RAG — 기술적 차이

| 구분 | Adaptive RAG | Agentic RAG |
|------|-------------|-------------|
| **핵심** | 질문 복잡도/유형 → 검색 파이프라인 라우팅 | LLM이 도구(검색, 계산, 코드 실행)를 자율적으로 선택/실행 |
| **의사결정자** | 규칙/분류기 (미리 정의된 분기) | LLM 자체 (ReAct/ToT 방식) |
| **현재 시스템** | `SearchStrategySelector`로 이미 일부 구현 | `GraduatedRetryHandler` + 멀티에이전트 구조로 이미 구현 |
| **확장 방향** | 생성 전략까지 Adaptive 확장 | LLM이 검색 쿼리를 직접 수립하도록 확장 |

**현재 시스템 분류**: Agentic RAG (에이전트별 도메인 분리 + 단계적 도구 선택)에 Adaptive 요소(검색 전략 선택)가 혼합된 형태

**사용자 의견에 대한 판단**: "도메인 탐색을 Agentic하게"의 방향은 **LLM이 검색 쿼리를 직접 수립**하는 것. 현재 `SearchStrategySelector`는 규칙 기반이므로, LLM이 직접 어떤 도메인을 어떤 쿼리로 검색할지 결정하는 방식으로 확장하는 것이 핵심.

### 2.3 HyDE — 현재 시스템에서의 적합성

HyDE(Hypothetical Document Embedding):
- TREC DL-20에서 nDCG@10 기준 기존 대비 +38% 개선
- 단, **추가 LLM 호출 1회 필요** → 응답시간 +2~5초
- 타임아웃이 이미 발생하는 S03, T02 케이스에서 역효과 가능성
- **판단**: 타임아웃 문제 해결 후 제한적으로 도입 (복잡한 멀티도메인 쿼리에만)

### 2.4 GraduatedRetryHandler — 재시도 vs K값 완화

**코드 확인 결과**: GraduatedRetryHandler Level 0~4 완전 구현됨
- L1 `RELAX_PARAMS`: K 증가 + 평가 기준 완화
- L2 `MULTI_QUERY`: 멀티쿼리 강화 + 공통법령 DB 포함
- L3 `CROSS_DOMAIN`: 인접 도메인 추가 검색
- L4 `PARTIAL_ANSWER`: 포기 후 현재 결과 반환

**사용자 의도 확인**: 재시도 원래 목적은 "답변 평가 FAIL 시 MULTI_QUERY 시도". 검색 실패 시 재시도는 부수 동작.

**판단**: 사용자 의견 맞음. 재시도보다 첫 시도의 K값을 높이는 것이 더 효율적. 단, 재시도를 완전히 제거하면 품질 저하 가능. → max_retry_level을 L1(K값 완화)로 하향 후 실험.

### 2.5 Chain-of-Thought 검증 현황

**코드 확인 결과**: `prompts.py`에 "자체 검증" 지시는 있지만, **실제 검증 로직은 없음**.
- LLM에게 "검증하세요"라고 지시하는 것과 실제 코드 레벨 검증은 다름
- 사용자 "이미 되어있는 것 같다"는 오해였음

### 2.6 Parent-Child 검색 구조 현황

**코드 확인 결과**: 미구현. ChromaDB에 평탄 구조(4개 독립 컬렉션). parent_id 메타데이터 없음.
- 사용자 "비슷한게 되어있는 것 같다"는 오해였음
- 현재는 도메인별 예산 할당(`DocumentBudget`) 방식으로 대체

### 2.7 리랭커 업그레이드 (RunPod Serverless 고려)

| 모델 | 파라미터 | 한국어 | 추론 시간(CPU) | RunPod 영향 |
|------|---------|--------|--------------|------------|
| bge-reranker-base | 278M | 제한적 | ~0.3s | 현재 |
| bge-reranker-v2-m3 | 568M | 완전 지원 | ~0.5s | GPU 메모리 2배, cold start 증가 |

- **한국어 RAG에서 v2-m3가 실질적 품질 개선** (임베딩 모델 bge-m3와 같은 패밀리 → 정합성)
- RunPod Serverless cold start 시간 증가 우려 → 실제 측정 후 결정 필요
- **판단**: 기능적으로 맞지만, 타임아웃 해결 전 도입 시 역효과 가능. Phase 2 후반에 검증.

---

## 3. 개선 계획

### Phase 1: 즉시 적용 (1-2일)

#### P1-1. 거부 정확도 100% 복원 — LLM 분류 프롬프트 개선

**파일**: `rag/utils/prompts.py` (`LLM_DOMAIN_CLASSIFICATION_PROMPT`)

> **판단 근거**: 도메인 분류는 LLM 기반(`ENABLE_LLM_DOMAIN_CLASSIFICATION`)으로 사용하기로 결정됨.
> 현재 프롬프트에 경계 케이스 few-shot 예시가 부족한 것이 근본 원인.
> 키워드 방식 수정은 fallback에만 적용.

**변경 내용**:
1. `LLM_DOMAIN_CLASSIFICATION_PROMPT`에 few-shot 경계 케이스 예시 추가:
   ```
   # 거부 케이스 (명시적 예시)
   "주식 시장에서 어떤 종목에 투자하면 좋을까요?" → rejection  (주식투자 ≠ 창업투자)
   "강남 아파트 지금 매수해야 할까요?" → rejection           (부동산투자 ≠ 사업자 부동산)
   "스마트폰 앱을 직접 개발하고 싶습니다" → rejection         (IT 개발 학습 ≠ 사업 개발)
   "마라톤 훈련 계획 알려주세요" → rejection

   # 경계 케이스 (도메인 분류)
   "창업 자금 투자 유치 방법" → startup_funding              (투자유치 = 창업)
   "연구개발 비용 세액공제" → finance_tax                    (R&D = 세무)
   ```
2. 명시적 rejection 출력 형식 강제: `"rejection"` 토큰으로 고정
3. 신뢰도 낮은 경우 vector fallback 위임 지시 추가

**예상 효과**: 거부 정확도 70% → 100% (R02, R03, R08 해결)

#### P1-2. Faithfulness 개선 — 프롬프트 구조 강화

**파일**: `rag/utils/prompts.py`

**변경 내용**:
1. "자체 지식 사용 금지" 규칙을 각 도메인 프롬프트 **최상단**으로 이동:
   - 현재: 프롬프트 하단 "자체 검증" 섹션
   - 변경: `## 핵심 규칙 (반드시 준수)` 섹션을 프롬프트 첫 번째 섹션으로 배치
   - 근거: LLM은 프롬프트 초반 지시를 더 충실히 따르는 경향
2. `generation_max_tokens` 2048 → 1024로 축소:
   - 현재 프롬프트 지시("800자 이내")와 일치
   - 불필요한 부연 설명 차단 → hallucination 감소
3. `ENABLE_CONTEXT_COMPRESSION` 환경변수 현황 확인 및 활성화 검토:
   - 현재 기본값 `False` — `.env` 설정 확인 후 `True` 전환
   - 관련 없는 문서 내용 noise 제거

**예상 효과**: Faithfulness +0.05~0.08

#### P1-3. 타임아웃 완화 — 재시도 전략 재설계

**파일**: `rag/agents/retrieval_agent.py`, `rag/utils/config/settings.py`

> **판단 근거**:
> - BM25 사전 빌드는 이미 `chromadb_warmup.py`에 구현됨 → 이 방향은 이미 완료
> - 실제 원인: GraduatedRetryHandler 다단계 재시도 누적 시간
> - 사용자 의도대로 "재시도보다 첫 시도에서 더 많은 문서"가 올바른 방향
> - 재시도는 "답변 평가 FAIL 시에만" 작동해야 함

**변경 내용**:
1. `max_retry_level` 기본값을 `L2(MULTI_QUERY)` → `L1(RELAX_PARAMS)`로 하향:
   - L1: K 증가 + 평가 기준 완화만 허용
   - L2(MULTI-QUERY) 이상: 답변 평가 FAIL이 명시적으로 발생한 경우에만 진입
2. 초기 K값 상향: `retrieval_k` 기본값 4 → 6으로 증가:
   - 재시도에 쓰던 시간을 첫 시도에서 더 많은 문서로 대체
3. `TOTAL_TIMEOUT` 300 → 120초 (스트리밍 첫 토큰 기준):
   - 완전한 답변을 기다리기보다 부분 답변을 빠르게 반환하는 방향 검토

**예상 효과**: S03, T02 타임아웃 해소 또는 대기 시간 단축

---

### Phase 2: 중기 개선 (3-5일)

#### P2-1. Agentic 도메인 탐색 — LLM 검색 쿼리 자율 수립

> **Adaptive RAG vs Agentic RAG 정리**:
> - **Adaptive RAG**: 규칙/분류기가 파이프라인을 라우팅 (현재 `SearchStrategySelector`)
> - **Agentic RAG**: LLM이 직접 어떤 도메인을, 어떤 쿼리로 검색할지 결정
> - 사용자가 원하는 "Agentic하게"는 **LLM이 검색 전략을 자율적으로 수립**하는 것
> - 현재 시스템은 이미 Agentic 구조(멀티에이전트)이나, 검색 전략 결정은 규칙 기반

**파일**: `rag/agents/retrieval_agent.py`, `rag/utils/prompts.py`

**변경 내용**:
1. `SearchStrategySelector`를 LLM 기반으로 전환:
   - 현재: 규칙 기반 (쿼리 길이, 키워드 등으로 HYBRID/VECTOR_HEAVY/BM25_HEAVY 결정)
   - 변경: LLM이 쿼리를 분석하고 어떤 도메인에서 어떤 검색 전략으로 찾을지 직접 결정
2. 검색 계획 수립 프롬프트 추가:
   ```
   질문을 분석하여 검색 계획을 세우세요:
   - 필요한 도메인 목록
   - 각 도메인에서 사용할 핵심 검색 키워드
   - 예상 문서 수
   ```
3. 계획 기반 병렬 검색 실행 후 통합

**예상 효과**: Context Recall +0.05~0.10 (특히 복합 도메인), 검색 정밀도 향상

#### P2-2. Contextual Retrieval — 청크별 문맥 prefix 주입

> **Semantic Chunking과의 차이**:
> - Semantic Chunking: 청킹 방식 자체를 변경 (데이터 품질 저하 위험 → 적용 안 함)
> - Contextual Retrieval: 청크 크기/구조 유지, prefix 텍스트만 추가 (전혀 다른 기법)
>
> **적용 방향**: 벡터DB 재빌드 필요하지만 chunk_size=1500 구조 유지

**파일**: `scripts/vectordb/__main__.py`, 벡터DB 빌드 스크립트

**변경 내용**:
1. 벡터DB 빌드 시 각 청크에 contextual prefix 주입:
   - 법령류: `[법령명 > 조항] ` prefix (메타데이터에서 자동 추출, LLM 불필요)
   - 기타: `[파일명 > 섹션제목] ` prefix
   - 예: `"[근로기준법 > 제60조] 연차 유급휴가: 사용자는 1년간..."`
2. BM25 인덱스도 prefix 포함 텍스트로 재빌드

**근거**: Anthropic 연구 — 실패 검색 49% 감소, reranking 병행 시 67% 감소
**예상 효과**: Context Recall +0.08~0.12, Context Precision +0.05
**전제조건**: 벡터DB 재빌드 (1회성 작업)

#### P2-3. Context Recall 개선 — Parent-Child 검색 (검토 필요)

> **현황 확인**: `chroma.py`에 Parent-Child 구조 없음. 평탄 구조(4개 독립 컬렉션).
> 사용자 "비슷한게 되어있는 것 같다"는 오해였음.

**개념**: 작은 청크로 정밀 검색 → 해당 청크의 부모(더 큰 맥락) 문서를 LLM에 전달

| 역할 | 청크 크기 | 용도 |
|------|---------|------|
| 검색용 child | 500자 | 정밀 매칭 |
| 생성용 parent | 2000자 | 맥락 보존 |

**구현 계획**:
1. 벡터DB 빌드 시 `parent_id` 메타데이터 추가
2. 검색 결과 → parent_id로 원본 청크 조회 → LLM에 전달
3. `chroma.py`에 `get_parent_document()` 추가

**우선순위**: P2-2(Contextual Retrieval)와 벡터DB 재빌드 시 함께 적용 권장
**예상 효과**: Context Recall +0.05~0.08

#### P2-4. HyDE — 복잡한 쿼리 한정 적용

> **HyDE 판단**: 한국어 RAG에서 효과 있지만 추가 LLM 호출(+2~5초)이 필요.
> 타임아웃이 해결된 이후, 복잡한 멀티도메인 쿼리에만 선별 적용.

**파일**: 신규 `rag/utils/hyde.py`, `rag/agents/retrieval_agent.py`

**구현 계획**:
1. `HyDERetriever` 클래스:
   - 쿼리 → LLM이 가상 답변 문서 생성 (temperature=0.0, max_tokens=200)
   - 가상 문서 임베딩으로 벡터 검색
   - 원본 쿼리 검색 결과와 RRF 융합
2. 적용 조건: `is_multi_domain=True` + `ENABLE_HYDE=true` 환경변수

**예상 효과**: Context Recall +0.05~0.10 (복잡한 멀티도메인 쿼리)
**전제조건**: P1-3 타임아웃 해결 완료 후 적용

#### P2-5. 리랭커 업그레이드 — RunPod Serverless 환경 고려

> **RunPod Serverless 환경 판단**:
> - bge-reranker-v2-m3: 568M 파라미터, 한국어 완전 지원, bge-m3와 같은 패밀리 → 품질 개선 예상
> - 단, GPU 메모리 약 2배, cold start 시간 증가 우려
> - 타임아웃이 이미 발생하는 상황에서 지연 추가는 역효과
> **권장**: P1-3 타임아웃 해결 완료 + 실제 RunPod 환경에서 지연 측정 후 결정

**파일**: `rag/utils/reranker.py`, RunPod 배포 설정

**변경 내용** (검증 후 적용):
1. `BAAI/bge-reranker-base` → `BAAI/bge-reranker-v2-m3` 교체
2. rerank candidate pool 확대: 입력 `k*4`개 → 상위 `k`개 반환
3. RunPod cold start 시간 측정 필수 (목표: 추가 지연 < 1초)

**예상 효과**: Context Precision +0.03~0.05 (한국어 reranking 정확도 향상)

---

### Phase 3: 장기 (필요 시)

#### P3-1. GraphRAG

> **판단**: 기한 부족으로 현재 구현 불가. 제외.

#### P3-2. ColBERT 3-Way Hybrid Search

> **개념 설명 (사용자 요청)**:
> - 현재: BM25(키워드) + Dense(의미) = 2-way hybrid → RRF 융합
> - ColBERT: 쿼리의 각 토큰과 문서의 각 토큰을 **개별적으로** 비교 (MaxSim 연산)
>   - 기존 CrossEncoder: `(query, doc)` 쌍 전체를 한 번에 처리
>   - ColBERT: 토큰별 최대 유사도 합산 → 더 세밀한 키워드 매칭
> - 한국어 지원: JaColBERT (일본어 기반, 한국어 부분 지원) 또는 한국어 ColBERT 파인튜닝 필요
>
> **효과/리스크**:
> - 예상 효과: Context Precision +0.05~0.08
> - 리스크: 추가 모델 로딩(VRAM), ColBERT 한국어 성능 미검증, RunPod 추가 비용
> - **권장**: Phase 3에서 소규모 PoC 후 결정

#### P3-3. Adaptive RAG 생성 전략 확장

현재 Adaptive 요소(`SearchStrategySelector`)를 **생성 단계까지 확장**:
- 단순 사실형 질문 → 간결한 생성 (max_tokens=512)
- 복합 절차형 질문 → 단계별 생성 (max_tokens=1024 + 번호 목록 형식)
- 멀티도메인 → 현재 `MULTI_DOMAIN_SYNTHESIS_PROMPT` 유지

> P2-1(Agentic 검색 전략)과 연계하여 개발

---

## 4. 프롬프트 개선 (P1-2 상세)

### 4.1 즉시 적용

1. **"자체 지식 사용 금지" 최상단 배치** — P1-2에 포함

2. **답변 길이 하드 제한**:
   - 현재: "800자 이내" (소프트 제한)
   - 변경: max_tokens=1024로 하드 제한 (프롬프트 지시와 코드 설정 일치)

3. **인용 형식**: 현재 방식 유지 (법령 외에도 인용 필요 — 사용자 의견 맞음)

### 4.2 중기 적용

1. **Few-shot 예시 추가**: 각 도메인 프롬프트에 "좋은 답변 예시" 1개 포함

2. **Chain-of-Thought 검증 강화**:
   > 현재 prompts.py에 "자체 검증" 지시는 있지만 실제 코드 레벨 검증 없음.
   > "이미 되어있는 것" 아님 — LLM에 지시하는 것과 코드 검증은 다름.

   - 생성된 답변의 각 문장에 대해 "이 내용이 참고자료 [번호]에 있는가?" 자가 검증 지시 강화
   - 코드 레벨: 답변의 숫자/날짜/법령명을 검색 문서와 대조하는 후처리 추가 (Fact-Check)

---

## 5. 데이터 품질 개선

### 5.1 도메인별 문서 보강

| 도메인 | 현재 CP | 문제 | 개선안 |
|--------|---------|------|--------|
| startup_funding | 0.2244 (최저) | 절차 문서 분산, 시의성 낮음 | 창업진흥원 2024~2025 최신 가이드 추가 |
| finance_tax | 0.5833 | 세법 조문이 길어 맥락 유실 | 조문별 메타데이터(법명, 조항번호) 강화 |
| hr_labor | 0.5952 | 해석례 Q&A 부족 | 고용노동부 해석례 데이터 추가 |
| law_common | 0.6111 | 양호 | 판례 요약 데이터 보강 |

### 5.2 청킹 전략

- **Semantic Chunking**: 적용 안 함 (데이터 품질 저하 — 사용자 판단 맞음)
- **현재 고정 청크 유지**: chunk_size=1500, chunk_overlap=150
- **개선**: P2-2 Contextual Retrieval prefix + P2-3 Parent-Child 구조로 보완

---

## 6. 응답속도 개선

### 6.1 현재 병목 분석

| 단계 | 예상 소요시간 | 병목 요인 |
|------|-------------|-----------|
| 도메인 분류 (LLM) | 1~3초 | LLM 호출 (현재 키워드 fallback은 0.1초) |
| 질문 분해 | 1~2초 | LLM 호출 (복합 도메인만) |
| 검색 | 2~5초 | 병렬 도메인 검색 + reranking |
| 생성 | 4~8초 | LLM 호출 (max_tokens=2048) |
| 평가+재시도 | 2~5초 | LLM 평가 + 재시도 시 추가 검색 |
| **합계** | **10~23초** | |

### 6.2 개선 전략

1. **LLM 평가 처리 방식**:
   > 사용자 의견: "답변 품질을 높이기 위해 재시도 필요"
   > 판단: 맞음. 단, 재시도가 타임아웃 원인이므로 조건 강화

   - 평가 FAIL 시 재시도 1회만 허용 (max_retry_level=L1)
   - 재시도 후에도 FAIL이면 현재 답변 반환 + 로그 기록

2. **병렬 검색 후 ReRank**:
   > 사용자 질문: "병렬 검색에서 각 도메인별 찾은 문서를 ReRank에 적용 가능한가?"
   > 답변: 가능하며 이미 RRF 융합 후 CrossEncoder ReRank 파이프라인이 구현됨.
   > 단, 각 도메인별 중간 ReRank → 도메인 간 RRF 융합 → 최종 ReRank의 2단계 구조로 개선 가능.

3. **generation_max_tokens 축소**: 2048 → 1024 (P1-2에 포함)

4. **스트리밍 우선 반환**: 첫 토큰 출력 목표 5초 이내

**목표**: 첫 토큰 출력 평균 10초 이내 (현재 추정 15~20초)

---

## 7. 거부 정확도 개선 (P1-1 상세)

### 7.1 실패 케이스 분석

| 케이스 | 질문 | 원인 | 해결 방향 |
|--------|------|------|----------|
| R02 | "주식 시장 불안정, 어떤 종목에 투자?" | LLM이 "투자" → startup_funding으로 분류 | 거부 few-shot 예시 추가 |
| R03 | "강남구 아파트 매수?" | LLM이 "매수", "가격" → finance_tax 분류 | 거부 few-shot 예시 추가 |
| R08 | "스마트폰 앱 개발, 프로그래밍 배우기" | LLM이 "개발" → startup/hr 분류 | 거부 few-shot 예시 추가 |

### 7.2 해결 전략

**LLM 분류 프롬프트 개선이 핵심** (키워드 방식 수정은 fallback 범위에서만):
1. 거부 케이스 few-shot 예시 5개 이상 추가 (P1-1)
2. 경계 케이스 구분 명시 (주식투자 ≠ 창업투자 등)
3. 거부 시 유사 비즈니스 서비스 안내 제공 개선

---

## 8. 우선순위 및 예상 효과 요약

| 순위 | 태스크 | Phase | 예상 효과 | 난이도 | 비고 |
|------|--------|-------|-----------|--------|------|
| 1 | **P1-1. LLM 분류 프롬프트 개선** | Phase 1 | 거부 100% 복원 | 낮음 | `prompts.py`만 수정 |
| 2 | **P1-2. 프롬프트 강화 + max_tokens 축소** | Phase 1 | Faith +0.05~0.08, 속도 개선 | 낮음 | `prompts.py` + settings |
| 3 | **P1-3. 재시도 전략 재설계** | Phase 1 | 타임아웃 해소, 속도 개선 | 중간 | `retrieval_agent.py` |
| 4 | **P2-1. Agentic 도메인 탐색 (LLM 검색 전략)** | Phase 2 | CR +0.05~0.10, CP 향상 | 중간 | 신규 로직 |
| 5 | **P2-2. Contextual Retrieval** | Phase 2 | CR +0.08~0.12 | 중간 | 벡터DB 재빌드 필요 |
| 6 | **P2-3. Parent-Child 검색** | Phase 2 | CR +0.05~0.08 | 중간 | P2-2와 함께 |
| 7 | **P2-5. 리랭커 업그레이드** | Phase 2 후반 | CP +0.03~0.05 | 낮음 | 타임아웃 해결 후 |
| 8 | **P2-4. HyDE** | Phase 2 후반 | CR +0.05~0.10 | 중간 | 타임아웃 해결 후 |
| 9 | P3-2. ColBERT PoC | Phase 3 | CP +0.05~0.08 | 높음 | 한국어 지원 검증 필요 |

### Phase 1 완료 시 예상 성능

| 메트릭 | 현재 (D) | Phase 1 후 예상 | 변화 |
|--------|---------|----------------|------|
| Faithfulness | 0.4577 | 0.51~0.54 | +0.05~0.08 |
| Context Recall | 0.3558 | 0.36~0.38 | +0.00~0.02 |
| Context Precision | 0.5343 | 0.54~0.55 | +0.01 |
| 거부 정확도 | 70% | **100%** | +30% |
| 타임아웃 | 2건 | **0건** | -2건 |

### Phase 1+2 완료 시 예상 성능

| 메트릭 | 현재 (D) | Phase 2 후 예상 | 변화 |
|--------|---------|----------------|------|
| Faithfulness | 0.4577 | 0.58~0.65 | +0.12~0.19 |
| Context Recall | 0.3558 | 0.45~0.52 | +0.09~0.16 |
| Context Precision | 0.5343 | 0.58~0.62 | +0.05~0.09 |
| Context F1 | 0.4272 | 0.51~0.57 | +0.08~0.14 |

---

## 9. 이미 적용된 사항 (중복 제안 금지)

- [x] chunk_size 800 → 1500 확대 (State B)
- [x] 하이브리드 검색 (BM25 + Vector + RRF) 도입
- [x] CrossEncoder 리랭킹 (BAAI/bge-reranker-base)
- [x] 도메인 거부 기능 (`REJECTION_RESPONSE`)
- [x] 단계적 재시도 GraduatedRetryHandler (L0~L4)
- [x] Multi-Query Retriever (L2 재시도 내)
- [x] 적응형 검색 모드 (SearchStrategySelector) — 규칙 기반
- [x] 동적 K값 (DocumentBudgetCalculator)
- [x] 법률 보충 검색 (legal_supplement)
- [x] 멀티턴 쿼리 재작성 (query_rewriter)
- [x] 복합 도메인 질문 분해 (QuestionDecomposer)
- [x] BM25 인덱스 사전 빌드 (chromadb_warmup.py)
- [x] LLM 기반 도메인 분류 (ENABLE_LLM_DOMAIN_CLASSIFICATION)
- [x] 멀티에이전트 구조 (Agentic RAG 기반)
- [x] 액션 선제안 (ACTION_HINT_TEMPLATE)
- [x] LLM 평가 + 재시도 (evaluator + post_eval_retry)

---

*v2 수정사항: BM25 사전 빌드 이미 구현 확인 / CoT 미구현 확인 / Parent-Child 미구현 확인 / Semantic Chunking 제외 근거 추가 / Adaptive vs Agentic RAG 차이 명확화 / HyDE 후순위 이동 / 리랭커 업그레이드 RunPod 고려 / 거부 개선 방향을 LLM 프롬프트로 전환*

*참고 문헌: arxiv 2410.13070 (Semantic Chunking), Anthropic Contextual Retrieval, arxiv 2501.09136 (Agentic RAG Survey), BAAI bge-reranker-v2-m3 HuggingFace, arxiv 2410.14567 (ELOQ OOS Detection)*
