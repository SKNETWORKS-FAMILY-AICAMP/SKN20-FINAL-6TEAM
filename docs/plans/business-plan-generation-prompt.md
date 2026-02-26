# 사업계획서 자동 생성 기능 개선 - Claude Code 구현 프롬프트

## 개요

현재 사업계획서(`business_plan`)는 하드코딩된 빈 템플릿(`[내용을 작성하세요]` 플레이스홀더)만 생성합니다.
이를 **하이브리드 방식(폼 입력 + LLM 생성)**으로 전환하여, 사용자가 핵심 정보를 입력하면 LLM이 섹션별로 실질적인 사업계획서 내용을 작성하도록 개선합니다.

**현재 상태**: `generation_method: "hardcoded"`, `fields: []` (빈 배열)
**목표 상태**: `generation_method: "llm"`, 구조화된 필드 + LLM 프롬프트 기반 생성

---

## 변경 대상 파일 (총 5개)

### 1. `rag/agents/document_registry.py` — 사업계획서 필드 정의 변경

**변경 내용**: `business_plan` 항목을 `hardcoded`에서 `llm`으로 전환하고 입력 필드를 추가합니다.

```python
# 기존 코드 (삭제)
"business_plan": DocumentTypeDef(
    type_key="business_plan",
    label="사업계획서",
    description="사업계획서 템플릿을 생성합니다.",
    generation_method="hardcoded",
    fields=[],
    default_format="docx",
),

# 변경 코드
"business_plan": DocumentTypeDef(
    type_key="business_plan",
    label="사업계획서",
    description="사업 정보를 기반으로 맞춤형 사업계획서를 생성합니다.",
    generation_method="llm",
    llm_prompt_key="BUSINESS_PLAN_GENERATION_PROMPT",
    default_format="docx",
    fields=[
        DocumentFieldDef(
            name="plan_type",
            label="사업계획서 유형",
            field_type="select",
            required=True,
            options=[
                "일반 사업계획서",
                "예비창업패키지 신청용",
                "정책자금 신청용",
                "IR 피칭용",
            ],
        ),
        DocumentFieldDef(
            name="business_item",
            label="사업 아이템명",
            field_type="text",
            required=True,
            placeholder="예: AI 기반 소상공인 경영 상담 챗봇",
        ),
        DocumentFieldDef(
            name="business_description",
            label="사업 아이템 설명",
            field_type="textarea",
            required=True,
            placeholder="핵심 제품/서비스를 2~3문장으로 설명해주세요",
        ),
        DocumentFieldDef(
            name="startup_motivation",
            label="창업 동기",
            field_type="textarea",
            required=False,
            placeholder="왜 이 사업을 시작하려 하시나요?",
        ),
        DocumentFieldDef(
            name="target_customer",
            label="타겟 고객",
            field_type="text",
            required=True,
            placeholder="예: 20~30대 1인 가구, 예비 창업자",
        ),
        DocumentFieldDef(
            name="competitors",
            label="예상 경쟁사/경쟁 서비스",
            field_type="textarea",
            required=False,
            placeholder="주요 경쟁사 또는 대체 서비스를 작성해주세요",
        ),
        DocumentFieldDef(
            name="differentiation",
            label="차별화 포인트",
            field_type="textarea",
            required=False,
            placeholder="경쟁사 대비 핵심 차별점",
        ),
        DocumentFieldDef(
            name="initial_investment",
            label="예상 초기 투자금 (만원)",
            field_type="number",
            required=False,
            placeholder="5000",
        ),
        DocumentFieldDef(
            name="monthly_revenue",
            label="예상 월 매출 (만원)",
            field_type="number",
            required=False,
            placeholder="1000",
        ),
        DocumentFieldDef(
            name="team_info",
            label="팀 구성",
            field_type="textarea",
            required=False,
            placeholder="예: 대표 1명(기술), 공동창업자 1명(마케팅), 개발자 2명",
        ),
        DocumentFieldDef(
            name="business_start_date",
            label="사업 시작 예정일",
            field_type="date",
            required=False,
        ),
    ],
),
```

