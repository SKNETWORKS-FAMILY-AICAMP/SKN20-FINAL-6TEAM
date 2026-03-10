# State E 재평가 계획 — LLM 도메인 분류 활성화

> **목적**: State E(`ba51612`)를 `ENABLE_LLM_DOMAIN_CLASSIFICATION=true`로 재평가하여 State C와 공정하게 비교
> **배경**: `ANALYSIS_STATE_C_VS_E.md` 참조 — State E 최초 평가 시 LLM 분류가 기본값 `false`로 실행됨
> **환경**: Windows, RunPod 임베딩, Docker 미사용, git worktree로 ba51612 격리

---

## 사전 조건 확인 (진행 전 필수)

- [ ] `vectordb_0305.zip`이 프로젝트 루트에 존재 — **없으면 진행 차단**
- [ ] RunPod API 키 및 Endpoint ID 확인 (`RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`)
- [ ] 현재 브랜치에 커밋되지 않은 변경사항 없음 (`git status` 확인)

---

## 실행 순서

### Step 1. Worktree 생성

```bash
# 프로젝트 루트에서 실행
git worktree add ../eval-state-e-llm-on ba51612
cd ../eval-state-e-llm-on
```

### Step 2. vectordb_0305.zip 존재 확인

```bash
# 없으면 여기서 중단
ls vectordb_0305.zip
```

### Step 3. 평가 스크립트 확인

```bash
ls rag/evaluation/__main__.py
```

- **존재 시**: 그대로 사용
- **없을 시**: main 레포에서 evaluation 모듈 복사

```bash
# evaluation 모듈이 없을 경우에만 실행
cp -r <메인레포 경로>/rag/evaluation rag/evaluation
```

worktree drop 시 복사한 파일도 함께 제거되므로 안전.

### Step 4. 의존성 확인 및 .env 설정

```bash
# 프로젝트 루트 .venv 사용 (per-service venv 없음)
# .env 파일에 아래 환경변수 설정 (기존 .env 백업 후 편집)
```

`.env` 필수 설정:
```
ENABLE_LLM_DOMAIN_CLASSIFICATION=true
EMBEDDING_PROVIDER=runpod
RUNPOD_API_KEY=<key>
RUNPOD_ENDPOINT_ID=<id>
ENABLE_ACTION_AWARE_GENERATION=false
TOTAL_TIMEOUT=300
LLM_TIMEOUT=120
```

### Step 5. 평가 실행

```bash
cd rag
python -m evaluation \
  --dataset ../docs/ragas-evaluation/eval_0310/ragas_dataset_0310.jsonl \
  --output ../docs/ragas-evaluation/eval_0310/results/answers_state_e_llm_on.json \
  --timeout 300
```

### Step 6. 결과 파일 메인 레포로 복사

```bash
cp ../docs/ragas-evaluation/eval_0310/results/answers_state_e_llm_on.json \
   <메인레포 경로>/docs/ragas-evaluation/eval_0310/results/
```

### Step 7. Worktree 정리

```bash
cd <메인레포 경로>
git worktree remove ../eval-state-e-llm-on
```

---

## 결과 분석 포인트

평가 완료 후 아래 3가지를 비교하여 보고서 작성:

| 비교 | 분석 목적 |
|------|---------|
| **State E (LLM ON) vs State C** | Context Recall/F1 동등·우위 여부 확인 |
| **State E (LLM ON) vs State E (LLM OFF)** | LLM 분류 활성화 효과 정량화 |
| **거부 정확도** | R02(주식투자), R03(부동산투자) 처리 확인 — LLM ON 시 거부 정확도가 유지되는지 |

---

## 결과 기록 위치

- 원시 결과: `docs/ragas-evaluation/eval_0310/results/answers_state_e_llm_on.json`
- 평가 보고서: `docs/ragas-evaluation/eval_0310/RAGAS_STATE_E_LLM_ON_REPORT.md`
  - State C 보고서(`RAGAS_STATE_C_REPORT.md`)와 동일한 형식으로 작성

---

## 주의사항

- `vectordb_0305.zip` 없으면 **절대 진행하지 않음** — 이 파일이 State E의 VectorDB
- 환경변수 외 코드 변경 없이 실행 — 순수 설정 차이만 측정해야 함
- 평가 후 worktree 반드시 정리: `git worktree remove ../eval-state-e-llm-on`
- Windows 환경이므로 경로 구분자 주의 (`/` vs `\`)
- RunPod 임베딩 사용: `EMBEDDING_PROVIDER=runpod` 필수 — `local`로 실행 시 임베딩 불일치 발생
