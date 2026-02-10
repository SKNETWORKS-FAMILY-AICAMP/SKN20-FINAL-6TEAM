"""요청 스키마 모듈.

API 요청에 사용되는 Pydantic 모델을 정의합니다.
"""

from typing import Any

from pydantic import BaseModel, Field


class CompanyContext(BaseModel):
    """기업 정보 컨텍스트.

    Attributes:
        company_name: 회사명
        business_number: 사업자등록번호
        industry_code: 업종 코드
        industry_name: 업종명
        employee_count: 직원 수
        years_in_business: 업력 (년)
        region: 지역
        annual_revenue: 연매출 (원)
    """

    company_name: str | None = Field(default=None, description="회사명")
    business_number: str | None = Field(default=None, description="사업자등록번호")
    industry_code: str | None = Field(default=None, description="업종 코드")
    industry_name: str | None = Field(default=None, description="업종명")
    employee_count: int | None = Field(default=None, description="직원 수")
    years_in_business: int | None = Field(default=None, description="업력 (년)")
    region: str | None = Field(default=None, description="지역")
    annual_revenue: int | None = Field(default=None, description="연매출 (원)")

    def to_context_string(self) -> str:
        """컨텍스트 문자열로 변환합니다."""
        parts = []
        if self.company_name:
            parts.append(f"회사명: {self.company_name}")
        if self.industry_name:
            parts.append(f"업종: {self.industry_name}")
        if self.employee_count is not None:
            parts.append(f"직원 수: {self.employee_count}명")
        if self.years_in_business is not None:
            parts.append(f"업력: {self.years_in_business}년")
        if self.region:
            parts.append(f"지역: {self.region}")
        return ", ".join(parts) if parts else "정보 없음"


class UserContext(BaseModel):
    """사용자 컨텍스트.

    Attributes:
        user_id: 사용자 ID
        user_type: 사용자 유형 (prospective, startup_ceo, sme_owner)
        company: 기업 정보
    """

    user_id: str | None = Field(default=None, description="사용자 ID")
    user_type: str = Field(
        default="prospective",
        description="사용자 유형 (prospective: 예비창업자, startup_ceo: 스타트업 CEO, sme_owner: 중소기업 대표)",
    )
    company: CompanyContext | None = Field(default=None, description="기업 정보")

    def get_user_type_label(self) -> str:
        """사용자 유형 라벨을 반환합니다."""
        labels = {
            "prospective": "예비 창업자",
            "startup_ceo": "스타트업 CEO",
            "sme_owner": "중소기업 대표",
        }
        return labels.get(self.user_type, "일반 사용자")


class ChatMessage(BaseModel):
    """채팅 메시지.

    Attributes:
        role: 역할 (user, assistant)
        content: 메시지 내용
    """

    role: str = Field(description="역할 (user, assistant)")
    content: str = Field(description="메시지 내용")


class ChatRequest(BaseModel):
    """채팅 요청 스키마.

    Attributes:
        message: 사용자 메시지
        history: 대화 이력
        user_context: 사용자 컨텍스트
        session_id: 세션 ID
    """

    message: str = Field(description="사용자 메시지")
    history: list[ChatMessage] = Field(default_factory=list, description="대화 이력")
    user_context: UserContext | None = Field(default=None, description="사용자 컨텍스트")
    session_id: str | None = Field(default=None, description="세션 ID")


class DocumentRequest(BaseModel):
    """문서 생성 요청 기본 스키마.

    Attributes:
        document_type: 문서 유형
        format: 출력 형식 (pdf, docx)
        user_context: 사용자 컨텍스트
    """

    document_type: str = Field(description="문서 유형")
    format: str = Field(default="pdf", description="출력 형식 (pdf, docx)")
    user_context: UserContext | None = Field(default=None, description="사용자 컨텍스트")


class ContractRequest(BaseModel):
    """근로계약서 생성 요청 스키마.

    Attributes:
        employee_name: 근로자 이름
        employee_birth: 근로자 생년월일
        employee_address: 근로자 주소
        job_title: 직위/직책
        job_description: 업무 내용
        contract_start_date: 계약 시작일
        contract_end_date: 계약 종료일 (무기계약 시 None)
        workplace: 근무 장소
        work_start_time: 근무 시작 시간
        work_end_time: 근무 종료 시간
        rest_time: 휴게 시간
        work_days: 근무 요일
        base_salary: 기본급 (월)
        payment_date: 급여 지급일
        is_permanent: 무기계약 여부
        company_context: 회사 정보
        format: 출력 형식
    """

    employee_name: str = Field(description="근로자 이름")
    employee_birth: str | None = Field(default=None, description="근로자 생년월일")
    employee_address: str | None = Field(default=None, description="근로자 주소")
    job_title: str = Field(description="직위/직책")
    job_description: str = Field(description="업무 내용")
    contract_start_date: str = Field(description="계약 시작일 (YYYY-MM-DD)")
    contract_end_date: str | None = Field(default=None, description="계약 종료일")
    workplace: str = Field(description="근무 장소")
    work_start_time: str = Field(default="09:00", description="근무 시작 시간")
    work_end_time: str = Field(default="18:00", description="근무 종료 시간")
    rest_time: str = Field(default="12:00-13:00", description="휴게 시간")
    work_days: str = Field(default="월~금", description="근무 요일")
    base_salary: int = Field(description="기본급 (월)")
    payment_date: int = Field(default=25, description="급여 지급일")
    is_permanent: bool = Field(default=True, description="무기계약 여부")
    company_context: CompanyContext | None = Field(default=None, description="회사 정보")
    format: str = Field(default="pdf", description="출력 형식")