**설계 의도**:
- `plan_type` (select): 제출처/용도에 따라 LLM 프롬프트 내에서 섹션 구성을 분기합니다. 예비창업패키지는 "문제 인식 → 해결 방안 → 시장성 → 성장 전략" 구조, IR용은 "Problem → Solution → Market → Traction → Ask" 구조 등이 다릅니다.
- `business_item`, `business_description`, `target_customer`: 필수 필드. 이 3개만 입력해도 최소한의 사업계획서가 생성되도록 합니다.
- 나머지 필드는 선택 사항. 입력하면 LLM이 해당 정보를 반영하고, 비워두면 업종 특성에 맞는 일반적인 내용으로 채웁니다.
- `company_context`(회사명, 업종코드, 지역 등)는 백엔드에서 자동 주입되므로 별도 필드 불필요.

---

### 2. `rag/utils/prompts.py` — 사업계획서 LLM 프롬프트 추가

파일 하단에 `BUSINESS_PLAN_GENERATION_PROMPT` 변수를 추가합니다.

```python
BUSINESS_PLAN_GENERATION_PROMPT = """당신은 한국의 창업 컨설턴트이자 사업계획서 전문 작성자입니다.
아래 입력 정보를 바탕으로 **사업계획서**를 작성하세요.

## 입력 정보
{field_values}

## 작성 지침

### 공통 규칙
1. 사용자가 입력한 팩트 정보(사업 아이템, 타겟 고객, 투자금 등)는 **그대로 반영**하세요.
2. 사용자가 입력하지 않은 항목은 업종 특성에 맞는 **합리적인 내용으로 보완** 작성하세요.
3. 모든 섹션은 구체적이고 실행 가능한 내용으로 작성하세요. "[내용을 작성하세요]" 같은 플레이스홀더는 절대 사용하지 마세요.
4. 각 섹션은 `## 섹션명` 형태의 마크다운 헤딩으로 구분하세요.
5. 재무 수치가 입력된 경우, 해당 수치를 기반으로 3개년 추정 재무 계획을 포함하세요.
6. 분량은 A4 기준 8~15페이지 분량으로 작성하세요.

### 사업계획서 유형별 섹션 구성

**[일반 사업계획서]**
## 1. 사업 개요
  - 사업 아이템 소개, 창업 동기 및 비전, 사업 목표 (단기/중기/장기)
## 2. 시장 분석
  - 시장 규모 및 성장성, 경쟁 환경 분석, 타겟 고객 세분화
## 3. 제품/서비스 상세
  - 핵심 기능 및 서비스 설명, 차별화 포인트, 가격 정책
## 4. 마케팅 및 고객 확보 전략
  - 마케팅 목표, 홍보 채널 및 방법, 고객 확보/유지 전략
## 5. 운영 계획
  - 조직 구성 및 인력 계획, 운영 프로세스, 주요 마일스톤
## 6. 재무 계획
  - 소요 자금 및 조달 계획, 매출 추정, 손익 추정 (3개년)

**[예비창업패키지 신청용]**
## 1. 문제 인식
  - 타겟 시장의 문제/불편 사항, 기존 솔루션의 한계
## 2. 해결 방안 (아이템 소개)
  - 제품/서비스 소개, 기술/비즈니스 모델의 핵심, 경쟁 우위
## 3. 시장성 분석
  - TAM/SAM/SOM 분석, 경쟁 현황, 타겟 고객 프로파일
## 4. 사업화 전략
  - Go-to-Market 전략, 수익 모델, 판매/유통 채널
## 5. 성장 전략 및 목표
  - 단계별 성장 로드맵 (1년/3년/5년), 핵심 KPI
## 6. 팀 구성 및 역량
  - 대표자 및 팀원 소개, 핵심 역량, 부족 역량 보완 계획
## 7. 자금 운용 계획
  - 정부 지원금 사용 계획 (항목별 금액), 자부담 계획, 매출 추정

