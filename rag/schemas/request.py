"""요청 스키마 모듈.

API 요청에 사용되는 Pydantic 모델을 정의합니다.
"""

import hashlib
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

    # -- 메타데이터 필터링 헬퍼 --

    # 시도 17개 정규화 매핑 (preprocess_announcements.py와 동일)
    _REGION_NORMALIZATION: dict[str, str] = {
        "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
        "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
        "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
        "충북": "충청북도", "충남": "충청남도", "전남": "전라남도",
        "경북": "경상북도", "경남": "경상남도", "제주": "제주특별자치도",
        "강원": "강원특별자치도", "전북": "전북특별자치도",
        "서울특별시": "서울특별시", "부산광역시": "부산광역시",
        "대구광역시": "대구광역시", "인천광역시": "인천광역시",
        "광주광역시": "광주광역시", "대전광역시": "대전광역시",
        "울산광역시": "울산광역시", "세종특별자치시": "세종특별자치시",
        "경기도": "경기도", "충청북도": "충청북도", "충청남도": "충청남도",
        "전라남도": "전라남도", "경상북도": "경상북도", "경상남도": "경상남도",
        "제주특별자치도": "제주특별자치도", "강원특별자치도": "강원특별자치도",
        "전북특별자치도": "전북특별자치도",
        "전라북도": "전북특별자치도", "강원도": "강원특별자치도",
    }

    def get_normalized_region(self) -> str | None:
        """기업 지역을 시도 레벨로 정규화합니다.

        company.region이 "서울특별시 강남구" 형태인 경우 "서울특별시"를 추출합니다.

        Returns:
            정규화된 시도명 또는 None (지역 정보 없음)
        """
        if not self.company or not self.company.region:
            return None

        region = self.company.region.strip()
        if not region:
            return None

        # 정확 매칭
        if region in self._REGION_NORMALIZATION:
            return self._REGION_NORMALIZATION[region]

        # 부분 매칭 (긴 키 우선)
        for key in sorted(self._REGION_NORMALIZATION.keys(), key=len, reverse=True):
            if key in region:
                return self._REGION_NORMALIZATION[key]

        return None

    def get_target_types_for_filter(self) -> list[str] | None:
        """사용자 유형에 맞는 공고 대상 필터 태그를 반환합니다.

        Returns:
            ChromaDB 필터에 사용할 target 태그 리스트 또는 None
        """
        mapping: dict[str, list[str]] = {
            "prospective": ["target_예비창업자", "target_전체"],
            "startup_ceo": ["target_창업기업", "target_예비창업자", "target_전체"],
            "sme_owner": ["target_중소기업", "target_소상공인", "target_전체"],
        }
        return mapping.get(self.user_type)

    def get_filter_hash(self) -> str | None:
        """캐시 키용 필터 해시를 생성합니다.

        region + user_type 조합의 해시를 반환합니다.

        Returns:
            해시 문자열 또는 None (필터링 대상 아님)
        """
        region = self.get_normalized_region()
        targets = self.get_target_types_for_filter()

        if region is None and targets is None:
            return None

        parts = [region or "", self.user_type or ""]
        return hashlib.md5(":".join(parts).encode()).hexdigest()[:8]


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

    message: str = Field(description="사용자 메시지", min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, description="대화 이력", max_length=50)
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

    employee_name: str = Field(description="근로자 이름", max_length=100)
    employee_birth: str | None = Field(default=None, description="근로자 생년월일", max_length=20)
    employee_address: str | None = Field(default=None, description="근로자 주소", max_length=200)
    job_title: str = Field(description="직위/직책", max_length=100)
    job_description: str = Field(description="업무 내용", max_length=500)
    contract_start_date: str = Field(description="계약 시작일 (YYYY-MM-DD)", pattern=r"^\d{4}-\d{2}-\d{2}$")
    contract_end_date: str | None = Field(default=None, description="계약 종료일", pattern=r"^\d{4}-\d{2}-\d{2}$")
    workplace: str = Field(description="근무 장소", max_length=200)
    work_start_time: str = Field(default="09:00", description="근무 시작 시간", max_length=10)
    work_end_time: str = Field(default="18:00", description="근무 종료 시간", max_length=10)
    rest_time: str = Field(default="12:00-13:00", description="휴게 시간", max_length=30)
    work_days: str = Field(default="월~금", description="근무 요일", max_length=30)
    base_salary: int = Field(description="기본급 (월)", gt=0)
    payment_date: int = Field(default=25, description="급여 지급일", ge=1, le=31)
    is_permanent: bool = Field(default=True, description="무기계약 여부")
    company_context: CompanyContext | None = Field(default=None, description="회사 정보")
    format: str = Field(default="pdf", description="출력 형식", pattern=r"^(pdf|docx)$")
