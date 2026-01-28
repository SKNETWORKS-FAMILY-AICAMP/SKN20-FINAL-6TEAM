"""
업종별 창업가이드 전처리 스크립트
1. 원본 데이터에서 필요한 필드만 추출하여 JSON 저장
2. 추출된 데이터를 RAG용 표준 형식으로 변환하여 JSONL 저장
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

# 상수 정의
SOURCE_NAME = "정부24+생활법령+인허가정보 "
SOURCE_URL = "https://www.easylaw.go.kr/,https://plus.gov.kr/?bypass=dusakf!,https://www.localdata.go.kr/"
DOCUMENT_TYPE = "startup_funding"
DOCUMENT_DOMAIN = "startup"


def load_json(filepath: str) -> Dict[str, Any]:
    """JSON 파일 로드"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {filepath}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 오류: {e}")


def filter_industries(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    원본 데이터에서 필요한 필드만 추출
    """
    print("\n📋 Step 1: 필드 필터링 시작")
    
    industries = data.get("industries", [])
    new_industries = []
    
    for industry in industries:
        # 필수 필드가 모두 있는 경우만 추가
        if all(key in industry for key in ["code", "name", "license_type", "required_licenses", "common_procedure"]):
            new_industry = {
                "code": industry["code"],
                "name": industry["name"],
                "license_type": industry["license_type"],
                "required_licenses": industry["required_licenses"],
                "common_procedure": industry["common_procedure"]
            }
            new_industries.append(new_industry)
    
    print(f"✅ 총 {len(new_industries)}개의 업종 데이터를 추출했습니다")
    return new_industries


def transform_required_licenses(licenses: List[Dict[str, Any]]) -> str:
    """required_licenses를 content 형식으로 변환"""
    if not licenses:
        return ""
    
    lines = []
    for license_info in licenses:
        parts = []
        parts.append(f"type: {license_info.get('type', '')}")
        parts.append(f"required: {str(license_info.get('required', False)).lower()}")
        if 'condition' in license_info:
            parts.append(f"condition: {license_info['condition']}")
        parts.append(f"authority: {license_info.get('authority', '')}")
        lines.append(", ".join(parts))
    
    return "\n ".join(lines)


def transform_common_procedure(procedure: Dict[str, str]) -> str:
    """common_procedure를 content 형식으로 변환"""
    if not procedure:
        return ""
    
    parts = []
    for key, value in sorted(procedure.items()):
        parts.append(f"{key}: {value}")
    
    return ", ".join(parts)


def create_content(industry: Dict[str, Any]) -> str:
    """
    업종 데이터를 content 문자열로 변환
    """
    content_parts = []
    
    # 필요 인허가
    required_licenses = industry.get('required_licenses', [])
    if required_licenses:
        licenses_text = transform_required_licenses(required_licenses)
        content_parts.append(f"[required_licenses] {licenses_text}")
    
    # 창업 절차
    common_procedure = industry.get('common_procedure', {})
    if common_procedure:
        procedure_text = transform_common_procedure(common_procedure)
        content_parts.append(f"[common_procedure] {procedure_text}")
    
    return "\n\n".join(content_parts)


def extract_metadata(industry: Dict[str, Any]) -> Dict[str, Any]:
    """
    메타데이터 추출
    """
    sections = []
    
    if industry.get('required_licenses'):
        sections.append("required_licenses")
    if industry.get('common_procedure'):
        sections.append("common_procedure")
    
    return {
        "sections": sections,
        "license_type": industry.get('license_type', ''),
        "industry_code": industry.get('code', '')
    }


def transform_industry(industry: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    """
    업종 데이터를 표준 형식으로 변환
    """
    code = industry.get("code", "")
    name = industry.get("name", "")
    
    return {
        "id": f"STARTUP_GUIDE_{code}",
        "type": DOCUMENT_TYPE,
        "domain": DOCUMENT_DOMAIN,
        "title": name,
        "content": create_content(industry),
        "source": {
            "name": SOURCE_NAME,
            "url": SOURCE_URL,
            "collected_at": collected_at
        },
        "metadata": extract_metadata(industry)
    }


def preprocess_industry_guide(input_path: str, output_path: str) -> None:
    """
    메인 전처리 함수
    1. 원본 데이터에서 필요한 필드만 추출
    2. RAG용 표준 형식으로 변환
    3. JSONL 파일로 저장
    """
    print(f"📂 입력 파일 로드 중: {input_path}")
    data = load_json(input_path)
    
    print(f"📊 총 {len(data.get('industries', []))}개 업종 발견")
    
    # Step 1: 필터링
    filtered_industries = filter_industries(data)
    
    # Step 2: RAG 형식으로 변환
    print("\n🔄 Step 2: RAG 형식 변환 시작")
    collected_at = datetime.now().strftime("%Y-%m-%d")
    processed_data = []
    
    for idx, industry in enumerate(filtered_industries, 1):
        try:
            transformed = transform_industry(industry, collected_at)
            processed_data.append(transformed)
            if idx % 100 == 0:
                print(f"✅ [{idx}/{len(filtered_industries)}] 변환 중...")
        except Exception as e:
            print(f"❌ [{idx}/{len(filtered_industries)}] {industry.get('name', 'Unknown')} 변환 실패: {e}")
    
    # Step 3: 출력 디렉토리 생성 및 저장
    print("\n💾 Step 3: 최종 파일 저장 중...")
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # 결과 저장 (각 문서를 한 줄씩 JSONL 형식으로)
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in processed_data:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')
    
    print(f"\n✨ 전처리 완료! {len(processed_data)}개 문서 생성")
    print(f"💾 저장 위치: {output_path}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    input_file = os.getenv(
        "INDUSTRY_GUIDE_INPUT",
        os.path.join(script_dir, "industry_startup_guide.json")
    )
    output_file = os.getenv(
        "INDUSTRY_GUIDE_OUTPUT",
        os.path.join(script_dir, "industry_startup_guide_filtered.jsonl")
    )
    
    print(f"🔍 입력 파일 경로: {input_file}")
    print(f"💾 출력 파일 경로: {output_file}")
    
    preprocess_industry_guide(input_file, output_file)