**[정책자금 신청용]**
## 1. 기업 현황
  - 기업 개요, 주요 연혁, 조직 구성
## 2. 사업 내용
  - 주력 제품/서비스, 기술력 및 보유 특허/인증, 생산/공급 체계
## 3. 시장 현황 및 전망
  - 산업 동향, 시장 규모, 경쟁사 비교
## 4. 자금 소요 및 상환 계획
  - 자금 용도 (시설/운전/R&D), 상세 소요 내역, 상환 계획
## 5. 향후 사업 계획
  - 매출/이익 추정 (3개년), 고용 계획, 수출 계획 (해당 시)

**[IR 피칭용]**
## 1. Problem
  - 해결하려는 핵심 문제, 시장 Pain Point
## 2. Solution
  - 제품/서비스 소개, 핵심 가치 제안
## 3. Market
  - TAM/SAM/SOM, 시장 성장률
## 4. Business Model
  - 수익 구조, 단위 경제학(Unit Economics)
## 5. Traction
  - 현재까지 성과 (MAU, 매출 등), 주요 마일스톤
## 6. Team
  - 핵심 팀 소개, 관련 경험
## 7. Financials
  - 3개년 매출/비용 추정, BEP 시점
## 8. Ask
  - 투자 유치 금액, 자금 사용 계획, 기대 성과

