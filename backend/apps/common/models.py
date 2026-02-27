from sqlalchemy import BigInteger, Column, Date, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import deferred, relationship
from datetime import datetime
from config.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(36), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")


class Code(Base):
    __tablename__ = "code"

    code_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default="")
    main_code = Column(String(1), nullable=False, comment="U:유저, B:업종, A:에이전트, H:주관기관, R:지역")
    code = Column(String(8), unique=True, nullable=False)
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    google_email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), nullable=False)
    birth = Column(DateTime, nullable=True)
    # 기존 DB에 컬럼 미반영인 환경에서도 기본 조회가 깨지지 않도록 지연 로딩합니다.
    age = deferred(Column(Integer, nullable=True))
    type_code = Column(String(8), ForeignKey("code.code"), default="U0000002", comment="U0000001:관리자, U0000002:예비창업자, U0000003:사업자")
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    # 기존 DB에 컬럼 미반영인 환경에서도 기본 조회가 깨지지 않도록 지연 로딩합니다.
    last_announce_checked_at = deferred(Column(DateTime, nullable=True))
    # 사용자별 알림 설정 비트마스크(1:D-7, 2:D-3, 4:신규 공고, 8:답변 완료)
    notification_settings = deferred(Column(Integer, nullable=True))
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")

    # Relationships
    companies = relationship("Company", back_populates="user", cascade="save-update, merge")
    histories = relationship("History", back_populates="user", cascade="save-update, merge")


class Company(Base):
    __tablename__ = "company"

    company_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False)
    com_name = Column(String(255), nullable=False, default="")
    biz_num = Column(String(50), nullable=False, default="", comment="사업자등록번호")
    addr = Column(String(255), nullable=False, default="")
    open_date = Column(DateTime, nullable=True, comment="개업일")
    biz_code = Column(String(8), ForeignKey("code.code"), comment="업종코드")
    file_path = Column(String(500), nullable=False, default="", comment="사업자등록증 파일 경로")
    main_yn = Column(Boolean, default=False, comment="0: 일반, 1: 대표 기업")
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")

    # Relationships
    user = relationship("User", back_populates="companies")
    schedules = relationship("Schedule", back_populates="company", cascade="save-update, merge")


class History(Base):
    __tablename__ = "history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False)
    agent_code = Column(String(8), ForeignKey("code.code"), comment="답변 에이전트 코드")
    question = Column(Text, default="", comment="질문")
    answer = Column(Text, default="", comment="JSON 형태 저장 가능")
    parent_history_id = Column(Integer, ForeignKey("history.history_id", ondelete="SET NULL"), nullable=True, comment="부모 히스토리 ID")
    evaluation_data = Column(JSON, nullable=True, comment="RAGAS 평가 결과 (faithfulness, answer_relevancy, context_precision, contexts)")
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")

    # Relationships
    user = relationship("User", back_populates="histories")
    parent = relationship("History", remote_side=[history_id], backref="children")


class File(Base):
    __tablename__ = "file"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False, default="")
    file_path = Column(String(500), nullable=False, default="")
    history_id = Column(Integer, ForeignKey("history.history_id", ondelete="SET NULL"), nullable=True)
    company_id = Column(Integer, ForeignKey("company.company_id", ondelete="SET NULL"), nullable=True)
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")


class Announce(Base):
    __tablename__ = "announce"

    announce_id = Column(Integer, primary_key=True, autoincrement=True)
    ann_name = Column(String(255), nullable=False, default="", comment="공고 제목")
    source_type = Column(String(20), nullable=False, default="", comment="bizinfo | kstartup")
    source_id = Column(String(50), nullable=False, default="", comment="원본 API 공고 ID")
    target_desc = Column(Text, comment="지원대상")
    exclusion_desc = Column(Text, comment="제외대상")
    amount_desc = Column(Text, comment="지원금액")
    apply_start = Column(Date, comment="접수 시작일")
    apply_end = Column(Date, comment="접수 종료일")
    region = Column(String(100), default="", comment="지역")
    organization = Column(String(200), default="", comment="주관기관명")
    source_url = Column(String(500), default="", comment="원본 URL")
    doc_s3_key = Column(String(500), default="", comment="공고문 원본 파일 S3 키")
    form_s3_key = Column(String(500), default="", comment="신청양식 파일 S3 키")
    file_id = Column(Integer, ForeignKey("file.file_id", ondelete="SET NULL"), nullable=True, comment="공고 첨부파일")
    biz_code = Column(String(8), ForeignKey("code.code"), default="BA000000", comment="관련 업종코드")
    host_gov_code = Column(String(8), nullable=True, comment="주관기관 코드 (향후 매핑)")
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")

    # Relationships
    schedules = relationship("Schedule", back_populates="announce")


class Schedule(Base):
    __tablename__ = "schedule"

    schedule_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("company.company_id", ondelete="RESTRICT"), nullable=False)
    announce_id = Column(Integer, ForeignKey("announce.announce_id", ondelete="SET NULL"), nullable=True)
    schedule_name = Column(String(255), nullable=False, default="", comment="일정 제목")
    start_date = Column(DateTime, nullable=False, default=datetime.now, comment="시작일시")
    end_date = Column(DateTime, nullable=False, default=datetime.now, comment="종료일시")
    memo = Column(Text, default="", comment="메모")
    create_date = Column(DateTime, default=datetime.now)
    update_date = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    use_yn = Column(Boolean, nullable=False, default=True, comment="0: 미사용, 1: 사용")

    # Relationships
    company = relationship("Company", back_populates="schedules")
    announce = relationship("Announce", back_populates="schedules")


class JobLog(Base):
    """스케줄러 작업 실행 이력.

    lifespan에서 Base.metadata.create_all()로 자동 생성됩니다.
    apps/common/job_tracker.py의 track_job() 컨텍스트 매니저로 기록합니다.
    """

    __tablename__ = "job_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, comment="작업명 (예: token_cleanup)")
    status = Column(String(20), nullable=False, comment="started | success | failed")
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True, comment="실행 시간(ms)")
    record_count = Column(Integer, nullable=True, comment="처리된 레코드 수")
    error_msg = Column(Text, nullable=True, comment="실패 시 오류 메시지 (최대 2000자)")
    meta = Column(JSON, nullable=True, comment="추가 메타데이터")
