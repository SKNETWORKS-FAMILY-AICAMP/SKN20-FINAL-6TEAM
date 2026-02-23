# RAG Feature Toggle 현황 분석 및 프로덕션 준비 계획

## Context

팀원이 RAG 서비스의 기능 토글 분류 가이드(`message.txt`)를 공유. 29개 기능을 4개 카테고리(항상 ON / 필수 ON / 토글 ON / 토글 OFF)로 정리한 문서.
3개 에이전트가 현재 프로젝트 코드베이스를 감사(audit)한 결과를 종합하여 방향성을 도출.

---

## 에이전트 회의 결과 요약

### 좋은 소식: 구현은 100% 완료

| 항목 | 결과 |
|------|------|
| 토글 가능 기능 19개 | **19/19 구현 완료** (config.py에 모두 존재, 코드에서 사용 중) |
| 항상 ON 기능 10개 | **10/10 구현 완료** (숨겨진 토글 없음, 진짜 항상 활성) |
| 기본값 일치 | **19/19 일치** (message.txt 권장값 = 코드 기본값) |

### 문제점 3가지

| # | 문제 | 영향 |
|---|------|------|
| 1 | **벡터DB 비어있음** (`rag/vectordb/` 빈 디렉토리) | RAG 서비스 작동 불가, CLI 테스트 불가, 데모 불가 |
| 2 | **.env에 6/19만 명시** (13개가 코드 기본값에 숨어있음) | 팀원이 설정 전체를 파악 못함, 실수로 기본값 변경 위험 |
| 3 | **문서 누락** (CLAUDE.md에 11개만, RetrievalAgent 7개 누락) | 고급 검색 설정을 아무도 모름 |

---

## 실행 계획

### Step 1: .env 파일 완전성 확보 (15분)

**파일**: `.env`

누락된 13개 변수를 카테고리별 주석과 함께 추가:

```env
# ===== RAG Core (Must-have ON) =====
ENABLE_HYBRID_SEARCH=true          # (이미 있음)
VECTOR_SEARCH_WEIGHT=0.7           # (이미 있음)
ENABLE_RERANKING=true              # (이미 있음)
ENABLE_DOMAIN_REJECTION=true       # 추가
ENABLE_VECTOR_DOMAIN_CLASSIFICATION=true  # (이미 있음)
ENABLE_LLM_EVALUATION=true         # 추가
ENABLE_FALLBACK=true               # 추가
ENABLE_RESPONSE_CACHE=true         # 추가
ENABLE_RATE_LIMIT=true             # 추가

# ===== RAG Search (Togglable ON) =====
ENABLE_FIXED_DOC_LIMIT=true        # 추가
ENABLE_CROSS_DOMAIN_RERANK=true    # 추가
ENABLE_LEGAL_SUPPLEMENT=true       # 추가
ENABLE_ADAPTIVE_SEARCH=true        # 추가
ENABLE_DYNAMIC_K=true              # 추가
ENABLE_POST_EVAL_RETRY=true        # 추가
ENABLE_GRADUATED_RETRY=true        # 추가
ENABLE_ACTION_AWARE_GENERATION=true # 추가

# ===== RAG Optional (OFF by default) =====
ENABLE_LLM_DOMAIN_CLASSIFICATION=false  # (이미 있음)
ENABLE_CONTEXT_COMPRESSION=false   # 추가
ENABLE_RAGAS_EVALUATION=false      # (이미 있음)
```

### Step 2: .env.example 동기화 (5분)

**파일**: `.env.example`

.env와 동일한 변수 목록을 값 없이(또는 기본값과 함께) 추가하여 팀원 온보딩 용이하게.

### Step 3: CLAUDE.md 환경 변수 섹션 업데이트 (15분)

**파일**: `rag/CLAUDE.md` — "환경 변수" 섹션

현재 11개 → message.txt 기반 19개 + Always-On 10개로 확장:

#### 필수 ON (OFF 시 서비스 품질 심각 저하)

