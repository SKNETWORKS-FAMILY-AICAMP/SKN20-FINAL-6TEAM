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
    age: int | None = Field(default=None, description="사용자 나이")
    company: CompanyContext | None = Field(default=None, description="기업 정보")
    companies: list[CompanyContext] = Field(default_factory=list, description="모든 활성 기업 목록")

    def get_user_type_label(self) -> str:
        """사용자 유형 라벨을 반환합니다. 나이가 있으면 함께 표기합니다."""
        labels = {
            "prospective": "예비 창업자",
            "startup_ceo": "스타트업 CEO",
            "sme_owner": "중소기업 대표",
        }
        label = labels.get(self.user_type, "일반 사용자")
        if self.age is not None:
            label += f" ({self.age}세)"
        return label

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

    def get_all_companies(self) -> list[CompanyContext]:
        """모든 활성 기업 목록을 반환합니다.

        Returns:
            기업 목록 (companies 필드 우선, 없으면 company 필드 래핑)
        """
        if self.companies:
            return self.companies
        if self.company:
            return [self.company]
        return []

    def get_all_companies_context_string(self) -> str:
        """모든 기업의 컨텍스트 문자열을 반환합니다.

        Returns:
            단일 기업이면 단순 문자열, 복수이면 [기업 N] 형식으로 포맷팅
        """
        all_comp = self.get_all_companies()
        if not all_comp:
            return "정보 없음"
        if len(all_comp) == 1:
            return all_comp[0].to_context_string()
        parts = []
        for i, c in enumerate(all_comp, 1):
            parts.append(f"[기업 {i}] {c.to_context_string()}")
        return "\n".join(parts)

    def get_normalized_regions(self) -> list[str]:
        """모든 기업의 지역을 시도 레벨로 정규화하여 합집합을 반환합니다.

        Returns:
            정규화된 시도명 리스트 (중복 없음, 정렬됨)
        """
        regions: set[str] = set()
        for c in self.get_all_companies():
            if not c.region:
                continue
            region = c.region.strip()
            if region in self._REGION_NORMALIZATION:
                regions.add(self._REGION_NORMALIZATION[region])
                continue
            for key in sorted(self._REGION_NORMALIZATION.keys(), key=len, reverse=True):
                if key in region:
                    regions.add(self._REGION_NORMALIZATION[key])
                    break
        return sorted(regions)

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

        regions + user_type 조합의 해시를 반환합니다.

        Returns:
            해시 문자열 또는 None (필터링 대상 아님)
        """
        regions = self.get_normalized_regions()
        targets = self.get_target_types_for_filter()

        if not regions and targets is None:
            return None

        parts = [",".join(regions), self.user_type or ""]
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
    history: list[ChatMessage] = Field(default_factory=list, description="대화 이력", max_length=20)
    user_context: UserContext | None = Field(default=None, description="사용자 컨텍스트")
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="세션 ID (영숫자, 하이픈, 언더스코어만 허용)",
    )


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

    # 휴일 (근로기준법 제55조)
    holidays: str = Field(
        default="주휴일 및 근로자의 날, 관공서의 공휴일에 관한 규정에 따른 공휴일",
        description="휴일 (근로기준법 제55조)",
        max_length=300,
    )

    # 연차유급휴가 (근로기준법 제60조)
    annual_leave_days: int = Field(
        default=15,
        description="연차유급휴가 일수 (근로기준법 제60조)",
        ge=0,
        le=365,
    )

    # 단시간근로자 (근로기준법 제18조)
    is_part_time: bool = Field(default=False, description="단시간근로자 여부")
    weekly_work_hours: float | None = Field(
        default=None,
        description="주당 소정근로시간 (단시간근로자)",
        ge=0,
        le=168,
    )

    # 임금 상세 (근로기준법 제43조, 제56조)
    overtime_pay_rate: int = Field(
        default=150,
        description="연장근로 가산율 (%)",
        ge=100,
        le=300,
    )
    night_pay_rate: int = Field(
        default=150,
        description="야간근로 가산율 (%)",
        ge=100,
        le=300,
    )
    holiday_pay_rate: int = Field(
        default=150,
        description="휴일근로 가산율 (%)",
        ge=100,
        le=300,
    )
    bonus: str | None = Field(default=None, description="상여금", max_length=200)
    allowances: str | None = Field(default=None, description="제 수당", max_length=200)
    payment_method: str = Field(default="계좌이체", description="임금 지급 방법", max_length=50)

    company_context: CompanyContext | None = Field(default=None, description="회사 정보")
    format: str = Field(default="pdf", description="출력 형식", pattern=r"^(pdf|docx)$")
    user_id: int | None = Field(default=None, description="사용자 ID (S3/DB 저장용)")
    company_id: int | None = Field(default=None, description="회사 ID")


class GenerateDocumentRequest(BaseModel):
    """범용 문서 생성 요청 스키마.

    Attributes:
        document_type: 문서 유형 키 (예: "nda", "service_agreement")
        params: 문서 필드 값
        format: 출력 형식 (pdf, docx)
        company_context: 회사 정보 (인증 시 자동 주입)
    """

    document_type: str = Field(description="문서 유형 키")
    params: dict[str, Any] = Field(default_factory=dict, description="문서 필드 값")
    format: str = Field(default="docx", description="출력 형식", pattern=r"^(pdf|docx)$")
    company_context: CompanyContext | None = Field(default=None, description="회사 정보")
    user_id: int | None = Field(default=None, description="사용자 ID (S3/DB 저장용)")
    company_id: int | None = Field(default=None, description="회사 ID")


class ModifyDocumentRequest(BaseModel):
    """문서 수정 요청 스키마.

    Attributes:
        file_content: 원본 파일 (base64 인코딩)
        file_name: 원본 파일명 (확장자 포함)
        instructions: 수정 지시사항
        format: 출력 형식 (pdf, docx)
        user_id: 사용자 ID (있으면 S3/DB 저장)
        document_id: 원본 문서 ID (버전관리)
    """

    file_content: str = Field(description="원본 파일 (base64 인코딩)")
    file_name: str = Field(description="원본 파일명 (확장자 포함)")
    instructions: str = Field(description="수정 지시사항", min_length=1, max_length=5000)
    format: str = Field(default="docx", description="출력 형식", pattern=r"^(pdf|docx)$")
    user_id: int | None = Field(default=None, description="사용자 ID (S3/DB 저장)")
    document_id: int | None = Field(default=None, description="원본 문서 ID (버전관리)")
