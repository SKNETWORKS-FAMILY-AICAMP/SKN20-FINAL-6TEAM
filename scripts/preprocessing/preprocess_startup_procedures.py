"""
창업절차 가이드 전처리 스크립트
startup_procedures.json → RAG용 표준 형식으로 변환
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any

# 상수 정의
SOURCE_NAME = "생활법령정보, 국세청"
SOURCE_URL = "https://easylaw.go.kr/"
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


def serialize_value(value: Any) -> str:
    """값을 문자열로 변환"""
    if isinstance(value, str):
        return value
    elif isinstance(value, list):
        # 리스트의 각 항목 처리
        if not value:
            return ""
        
        # 첫 번째 항목으로 타입 판단
        first_item = value[0]
        
        if isinstance(first_item, dict):
            # 딕셔너리 리스트인 경우 → \n으로 구분
            parts = []
            for item in value:
                if 'type' in item and 'description' in item:
                    parts.append(f"{item['type']}: {item['description']}")
                elif 'offense' in item and 'penalty' in item:
                    parts.append(f"{item['offense']}: {item['penalty']}")
                else:
                    # 일반 딕셔너리: key: value 형식
                    dict_parts = [f"{k}: {serialize_value(v)}" for k, v in item.items()]
                    parts.append(", ".join(dict_parts))
            return "\n".join(parts)
        else:
            # 문자열 리스트인 경우 → ,로 구분
            parts = [serialize_value(item) for item in value]
            return ", ".join(parts)
    elif isinstance(value, dict):
        # 딕셔너리: key: value 형식
        parts = [f"{k}: {serialize_value(v)}" for k, v in value.items()]
        return "\n".join(parts)
    else:
        return str(value)


def flatten_content(items: List[Dict[str, Any]]) -> str:
    """
    items 배열에서 section과 실제 내용을 추출하여 하나의 문자열로 변환
    [section명]내용 형식으로 출력
    """
    content_parts = []
    
    for item in items:
        section = item.get("section", "")
        if not section:
            continue
        
        # section 외의 모든 키-값 추출
        item_data = {k: v for k, v in item.items() if k != "section"}
        
        # 내용 직렬화
        if item_data:
            if len(item_data) == 1:
                # section 제목과 내용을 한 줄로
                content_parts.append(f"[{section}] {serialize_value(list(item_data.values())[0])}")
            else:
                # 여러 키가 있는 경우도 한 줄로
                content_parts.append(f"[{section}] {serialize_value(item_data)}")
        else:
            content_parts.append(f"[{section}]")
    
    return "\n\n".join(content_parts)


def extract_metadata(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    items에서 section 제목 목록 추출 (메타데이터용)
    """
    sections = [item.get("section", "") for item in items if item.get("section")]
    return {
        "sections": sections
    }


def transform_category(category_data: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    """
    카테고리 데이터를 표준 형식으로 변환
    """
    csm_seq = category_data.get("csmSeq", "")
    category = category_data.get("category", "")
    items = category_data.get("items", [])
    
    return {
        "id": f"STARTUP_PROCEDURES_{csm_seq}",
        "type": DOCUMENT_TYPE,
        "domain": DOCUMENT_DOMAIN,
        "title": category,
        "content": flatten_content(items),
        "source": {
            "name": SOURCE_NAME,
            "url": SOURCE_URL,
            "collected_at": collected_at
        },
        "metadata": extract_metadata(items)
    }


def preprocess_startup_procedures(input_path: str, output_path: str) -> None:
    """
    메인 전처리 함수
    """
    print(f"📂 입력 파일 로드 중: {input_path}")
    data = load_json(input_path)
    
    collected_at = data.get("collected_at", datetime.now().strftime("%Y-%m-%d"))
    categories = data.get("categories", [])
    
    print(f"📊 총 {len(categories)}개 카테고리 발견")
    
    # 변환 수행
    processed_data = []
    for idx, category in enumerate(categories, 1):
        try:
            transformed = transform_category(category, collected_at)
            processed_data.append(transformed)
            print(f"✅ [{idx}/{len(categories)}] {category.get('category')} 변환 완료")
        except Exception as e:
            print(f"❌ [{idx}/{len(categories)}] {category.get('category')} 변환 실패: {e}")
    
    # 출력 디렉토리 생성
    output_dir = os.path.dirname(output_path)
    if output_dir:  # 빈 문자열이 아닌 경우에만 생성
        os.makedirs(output_dir, exist_ok=True)
    
    # 결과 저장 (각 문서를 한 줄씩 JSONL 형식으로)
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in processed_data:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')
    
    print(f"\n✨ 전처리 완료! {len(processed_data)}개 문서 생성")
    print(f"💾 저장 위치: {output_path}")


if __name__ == "__main__":
    # 스크립트가 있는 디렉토리 (프로젝트 루트)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 환경 변수에서 경로 읽기, 없으면 기본값 사용
    input_file = os.getenv(
        "STARTUP_PROCEDURES_INPUT",
        os.path.join(script_dir, "startup_procedures.json")
    )
    output_file = os.getenv(
        "STARTUP_PROCEDURES_OUTPUT",
        os.path.join(script_dir, "startup_procedures_filtered.json")
    )
    
    print(f"🔍 입력 파일 경로: {input_file}")
    print(f"💾 출력 파일 경로: {output_file}")
    
    preprocess_startup_procedures(input_file, output_file)