| 변수 | 기본값 | OFF 시 영향 |
|------|--------|------------|
| ENABLE_HYBRID_SEARCH | true | BM25 비활성 → 키워드 정확도 하락 |
| ENABLE_RERANKING | true | 검색 관련성 60% 저하 |
| ENABLE_DOMAIN_REJECTION | true | 범위 밖 질문에 할루시네이션 |
| ENABLE_VECTOR_DOMAIN_CLASSIFICATION | true | 키워드만으로 분류 → 정확도 급감 |
| ENABLE_LLM_EVALUATION | true | 저품질 답변 그대로 노출 |
| ENABLE_FALLBACK | true | 검색 실패 시 에러 노출 |
| ENABLE_RESPONSE_CACHE | true | 동일 질문 매번 LLM 호출 → 비용↑ |
| ENABLE_RATE_LIMIT | true | API 남용 방어 없음 |

#### 상황별 토글 가능 (기본 ON)

| 변수 | 기본값 | OFF 시나리오 |
|------|--------|-------------|
| ENABLE_FIXED_DOC_LIMIT | true | Dynamic K로 전환 시 |
| ENABLE_CROSS_DOMAIN_RERANK | true | 단일 도메인 질문만 있을 때 |
| ENABLE_LEGAL_SUPPLEMENT | true | 법률 질문 없는 환경 |
| ENABLE_ADAPTIVE_SEARCH | true | 검색 전략 고정 시 |
| ENABLE_DYNAMIC_K | true | 문서 수 고정 시 |
| ENABLE_POST_EVAL_RETRY | true | 비용 절감 필요 시 |
| ENABLE_GRADUATED_RETRY | true | 비용 절감 필요 시 |
| ENABLE_ACTION_AWARE_GENERATION | true | 액션 추천 불필요 시 |

#### 기본 OFF (필요 시 ON)

| 변수 | 기본값 | ON 시나리오 |
|------|--------|------------|
| ENABLE_CONTEXT_COMPRESSION | false | 검색 문서가 너무 길 때 (LLM 비용 추가) |
| ENABLE_LLM_DOMAIN_CLASSIFICATION | false | 벡터 분류 디버깅 시 (LLM 비용 추가) |
| ENABLE_RAGAS_EVALUATION | false | RAG 품질 정량 측정 시 (LLM 비용 추가) |

### Step 4: docs/FEATURE_TOGGLES.md 생성 (20분)

**파일**: `docs/FEATURE_TOGGLES.md`

message.txt 내용을 정식 문서로 승격:
- 4개 카테고리 분류표 (message.txt 원본 기반)
- 시나리오별 설정 예시 (데모용 / 프로덕션 / 디버깅)
- 항상 ON 10개 기능 리스트 (구현 파일 경로 포함)

### Step 5: 벡터DB 빌드 (30~60분, 대기 시간)

**명령어**:
```bash
cd D:\final_project\rag
py -m vectorstores.build_vectordb --all --force
```

**검증**:
```bash
py -c "
import chromadb
client = chromadb.PersistentClient(path='vectordb')
for c in client.list_collections():
    print(f'{c.name}: {c.count()} docs')
"
```

**예상 결과**:

| 컬렉션 | 예상 문서 수 |
|--------|------------|
| startup_funding_db | ~2,100 |
| finance_tax_db | ~2,100 |
| hr_labor_db | ~1,500 |
| law_common_db | ~9,000 |

### Step 6: CLI 테스트 (벡터DB 빌드 후)

```bash
cd D:\final_project\rag

# Hybrid Search ON + Re-ranking ON (기본 상태) 테스트
py cli.py --query "세탁소 주휴수당 계산 방법" --quiet
py cli.py --query "창업중소기업 세액감면 요건" --quiet
py cli.py --query "전자상거래법 통신판매업자 의무" --quiet
```

---

## 수정 파일 요약

| 파일 | 변경 내용 | 예상 시간 |
|------|----------|----------|
| `.env` | 누락된 13개 RAG 토글 추가 | 15분 |
| `.env.example` | .env와 동기화 | 5분 |
| `rag/CLAUDE.md` | 환경 변수 섹션 재작성 (19+10개) | 15분 |
| `docs/FEATURE_TOGGLES.md` | 신규 생성 (운영 가이드) | 20분 |

**코드 변경 없음** — 설정 파일 + 문서만 수정

---

## 검증 방법

1. `.env` 변수 누락 확인: `config.py`의 Settings 필드와 `.env` 키 대조
2. 벡터DB 빌드 후 CLI로 각 도메인 1개씩 질문 테스트
3. `docs/FEATURE_TOGGLES.md`가 message.txt 4개 카테고리를 모두 포함하는지 확인
