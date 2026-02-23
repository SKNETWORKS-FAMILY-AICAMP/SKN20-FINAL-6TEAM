"""액션 실행기 모듈.

문서 생성 등의 액션을 실행하는 Action Executor를 구현합니다.
"""

import base64
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from schemas.request import CompanyContext, ContractRequest
from schemas.response import DocumentResponse
from utils.config import get_settings


class ActionExecutor:
    """액션 실행기 클래스.

    문서 생성 등의 액션을 실행합니다.

    지원 문서:
    - 근로계약서 (PDF)
    - 취업규칙 템플릿 (DOCX)
    - 사업계획서 템플릿 (DOCX)

    Attributes:
        settings: 설정 객체
        output_dir: 출력 디렉토리

    Example:
        >>> executor = ActionExecutor()
        >>> result = executor.generate_labor_contract(contract_data)
        >>> print(result.file_name)
    """

    def __init__(self):
        """ActionExecutor를 초기화합니다."""
        self.settings = get_settings()
        self.output_dir = Path(__file__).parent.parent / "output"
        self.output_dir.mkdir(exist_ok=True)

    def generate_labor_contract(
        self,
        request: ContractRequest,
    ) -> DocumentResponse:
        """근로계약서를 생성합니다.

        Args:
            request: 근로계약서 생성 요청

        Returns:
            문서 생성 응답
        """
        try:
            if request.format == "pdf":
                return self._generate_contract_pdf(request)
            elif request.format == "docx":
                return self._generate_contract_docx(request)
            else:
                return DocumentResponse(
                    success=False,
                    document_type="labor_contract",
                    message=f"지원하지 않는 형식: {request.format} (pdf 또는 docx만 가능)",
                )
        except Exception as e:
            return DocumentResponse(
                success=False,
                document_type="labor_contract",
                message=f"근로계약서 생성 실패: {str(e)}",
            )

    def _generate_contract_pdf(
        self,
        request: ContractRequest,
    ) -> DocumentResponse:
        """근로계약서 PDF를 생성합니다."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        # 버퍼 생성
        buffer = BytesIO()

        # PDF 문서 생성
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        # 스타일 설정
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Title"],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # 가운데 정렬
        )
        normal_style = ParagraphStyle(
            "Normal",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
        )

        # 내용 구성
        elements = []

        # 제목
        elements.append(Paragraph("표준 근로계약서", title_style))
        elements.append(Spacer(1, 20))

        # 계약 당사자 (사용자 입력 이스케이프)
        company_name = "회사명 미기재"
        if request.company_context:
            company_name = request.company_context.company_name or company_name

        elements.append(Paragraph(
            f"<b>사업주(갑)</b>: {xml_escape(company_name)}",
            normal_style
        ))
        elements.append(Paragraph(
            f"<b>근로자(을)</b>: {xml_escape(request.employee_name)}",
            normal_style
        ))
        elements.append(Spacer(1, 20))

        # 계약 내용
        contract_type = "무기계약" if request.is_permanent else "기간제 계약"
        contract_period = "정함 없음"
        if not request.is_permanent and request.contract_end_date:
            contract_period = f"{request.contract_start_date} ~ {request.contract_end_date}"

        # 사용자 입력 이스케이프 (ReportLab HTML 인젝션 방지)
        esc = xml_escape
        content = f"""
        <b>제1조 (계약 유형)</b><br/>
        본 계약은 {esc(contract_type)}입니다.<br/><br/>

        <b>제2조 (계약 기간)</b><br/>
        계약 시작일: {esc(request.contract_start_date)}<br/>
        계약 기간: {esc(contract_period)}<br/><br/>

        <b>제3조 (근무 장소)</b><br/>
        {esc(request.workplace)}<br/><br/>

        <b>제4조 (업무 내용)</b><br/>
        직위: {esc(request.job_title)}<br/>
        담당 업무: {esc(request.job_description)}<br/><br/>

        <b>제5조 (근무 시간)</b><br/>
        근무 시간: {esc(request.work_start_time)} ~ {esc(request.work_end_time)}<br/>
        휴게 시간: {esc(request.rest_time)}<br/>
        근무 요일: {esc(request.work_days)}<br/><br/>

        <b>제6조 (임금)</b><br/>
        기본급: 월 {request.base_salary:,}원<br/>
        지급일: 매월 {request.payment_date}일<br/><br/>

        <b>제7조 (기타)</b><br/>
        본 계약서에 명시되지 않은 사항은 근로기준법 및 관계 법령에 따릅니다.
        """

        elements.append(Paragraph(content, normal_style))
        elements.append(Spacer(1, 40))

        # 서명란
        today = datetime.now().strftime("%Y년 %m월 %d일")
        elements.append(Paragraph(f"작성일: {today}", normal_style))
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("사업주(갑):                    (인)", normal_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("근로자(을):                    (인)", normal_style))

        # PDF 빌드
        doc.build(elements)

        # 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"labor_contract_{timestamp}_{uuid.uuid4().hex[:6]}.pdf"
        file_path = self.output_dir / file_name

        buffer.seek(0)
        with open(file_path, "wb") as f:
            f.write(buffer.read())

        # base64 인코딩
        buffer.seek(0)
        file_content = base64.b64encode(buffer.read()).decode("utf-8")

        return DocumentResponse(
            success=True,
            document_type="labor_contract",
            file_path=str(file_path),
            file_name=file_name,
            file_content=file_content,
            message="근로계약서가 생성되었습니다.",
        )

    def _generate_contract_docx(
        self,
        request: ContractRequest,
    ) -> DocumentResponse:
        """근로계약서 DOCX를 생성합니다."""
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        # 문서 생성
        doc = Document()

        # 제목
        title = doc.add_heading("표준 근로계약서", level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 계약 당사자
        company_name = "회사명 미기재"
        if request.company_context:
            company_name = request.company_context.company_name or company_name

        doc.add_paragraph(f"사업주(갑): {company_name}")
        doc.add_paragraph(f"근로자(을): {request.employee_name}")
        doc.add_paragraph()

        # 계약 내용
        contract_type = "무기계약" if request.is_permanent else "기간제 계약"
        contract_period = "정함 없음"
        if not request.is_permanent and request.contract_end_date:
            contract_period = f"{request.contract_start_date} ~ {request.contract_end_date}"

        doc.add_heading("제1조 (계약 유형)", level=2)
        doc.add_paragraph(f"본 계약은 {contract_type}입니다.")

        doc.add_heading("제2조 (계약 기간)", level=2)
        doc.add_paragraph(f"계약 시작일: {request.contract_start_date}")
        doc.add_paragraph(f"계약 기간: {contract_period}")

        doc.add_heading("제3조 (근무 장소)", level=2)
        doc.add_paragraph(request.workplace)

        doc.add_heading("제4조 (업무 내용)", level=2)
        doc.add_paragraph(f"직위: {request.job_title}")
        doc.add_paragraph(f"담당 업무: {request.job_description}")

        doc.add_heading("제5조 (근무 시간)", level=2)
        doc.add_paragraph(f"근무 시간: {request.work_start_time} ~ {request.work_end_time}")
        doc.add_paragraph(f"휴게 시간: {request.rest_time}")
        doc.add_paragraph(f"근무 요일: {request.work_days}")

        doc.add_heading("제6조 (임금)", level=2)
        doc.add_paragraph(f"기본급: 월 {request.base_salary:,}원")
        doc.add_paragraph(f"지급일: 매월 {request.payment_date}일")

        doc.add_heading("제7조 (기타)", level=2)
        doc.add_paragraph("본 계약서에 명시되지 않은 사항은 근로기준법 및 관계 법령에 따릅니다.")

        # 서명란
        doc.add_paragraph()
        today = datetime.now().strftime("%Y년 %m월 %d일")
        doc.add_paragraph(f"작성일: {today}")
        doc.add_paragraph()
        doc.add_paragraph("사업주(갑):                    (인)")
        doc.add_paragraph("근로자(을):                    (인)")

        # 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"labor_contract_{timestamp}_{uuid.uuid4().hex[:6]}.docx"
        file_path = self.output_dir / file_name

        doc.save(file_path)

        # base64 인코딩
        with open(file_path, "rb") as f:
            file_content = base64.b64encode(f.read()).decode("utf-8")

        return DocumentResponse(
            success=True,
            document_type="labor_contract",
            file_path=str(file_path),
            file_name=file_name,
            file_content=file_content,
            message="근로계약서가 생성되었습니다.",
        )

    def generate_business_plan_template(
        self,
        format: str = "docx",
    ) -> DocumentResponse:
        """사업계획서 템플릿을 생성합니다.

        Args:
            format: 출력 형식 (docx)

        Returns:
            문서 생성 응답
        """
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            # 문서 생성
            doc = Document()

            # 제목
            title = doc.add_heading("사업계획서", level=0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 목차
            sections = [
                ("1. 사업 개요", [
                    "1.1 사업 아이템 소개",
                    "1.2 창업 동기 및 비전",
                    "1.3 사업 목표",
                ]),
                ("2. 시장 분석", [
                    "2.1 시장 규모 및 성장성",
                    "2.2 경쟁 현황",
                    "2.3 타겟 고객",
                ]),
                ("3. 제품/서비스", [
                    "3.1 제품/서비스 설명",
                    "3.2 차별화 포인트",
                    "3.3 가격 정책",
                ]),
                ("4. 마케팅 전략", [
                    "4.1 마케팅 목표",
                    "4.2 홍보 채널",
                    "4.3 고객 확보 전략",
                ]),
                ("5. 운영 계획", [
                    "5.1 조직 구성",
                    "5.2 인력 계획",
                    "5.3 운영 프로세스",
                ]),
                ("6. 재무 계획", [
                    "6.1 소요 자금",
                    "6.2 매출 계획",
                    "6.3 손익 계획",
                ]),
            ]

            for section_title, subsections in sections:
                doc.add_heading(section_title, level=1)
                for subsection in subsections:
                    doc.add_heading(subsection, level=2)
                    doc.add_paragraph("[내용을 작성하세요]")
                    doc.add_paragraph()

            # 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"business_plan_template_{timestamp}_{uuid.uuid4().hex[:6]}.docx"
            file_path = self.output_dir / file_name

            doc.save(file_path)

            # base64 인코딩
            with open(file_path, "rb") as f:
                file_content = base64.b64encode(f.read()).decode("utf-8")

            return DocumentResponse(
                success=True,
                document_type="business_plan",
                file_path=str(file_path),
                file_name=file_name,
                file_content=file_content,
                message="사업계획서 템플릿이 생성되었습니다.",
            )

        except Exception as e:
            return DocumentResponse(
                success=False,
                document_type="business_plan",
                message=f"사업계획서 템플릿 생성 실패: {str(e)}",
            )

    def execute_action(
        self,
        action_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """액션을 실행합니다.

        Args:
            action_type: 액션 유형
            params: 액션 파라미터

        Returns:
            실행 결과
        """
        if action_type == "document_generation":
            doc_type = params.get("document_type")
            if doc_type == "labor_contract":
                request = ContractRequest(**params)
                result = self.generate_labor_contract(request)
                return result.model_dump()
            elif doc_type == "business_plan":
                result = self.generate_business_plan_template()
                return result.model_dump()

        return {"success": False, "message": f"지원하지 않는 액션: {action_type}"}
