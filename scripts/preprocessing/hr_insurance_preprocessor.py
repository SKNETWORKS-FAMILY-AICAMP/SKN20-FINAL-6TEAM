"""
Human Resources PDF 전처리 파일 => (4대보험 전용)
- 4대보험 가이드: 섹션별 파싱
- 텍스트 정제 (null 문자, 줄바꿈 등 처리)
- JSON 및 JSONL 형식으로 저장
"""

import os
import re
import json
from datetime import datetime
from pypdf import PdfReader
from typing import List, Dict, Optional, Tuple, Any


class HRPDFPreprocessor:
    """HR PDF 전처리 클래스"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or "preprocessed_output"
        os.makedirs(self.output_dir, exist_ok=True)

    def clean_text(self, text: str) -> str:
        """텍스트 정제 - null 문자, 불필요한 공백 등 제거"""
        if not text:
            return ""

        # null 문자 제거
        text = text.replace('\x00', ' ')

        # 연속된 공백을 하나로
        text = re.sub(r'[ \t]+', ' ', text)

        # 줄 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # 3개 이상 연속 줄바꿈을 2개로
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()



    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF에서 텍스트 추출"""
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
        return self.clean_text(text)

    # ========================================
    # 4대보험
    # ========================================

    def parse_guide_document(self, text: str, filename: str) -> List[Dict[str, Any]]:
        """가이드 문서 파싱 (4대보험 등) - 새 통일 스키마 반환"""
        documents = []
        collected_at = datetime.now().isoformat(timespec="seconds")

        # 주요 섹션 헤더 패턴 (독립적인 섹션으로 분리)
        main_sections = [
            ("국민연금", "국민연금"),
            ("국민건강보험", "국민건강보험"),
            ("산업재해보상보험", "산업재해보상보험"),
            ("산재보험", "산업재해보상보험"),
            ("고용보험", "고용보험"),
            ("4대 사회보험", "4대사회보험_개요"),
            ("사회보험 개요", "4대사회보험_개요"),
            ("취업규칙", "취업규칙")
        ]

        # 섹션별로 내용 분리
        section_contents = {}

        lines = text.split('\n')
        current_section = "개요"
        current_content = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                current_content.append("")
                continue

            # 새 섹션 시작 확인 (라인이 섹션 헤더로만 구성된 경우)
            new_section = None
            for keyword, section_name in main_sections:
                # 헤더는 보통 짧고 키워드를 포함
                if keyword in line_stripped and len(line_stripped) < 30:
                    # 숫자로 시작하는 섹션 헤더 (예: "1. 국민연금")
                    if re.match(r'^[\d\.\s]*' + re.escape(keyword), line_stripped):
                        new_section = section_name
                        break
                    # 키워드만 있는 경우
                    elif line_stripped == keyword or line_stripped.endswith(keyword):
                        new_section = section_name
                        break

            if new_section:
                # 이전 섹션 저장
                if current_content:
                    content_text = '\n'.join(current_content).strip()
                    if len(content_text) > 100:  # 최소 100자 이상
                        if current_section not in section_contents:
                            section_contents[current_section] = []
                        section_contents[current_section].append(content_text)

                current_section = new_section
                current_content = []
            else:
                current_content.append(line_stripped)

        # 마지막 섹션 저장
        if current_content:
            content_text = '\n'.join(current_content).strip()
            if len(content_text) > 100:
                if current_section not in section_contents:
                    section_contents[current_section] = []
                section_contents[current_section].append(content_text)

        # 새 통일 스키마로 문서 생성
        for index, (section_name, contents) in enumerate(section_contents.items(), 1):
            full_content = '\n\n'.join(contents)
            title = f"{section_name} 안내"
            content_with_title = f"{title}\n\n{full_content}"
            
            doc = {
                "id": f"MAGOR_INSURNACE_HR_{index}",
                "type": "labor",
                "domain": "guide",
                "title": title,
                "content": content_with_title,
                "source": {
                    "name": filename,
                    "url": "",
                    "collected_at": collected_at
                },
                "effective_date": "",
                "metadata": {
                    "category": "가이드",
                    "chapter": "4대 사회보험",
                    "chapter_title": "4대 사회보험 및 취업규칙 신고",
                    "section": section_name,
                    "section_title": section_name
                }
            }
            documents.append(doc)

        return documents

    def process_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """단일 PDF 처리 - 4대보험 가이드만 처리"""
        print(f"처리 중: {pdf_path}")

        filename = os.path.basename(pdf_path)
        text = self.extract_text_from_pdf(pdf_path)

        # 4대보험 가이드 처리
        documents = self.parse_guide_document(text, filename)

        print(f"  추출된 문서 수: {len(documents)}")
        return documents

    def process_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """디렉토리 내 모든 PDF 처리 - 새 통일 스키마 반환"""
        all_documents = []

        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_path = os.path.join(root, file)
                    documents = self.process_pdf(pdf_path)
                    all_documents.extend(documents)

        return all_documents

    def save_to_json(self, documents: List[Dict[str, Any]], output_filename: str = "hr_documents.json"):
        """결과를 JSON으로 저장 (새 통일 스키마)"""
        output_path = os.path.join(self.output_dir, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(documents, f, ensure_ascii=False, indent=2)

        print(f"\n저장 완료: {output_path}")
        print(f"총 문서 수: {len(documents)}")

        return output_path

    def save_to_jsonl(self, documents: List[Dict[str, Any]], output_filename: str = "hr_documents.jsonl"):
        """결과를 JSONL로 저장 (RAG용, 새 통일 스키마)"""
        output_path = os.path.join(self.output_dir, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n')

        print(f"JSONL 저장 완료: {output_path}")
        return output_path


def main():
    """메인 실행 함수"""
    # 설정
    input_pdf = "../../data/origin/labor/[PDF]중소벤처기업 4대보험 신고.pdf"  # 4대보험 PDF 파일 경로
    output_dir = "../../data/preprocessed/labor"

    # 전처리기 초기화
    preprocessor = HRPDFPreprocessor(output_dir=output_dir)

    print("=" * 60)
    print("4대보험 PDF 전처리 시작")
    print("=" * 60)
    print(f"입력 파일: {input_pdf}")
    print(f"출력 디렉토리: {output_dir}")
    print()

    # PDF 파일 처리
    documents = preprocessor.process_pdf(input_pdf)

    # 결과 저장
    print("\n" + "=" * 60)
    print("결과 저장 중...")
    print("=" * 60)

    # JSON 저장
    # preprocessor.save_to_json(documents, "hr_4insurance_documents.json")

    # JSONL 저장 (RAG용)
    preprocessor.save_to_jsonl(documents, "hr_4insurance_documents.jsonl")

if __name__ == "__main__":
    main()
