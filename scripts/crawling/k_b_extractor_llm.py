#!/usr/bin/env python3
"""순수 LLM 추출기 - 정규식 없음, 검증 없음, 그냥 LLM이 전부 처리"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import fitz
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF 전체 텍스트 추출"""
    try:
        doc = fitz.open(pdf_path)
        text = "\n\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        logger.error(f"PDF 텍스트 추출 실패: {e}")
        return ""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _extract_with_llm(client: OpenAI, text: str, vrf_str: str) -> dict:
    """LLM으로 한 번에 추출"""

    if vrf_str == "b":
        prompt = f"""다음은 정부 지원사업 공고문입니다.

이 공고문에서 다음 3가지 정보를 정확히 추출하세요:

1. **지원자격** (신청자격, 참가자격, 지원대상, 모집대상 등)
   - 누가 지원할 수 있는지에 대한 자격, 요건, 조건

2. **제외대상** (지원제외, 참여제한, 결격사유 등)
   - 누가 지원할 수 없는지에 대한 제외 조건, 제한 사항

3. **지원금액** (지원규모, 지원한도, 보조금액, 융자한도 등)
   - 얼마를 지원받는지에 대한 금액, 한도, 비율 정보

**중요 규칙**:
- 각 섹션의 원문을 최대한 그대로 유지하세요 (불릿, 번호, 들여쓰기 보존)
- 해당 섹션이 문서에 없으면 빈 문자열로 반환하세요
- 다른 섹션 내용을 섞지 마세요

**공고문**:
{text[:15000]}

다음 JSON 형식으로만 답변하세요:
{{
  "지원자격": "추출된 내용 (없으면 빈 문자열)",
  "제외대상": "추출된 내용 (없으면 빈 문자열)",
  "지원금액": "추출된 내용 (없으면 빈 문자열)"
}}
"""
    else:  # 'k'
        prompt = f"""다음은 정부 지원사업 공고문입니다.

이 공고문에서 다음 2가지 정보를 정확히 추출하세요:

1. **제외대상** (지원제외, 참여제한, 결격사유 등)
   - 누가 지원할 수 없는지에 대한 제외 조건, 제한 사항

2. **지원금액** (지원규모, 지원한도, 보조금액, 융자한도 등)
   - 얼마를 지원받는지에 대한 금액, 한도, 비율 정보

**중요 규칙**:
- 각 섹션의 원문을 최대한 그대로 유지하세요 (불릿, 번호, 들여쓰기 보존)
- 해당 섹션이 문서에 없으면 빈 문자열로 반환하세요
- 다른 섹션 내용을 섞지 마세요

**공고문**:
{text[:15000]}

다음 JSON 형식으로만 답변하세요:
{{
  "제외대상": "추출된 내용 (없으면 빈 문자열)",
  "지원금액": "추출된 내용 (없으면 빈 문자열)"
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0
        )

        result = json.loads(response.choices[0].message.content or "{}")

        # 토큰 사용량 로깅
        usage = response.usage
        logger.info(f"토큰 사용: input={usage.prompt_tokens}, output={usage.completion_tokens}, 총={usage.total_tokens}")

        return result

    except Exception as e:
        logger.error(f"LLM 추출 실패: {e}")
        return {}


def extract_simple(pdf_path: Path, vrf_str: str, client: OpenAI) -> dict:
    """
    순수 LLM 추출 (정규식, 검증 없음)

    Returns:
        {
            "file": "파일명",
            "지원자격": "내용",
            "제외대상": "내용",
            "지원금액": "내용",
            "metadata": {
                "processing_time": float,
                "total_tokens": int
            }
        }
    """
    start_time = time.time()

    result = {
        "file": pdf_path.name,
        "metadata": {
            "processing_time": 0.0,
            "total_tokens": 0
        }
    }

    # PDF 텍스트 추출
    text = _extract_text_from_pdf(pdf_path)

    if not text:
        logger.error(f"텍스트 추출 실패: {pdf_path.name}")
        if vrf_str == "b":
            result["지원자격"] = ""
            result["제외대상"] = ""
            result["지원금액"] = ""
        else:
            result["제외대상"] = ""
            result["지원금액"] = ""
        return result

    # LLM 추출
    logger.info(f"LLM 추출 시작: {pdf_path.name}")
    llm_result = _extract_with_llm(client, text, vrf_str)

    # 결과 합치기
    if vrf_str == "b":
        result["지원자격"] = llm_result.get("지원자격", "")
        result["제외대상"] = llm_result.get("제외대상", "")
        result["지원금액"] = llm_result.get("지원금액", "")
    else:
        result["제외대상"] = llm_result.get("제외대상", "")
        result["지원금액"] = llm_result.get("지원금액", "")

    # 메타데이터
    result["metadata"]["processing_time"] = time.time() - start_time

    return result


def process_pdfs_simple(
    pdf_folder: Path,
    vrf_str: str,
    output_jsonl: Optional[Path] = None
) -> list[dict]:
    """여러 PDF 파일 배치 처리"""

    client = OpenAI()
    pdf_files = list(pdf_folder.glob("*.pdf"))

    logger.info(f"총 {len(pdf_files)}개 PDF 처리 시작")

    results = []

    for pdf_path in pdf_files:
        logger.info(f"\n{'='*80}")
        logger.info(f"파일: {pdf_path.name}")
        logger.info(f"{'='*80}")

        result = extract_simple(pdf_path, vrf_str, client)
        results.append(result)

    # 결과 저장
    if output_jsonl:
        with open(output_jsonl, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.info(f"\n결과 저장: {output_jsonl}")

    return results


if __name__ == "__main__":
    import sys
    import os

    # API 키 설정
    if not os.getenv("OPENAI_API_KEY"):
        with open("../.env") as f:
            for line in f:
                if "OPENAI_API_KEY" in line:
                    os.environ["OPENAI_API_KEY"] = line.split("=")[1].strip()

    if len(sys.argv) < 3:
        print("사용법: python simple_llm_extractor.py <PDF폴더> <b|k> [출력파일.jsonl]")
        sys.exit(1)

    pdf_folder = Path(sys.argv[1])
    vrf_str = sys.argv[2]
    output_file = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    if not pdf_folder.exists():
        print(f"폴더 없음: {pdf_folder}")
        sys.exit(1)

    if vrf_str not in ("b", "k"):
        print("vrf_str은 'b' 또는 'k'만 가능")
        sys.exit(1)

    results = process_pdfs_simple(pdf_folder, vrf_str, output_file)

    # 결과 요약
    print(f"\n{'='*80}")
    print("추출 결과 요약")
    print(f"{'='*80}")

    for r in results:
        print(f"\n[{r['file']}]")

        if vrf_str == "b":
            print(f"  지원자격: {len(r.get('지원자격', ''))}자")
        print(f"  제외대상: {len(r.get('제외대상', ''))}자")
        print(f"  지원금액: {len(r.get('지원금액', ''))}자")
        print(f"  처리시간: {r['metadata']['processing_time']:.2f}초")
