"""문서 유형 레지스트리 모듈.

8개 문서 유형의 메타데이터(필드 정의, 생성 방식, 프롬프트 키)를 정의합니다.
"""

from dataclasses import dataclass, field


@dataclass
class DocumentFieldDef:
    """문서 필드 정의.

    Attributes:
        name: 필드 키 (예: "disclosing_party")
        label: UI 라벨 (예: "정보 제공자")
        field_type: 필드 타입 ("text" | "date" | "number" | "textarea" | "select")
        required: 필수 여부
        placeholder: 플레이스홀더 텍스트
        options: select 타입용 옵션 리스트
    """

    name: str
    label: str
    field_type: str = "text"
    required: bool = True
    placeholder: str = ""
    options: list[str] | None = None


@dataclass
class DocumentTypeDef:
    """문서 유형 정의.

    Attributes:
        type_key: 문서 유형 키 (예: "nda")
        label: 문서 유형 라벨 (예: "비밀유지계약서 (NDA)")
        description: 짧은 설명
        fields: 필드 정의 리스트
        generation_method: 생성 방식 ("hardcoded" | "llm")
        llm_prompt_key: utils/prompts.py의 프롬프트 변수명
        default_format: 기본 출력 형식
    """

    type_key: str
    label: str
    description: str
    fields: list[DocumentFieldDef]
    generation_method: str  # "hardcoded" | "llm"
    llm_prompt_key: str | None = None
    default_format: str = "docx"


# ---------- 8개 문서 유형 정의 ----------