### 문서 포맷
- 마크다운 헤딩(`##`, `###`)으로 섹션을 구분하세요.
- 표가 필요한 경우 마크다운 표 문법을 사용하세요.
- 입력된 "사업계획서 유형"에 해당하는 섹션 구성을 따르세요. 유형이 입력되지 않았으면 "일반 사업계획서" 구성을 사용하세요.
"""
```

**설계 의도**:
- 용도별 4가지 섹션 구성을 프롬프트 안에 포함시켜 `plan_type` select 값에 따라 LLM이 알아서 분기하도록 합니다. 별도 코드 분기 없이 프롬프트 하나로 처리합니다.
- "사용자 입력은 그대로 반영, 미입력은 업종에 맞게 보완"이라는 핵심 규칙을 명시합니다.
- 마크다운 헤딩 형식을 지정해서, 기존 `_build_docx_from_text()`의 `#` 감지 로직과 호환되도록 합니다.

---

### 3. `rag/agents/executor.py` — 사업계획서 분기 로직 변경

**변경 내용**: `generate_document()` 메서드에서 `business_plan`이 이제 `llm` 방식이므로 하드코딩 분기를 제거합니다.

```python
# 기존 코드 (executor.py 내 generate_document 메서드)
if type_def.generation_method == "hardcoded":
    if document_type == "labor_contract":
        return self.generate_labor_contract(ContractRequest(**params))
    elif document_type == "business_plan":
        return self.generate_business_plan_template(format=format)

# 변경 코드
if type_def.generation_method == "hardcoded":
    if document_type == "labor_contract":
        return self.generate_labor_contract(ContractRequest(**params))
```

또한 `execute_action()` 메서드에서도 동일하게 수정:

```python
# 기존 코드
elif doc_type == "business_plan":
    result = self.generate_business_plan_template()
    return result.model_dump()

# 변경: 이 분기를 제거하고, generate_document()로 통합되도록 함
```

`generate_business_plan_template()` 메서드 자체는 삭제하지 말고 유지해도 됩니다 (폴백용).

추가로, `_generate_document_by_llm()` 메서드에서 사업계획서는 분량이 길기 때문에 `max_tokens`를 높여야 합니다:

```python
# 기존 코드
llm = create_llm(label="문서생성", temperature=0.3, max_tokens=4096)

# 변경: 사업계획서는 max_tokens를 높임
token_limit = 8192 if type_def.type_key == "business_plan" else 4096
llm = create_llm(label="문서생성", temperature=0.3, max_tokens=token_limit)
```

---

### 4. `frontend/src/components/chat/ActionButtons.tsx` — 사업계획서를 동적 폼으로 전환

**변경 내용**: `business_plan`을 `LLM_DOC_TYPES`에 추가하고, 기존 직접 다운로드 로직을 제거합니다.

```typescript
// 기존 코드
const LLM_DOC_TYPES = new Set([
  'nda',
  'service_agreement',
  'cofounder_agreement',
  'investment_loi',
  'mou',
  'privacy_consent',
  'shareholders_agreement',
]);

// 변경 코드 — business_plan 추가
const LLM_DOC_TYPES = new Set([
  'business_plan',       // ← 추가
  'nda',
  'service_agreement',
  'cofounder_agreement',
  'investment_loi',
  'mou',
  'privacy_consent',
  'shareholders_agreement',
]);
```

그리고 `handleAction()` 내 `business_plan` 전용 분기를 제거:

```typescript
// 기존 코드
if (docType === 'labor_contract') {
  setContractModalOpen(true);
} else if (docType === 'business_plan') {
  await downloadBusinessPlan();         // ← 이 분기 제거
} else if (LLM_DOC_TYPES.has(docType)) {
  setDocModalType(docType);
}

// 변경 코드 — business_plan이 LLM_DOC_TYPES에 포함되므로 자동으로 DocumentFormModal 사용
if (docType === 'labor_contract') {
  setContractModalOpen(true);
} else if (LLM_DOC_TYPES.has(docType)) {
  setDocModalType(docType);
}
```

`downloadBusinessPlan()` 함수와 `generateBusinessPlan` import는 삭제해도 됩니다.

---

### 5. `rag/routes/documents.py` — 사업계획서 전용 엔드포인트 유지 (선택)

기존 `POST /api/documents/business-plan` 엔드포인트는 하위 호환을 위해 유지하되, 내부적으로 `generate_document("business_plan", ...)` 를 호출하도록 변경합니다. 또는 deprecated 처리 후 프론트엔드가 범용 엔드포인트(`POST /api/documents/generate`)를 사용하므로 제거해도 무방합니다.

---

## 요약: 변경 체크리스트

| # | 파일 | 변경 내용 |
|---|------|-----------|
| 1 | `rag/agents/document_registry.py` | `business_plan` 필드 정의 추가, `generation_method`를 `"llm"`으로 변경, `llm_prompt_key` 추가 |
| 2 | `rag/utils/prompts.py` | `BUSINESS_PLAN_GENERATION_PROMPT` 변수 추가 |
| 3 | `rag/agents/executor.py` | `generate_document()`에서 `business_plan` 하드코딩 분기 제거, LLM 생성 시 사업계획서 `max_tokens` 상향 |
| 4 | `frontend/src/components/chat/ActionButtons.tsx` | `LLM_DOC_TYPES`에 `business_plan` 추가, 직접 다운로드 분기 제거 |
| 5 | `rag/routes/documents.py` (선택) | 전용 엔드포인트 deprecated 또는 범용으로 위임 |

## 핵심 설계 원칙

1. **기존 LLM 문서 생성 파이프라인 재사용**: NDA, 용역계약서 등 7개 문서가 이미 사용하는 `_generate_document_by_llm()` → `_build_docx_from_text()` / `_build_pdf_from_text()` 파이프라인을 그대로 활용합니다. 새로운 생성 파이프라인을 만들 필요 없습니다.
2. **프론트엔드 동적 폼 재사용**: `DocumentFormModal.tsx`가 registry 필드 정의를 읽어 자동으로 폼을 렌더링하므로, 프론트엔드 폼 컴포넌트 신규 개발이 불필요합니다.
3. **회사 정보 자동 주입**: 백엔드 프록시(`backend/apps/rag/router.py`)가 이미 인증된 사용자의 company 정보를 `company_context`로 자동 주입하므로, 회사명/업종/지역은 별도 입력 필드 없이 프롬프트에 포함됩니다.
4. **용도별 분기는 프롬프트 내에서 처리**: `plan_type` select 값에 따라 LLM이 프롬프트 내 지침을 따르므로, 코드 레벨의 조건 분기가 불필요합니다.
