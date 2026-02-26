from pydantic import BaseModel, Field

MAX_MESSAGE_LENGTH = 2000


class RagChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=5000)


class RagChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: list[RagChatMessage] = Field(default_factory=list, max_length=50)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)


class ContractGenerateRequest(BaseModel):
    employee_name: str = Field(..., min_length=1, max_length=100)
    job_title: str = Field(..., min_length=1, max_length=100)
    job_description: str = Field(..., min_length=1, max_length=500)
    contract_start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    workplace: str = Field(..., min_length=1, max_length=200)
    base_salary: int = Field(..., gt=0)
    is_permanent: bool = Field(default=True)
    contract_end_date: str | None = Field(default=None)
    work_start_time: str = Field(default="09:00")
    work_end_time: str = Field(default="18:00")
    rest_time: str = Field(default="12:00-13:00")
    work_days: str = Field(default="월~금")
    payment_date: int = Field(default=25, ge=1, le=31)
    holidays: str = Field(
        default="주휴일 및 근로자의 날, 관공서의 공휴일에 관한 규정에 따른 공휴일",
        max_length=300,
    )
    annual_leave_days: int = Field(default=15, ge=0, le=365)
    is_part_time: bool = Field(default=False)
    weekly_work_hours: float | None = Field(default=None, ge=0, le=168)
    overtime_pay_rate: int = Field(default=150, ge=100, le=300)
    night_pay_rate: int = Field(default=150, ge=100, le=300)
    holiday_pay_rate: int = Field(default=150, ge=100, le=300)
    bonus: str | None = Field(default=None, max_length=200)
    allowances: str | None = Field(default=None, max_length=200)
    payment_method: str = Field(default="계좌이체", max_length=50)
    format: str = Field(default="pdf", pattern=r"^(pdf|docx)$")