DOCUMENT_TYPE_REGISTRY: dict[str, DocumentTypeDef] = {
    # 1) 표준 근로계약서 — 기존 하드코딩 로직
    "labor_contract": DocumentTypeDef(
        type_key="labor_contract",
        label="표준 근로계약서",
        description="근로기준법에 따른 표준 근로계약서를 생성합니다.",
        generation_method="hardcoded",
        fields=[],  # 기존 전용 폼 사용
        default_format="pdf",
    ),
    # 2) 사업계획서 — LLM 기반 생성
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
    # 3) 비밀유지계약서 (NDA)
    "nda": DocumentTypeDef(
        type_key="nda",
        label="비밀유지계약서 (NDA)",
        description="당사자 간 비밀정보 보호를 위한 NDA를 생성합니다.",
        generation_method="llm",
        llm_prompt_key="NDA_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="party_a", label="갑 (정보 제공자)", placeholder="(주)비지테크"),
            DocumentFieldDef(name="party_b", label="을 (정보 수령자)", placeholder="(주)파트너"),
            DocumentFieldDef(name="confidential_scope", label="비밀정보 범위", field_type="textarea", placeholder="기술 자료, 영업 비밀, 고객 정보 등"),
            DocumentFieldDef(name="duration", label="유효 기간", placeholder="2년"),
            DocumentFieldDef(name="penalty", label="위약금", required=False, placeholder="1억원"),
        ],
    ),
    # 4) 용역 계약서
    "service_agreement": DocumentTypeDef(
        type_key="service_agreement",
        label="용역 계약서",
        description="외주/프리랜서 용역 계약서를 생성합니다.",
        generation_method="llm",
        llm_prompt_key="SERVICE_AGREEMENT_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="client", label="위탁자 (갑)", placeholder="(주)비지테크"),
            DocumentFieldDef(name="contractor", label="수탁자 (을)", placeholder="홍길동"),
            DocumentFieldDef(name="service_description", label="용역 내용", field_type="textarea", placeholder="웹 애플리케이션 개발"),
            DocumentFieldDef(name="total_amount", label="용역 대금", placeholder="1,000만원"),
            DocumentFieldDef(name="start_date", label="계약 시작일", field_type="date"),
            DocumentFieldDef(name="end_date", label="계약 종료일", field_type="date"),
            DocumentFieldDef(name="deliverables", label="납품물", field_type="textarea", required=False, placeholder="소스코드, 설계문서"),
        ],
    ),
    # 5) 공동 창업 계약서
    "cofounder_agreement": DocumentTypeDef(
        type_key="cofounder_agreement",
        label="공동 창업 계약서",
        description="공동 창업자 간 역할·지분·퇴출 조건 등을 정하는 계약서입니다.",
        generation_method="llm",
        llm_prompt_key="COFOUNDER_AGREEMENT_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="cofounders", label="공동 창업자 (쉼표 구분)", placeholder="홍길동, 김철수"),
            DocumentFieldDef(name="equity_split", label="지분 비율", placeholder="50:50"),
            DocumentFieldDef(name="roles", label="역할 분담", field_type="textarea", placeholder="홍길동: 기술 총괄, 김철수: 경영 총괄"),
            DocumentFieldDef(name="company_name", label="회사명", required=False, placeholder="(주)비지테크"),
            DocumentFieldDef(name="profit_distribution", label="이익 분배 방식", field_type="textarea", required=False, placeholder="지분 비율에 따라 배분"),
            DocumentFieldDef(name="exit_conditions", label="탈퇴/퇴출 조건", field_type="textarea", required=False, placeholder="3개월 이상 무단 이탈 시"),
        ],
    ),
    # 6) 투자 의향서 (LOI)
    "investment_loi": DocumentTypeDef(
        type_key="investment_loi",
        label="투자 의향서 (LOI)",
        description="투자자와 피투자 회사 간의 투자 의향서를 생성합니다.",
        generation_method="llm",
        llm_prompt_key="INVESTMENT_LOI_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="investor", label="투자자", placeholder="(주)벤처캐피탈"),
            DocumentFieldDef(name="investee", label="피투자 회사", placeholder="(주)비지테크"),
            DocumentFieldDef(name="investment_amount", label="투자 금액", placeholder="5억원"),
            DocumentFieldDef(name="equity_ratio", label="투자 지분율", placeholder="10%"),
            DocumentFieldDef(name="conditions", label="투자 조건", field_type="textarea", placeholder="시리즈A, 이사회 참여권"),
            DocumentFieldDef(name="negotiation_period", label="협상 기간", placeholder="3개월"),
        ],
    ),
    # 7) 업무 협약서 (MOU)
    "mou": DocumentTypeDef(
        type_key="mou",
        label="업무 협약서 (MOU)",
        description="기관/기업 간 업무 협력을 위한 MOU를 생성합니다.",
        generation_method="llm",
        llm_prompt_key="MOU_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="party_a", label="갑", placeholder="(주)비지테크"),
            DocumentFieldDef(name="party_b", label="을", placeholder="(주)파트너"),
            DocumentFieldDef(name="purpose", label="협력 목적", field_type="textarea", placeholder="AI 기술 분야 상호 발전 및 시장 확대"),
            DocumentFieldDef(name="cooperation_scope", label="협력 범위", field_type="textarea", placeholder="공동 연구, 기술 교류, 인력 파견"),
            DocumentFieldDef(name="duration", label="협약 기간", placeholder="1년"),
            DocumentFieldDef(name="roles", label="역할 분담", field_type="textarea", required=False, placeholder="갑: 기술 제공, 을: 데이터 제공"),
        ],
    ),
    # 8) 개인정보 동의서
    "privacy_consent": DocumentTypeDef(
        type_key="privacy_consent",
        label="개인정보 수집·이용 동의서",
        description="개인정보 수집·이용에 대한 동의서를 생성합니다.",
        generation_method="llm",
        llm_prompt_key="PRIVACY_CONSENT_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="collector", label="수집자 (회사/기관명)", placeholder="(주)비지테크"),
            DocumentFieldDef(name="items", label="수집 항목", field_type="textarea", placeholder="이름, 이메일, 전화번호"),
            DocumentFieldDef(name="purpose", label="이용 목적", field_type="textarea", placeholder="서비스 제공, 마케팅"),
            DocumentFieldDef(name="retention_period", label="보유 기간", placeholder="회원 탈퇴 시까지"),
            DocumentFieldDef(name="third_party_recipients", label="제3자 제공 대상", field_type="textarea", required=False, placeholder="결제대행사, 배송업체 등 (미입력 시 '제공하지 않음')"),
        ],
    ),
    # 9) 주주간 계약서
    "shareholders_agreement": DocumentTypeDef(
        type_key="shareholders_agreement",
        label="주주간 계약서",
        description="주주 간 의결권, 양도 제한, 배당 등을 정하는 계약서입니다.",
        generation_method="llm",
        llm_prompt_key="SHAREHOLDERS_AGREEMENT_GENERATION_PROMPT",
        fields=[
            DocumentFieldDef(name="shareholders", label="주주 (쉼표 구분)", placeholder="홍길동, 김철수, 이영희"),
            DocumentFieldDef(name="equity_structure", label="지분 구조", placeholder="홍길동 40%, 김철수 35%, 이영희 25%"),
            DocumentFieldDef(name="voting_rights", label="의결권 사항", field_type="textarea", required=False, placeholder="이사 선임, 정관 변경 시 주주 2/3 동의"),
            DocumentFieldDef(name="transfer_restrictions", label="양도 제한 / 우선매수권", field_type="textarea", required=False, placeholder="우선매수권, 동반매도권, 동반매수청구권"),
            DocumentFieldDef(name="management_rights", label="경영권 / 이사 선임", field_type="textarea", required=False, placeholder="대표이사 선임권, 이사회 구성 방법"),
            DocumentFieldDef(name="dividend_policy", label="배당 정책", field_type="textarea", required=False, placeholder="순이익의 20% 이상 배당"),
        ],
    ),
}
