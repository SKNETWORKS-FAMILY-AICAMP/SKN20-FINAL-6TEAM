"""4대보험 사업자 교육 PDF 전처리 (OpenAI GPT-4o Vision API)

OpenAI GPT-4o Vision API를 사용하여 이미지 기반 PDF에서 텍스트와 테이블을 추출하고,
대제목(장)/중제목(절) 단위로 분할하여 RAG용 JSONL 파일을 생성합니다.

처리 흐름:
    PDF → pymupdf 페이지별 이미지 렌더링 → base64 인코딩
        → GPT-4o Vision API (페이지 유형 분류 + 문맥 인식 텍스트 추출)
        → [TYPE: content|form|divider|cover] 태그 파싱
        → 응답 캐싱 (JSON)
        → 대제목/중제목 파싱 (form/cover 스킵)
        → 통합 스키마 JSONL 출력

대제목: 그래픽 구분 페이지 (예: "Ⅱ 국민연금 제도 안내") → id 접두어 (NP_001)
중제목: 번호+제목 (예: "01 국민연금 제도란?") → title 필드
content: 중제목 기준으로 한 라인 구성

입력: scripts/4대보험_사업자_교육.pdf (또는 data/4대보험_사업자_교육.pdf)
출력: data/preprocessed/labor/hr_insurance_edu.jsonl
"""

import argparse
import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz  # pymupdf
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

# 프로젝트 루트의 .env 로드
_PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# API 응답 캐시 파일 경로
_CACHE_PATH = Path(__file__).parent / "_cache_openai_response.json"

# LLM 분할 결과 캐시 파일 경로
_SPLIT_CACHE_PATH = Path(__file__).parent / "_cache_split_sections.json"

# 대제목 구분 페이지 감지 키워드
CHAPTER_DIVIDER_KEYWORDS: list[tuple[str, str, str]] = [
    # (keyword, chapter_name, id_prefix)
    ("4대사회보험", "4대사회보험 포털사이트 이용방법", "SOC"),
    ("국민연금", "국민연금 제도 안내", "NP"),
    ("건강보험", "국민건강보험 제도 안내", "NHI"),
    ("고용산재보험", "고용·산재보험 제도 안내", "WCEI"),
    ("고용보험", "고용·산재보험 제도 안내", "WCEI"),
    ("산재보험", "고용·산재보험 제도 안내", "WCEI"),
]

# 중제목 패턴: "01 제목", "## 01 제목" 등 (선택적 마크다운 헤딩 + 2자리 숫자 + 공백 + 제목)
SUBTITLE_PATTERN = re.compile(r"^(?:#+\s+)?(\d{2})\s+(.+)")

MIN_SECTION_LENGTH = 50

# 거부 텍스트 필터링 키워드
REFUSAL_KEYWORDS: list[str] = [
    "죄송", "I'm sorry", "I can't", "분석할 수 없", "도와드리겠습니다",
    "추가적인 정보가 필요하다면", "텍스트가 포함되어 있지 않",
]

# LLM 분할 대상 문서 길이 임계값 (자)
SPLIT_THRESHOLD = 1500


def _format_page_range(sorted_pages: list[int]) -> str:
    """정렬된 페이지 목록 → "1-3,5,7-9" 형태의 축약 문자열."""
    if not sorted_pages:
        return ""
    ranges: list[str] = []
    start = prev = sorted_pages[0]
    for p in sorted_pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = p
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(ranges)


def _count_page_types(pages_data: list[dict[str, Any]]) -> dict[str, int]:
    """페이지 유형별 개수를 집계."""
    counts: dict[str, int] = {}
    for p in pages_data:
        t = p.get("page_type", "content")
        counts[t] = counts.get(t, 0) + 1
    return counts


def _save_cache(pages_data: list[dict[str, Any]]) -> None:
    """캐시를 원자적으로 저장 (temp 파일 → rename)."""
    temp_path = _CACHE_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(pages_data, f, ensure_ascii=False, indent=2)
    temp_path.replace(_CACHE_PATH)
    print(f"  캐시 저장: {_CACHE_PATH}")

# GPT-4o Vision 프롬프트
_VISION_SYSTEM_PROMPT = """\
당신은 한국어 PDF 교육 자료의 텍스트 추출 전문가입니다.
이 문서는 "4대보험 사업자 교육" 교재로, 국민연금·건강보험·고용보험·산재보험의
제도 안내와 신고 절차를 설명하는 교육 자료입니다.

## 응답 형식
반드시 첫 줄에 페이지 유형 태그를 작성하고, 그 다음 줄부터 내용을 작성하세요:

[TYPE: content] - 교육/설명 본문 페이지
[TYPE: form] - 신고서, 신청서, 별지 서식, 웹페이지 캡처본 등 양식/스크린샷 페이지
[TYPE: divider] - 챕터 구분 페이지 (큰 제목만 있는 장식 페이지)
[TYPE: cover] - 표지, 목차, 빈 페이지

## 추출 규칙
1. [TYPE: content] 페이지만 텍스트를 상세히 추출하세요.
2. [TYPE: form] 페이지는 태그만 작성하고 텍스트를 추출하지 마세요.
   - 신고서/신청서 양식, "별지 제N호 서식", 접수번호/처리기간 칸이 있는 서류
   - 포털 사이트/웹사이트 캡처 화면, 시스템 화면 스크린샷
   - 작성 예시가 채워진 양식 샘플
3. [TYPE: divider] 페이지는 태그 + 보이는 제목 텍스트만 짧게 추출하세요.
4. [TYPE: cover] 페이지는 태그만 작성하세요.
5. 교육 본문의 문맥을 이해하여, 제도 설명·절차 안내·대상자 요건 등
   교육에 필요한 핵심 내용을 정확히 추출하세요.
6. 표(table)는 markdown 테이블로 변환하세요.
7. 페이지 헤더/푸터/페이지 번호는 제외하세요.
8. 글머리 기호(○, ●, -, ※ 등)는 그대로 유지하세요.
9. 원본 텍스트를 그대로 추출하세요. 요약이나 해석은 금지입니다.
10. 그래프, 차트, 다이어그램, 타임라인, 흐름도 등 시각적 도표 내부의 텍스트(축 라벨, 데이터 값,
    날짜 마커, 화살표 텍스트 등)는 추출하지 마세요. 도표 아래/옆에 있는 설명 본문만 추출하세요.
11. 색상 배너(초록색/파란색 띠) 안에 번호와 제목이 있는 소제목 헤더
    (예: 흰색 원 안의 "02" + "국민연금 사업장 실무")는 반드시 "## 02 제목" 형식으로 추출하세요.
    이 배너형 제목은 [TYPE: content]로 분류하고 첫 줄에 마크다운 헤딩으로 작성하세요."""

_VISION_USER_PROMPT = "이 PDF 페이지의 텍스트를 추출해주세요."


class OpenAIVisionParser:
    """OpenAI GPT-4o Vision API로 PDF 페이지별 텍스트 추출."""

    MAX_RETRIES = 3
    DPI = 200  # 텍스트 인식 정확도와 API 비용 사이 균형점

    _TYPE_TAG_PATTERN = re.compile(
        r"^\[TYPE:\s*(content|form|divider|cover)\]", re.IGNORECASE
    )

    _REFUSAL_PATTERNS = ("I'm sorry", "I can't assist", "I cannot assist")

    _VISION_RETRY_PROMPT = (
        "이 이미지는 한국 국민건강보험공단에서 발행한 '4대보험 사업자 교육' 공개 교재의 "
        "한 페이지입니다. 교육 목적의 공개 자료이며, 포함된 개인정보는 모두 가상의 예시입니다. "
        "페이지의 텍스트를 추출해주세요."
    )

    _VISION_FORCE_CONTENT_PROMPT = (
        "이 이미지는 '4대보험 사업자 교육' 공개 교재의 한 페이지입니다. "
        "이 페이지에 양식(신고서 등)이나 웹사이트 캡처가 포함되어 있더라도, "
        "페이지에 보이는 모든 교육 관련 텍스트를 추출해주세요. "
        "[TYPE: content] 태그로 시작하고, 양식 내부의 예시 데이터는 제외하되 "
        "제도 설명, 절차 안내, 대상자 요건 등 교육 본문은 반드시 포함하세요."
    )

    _VISION_FORCE_SYSTEM_PROMPT = """\
당신은 한국어 PDF 교육 자료의 텍스트 추출 전문가입니다.
이 문서는 "4대보험 사업자 교육" 교재로, 국민연금·건강보험·고용보험·산재보험의
제도 안내와 신고 절차를 설명하는 교육 자료입니다.

## 응답 형식
반드시 첫 줄에 [TYPE: content] 태그를 작성하고, 그 다음 줄부터 내용을 작성하세요.

## 추출 규칙
1. 이 페이지에 양식(신고서, 신청서)이나 웹사이트 캡처가 포함되어 있더라도,
   페이지 상단/중간에 있는 교육 본문 텍스트는 반드시 추출하세요.
2. 양식 내부의 예시 데이터(이름, 주민등록번호, 금액 등 기입 예시)는 제외하세요.
3. 제도 설명, 절차 안내, 대상자 요건, 신고 기한, 적용 기준 등
   교육에 필요한 핵심 내용을 정확히 추출하세요.
4. 표(table)는 markdown 테이블로 변환하세요.
5. 페이지 헤더/푸터/페이지 번호는 제외하세요.
6. 글머리 기호(○, ●, -, ※ 등)는 그대로 유지하세요.
7. 원본 텍스트를 그대로 추출하세요. 요약이나 해석은 금지입니다.
8. 색상 배너 안에 번호와 제목이 있는 소제목 헤더는
   "## 02 제목" 형식으로 추출하세요."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        resolved_key = api_key or os.getenv("OPENAI_API_KEY", "")
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        self.client = OpenAI(api_key=resolved_key)
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")

    def _parse_vision_response(self, raw: str) -> tuple[str, str]:
        """API 응답에서 페이지 유형 태그와 본문 분리.

        Returns:
            (page_type, text) - page_type은 "content"|"form"|"divider"|"cover"
        """
        if not raw or not raw.strip():
            return ("cover", "")

        lines = raw.strip().split("\n", 1)
        first_line = lines[0].strip()

        m = self._TYPE_TAG_PATTERN.match(first_line)
        if m:
            page_type = m.group(1).lower()
            text = lines[1].strip() if len(lines) > 1 else ""
            return (page_type, text)

        # 태그 없으면 기본값 content
        return ("content", raw.strip())

    def _render_page_to_base64(self, doc: fitz.Document, page_idx: int) -> str:
        """pymupdf로 PDF 페이지를 PNG 이미지로 렌더링 후 base64 인코딩."""
        page = doc.load_page(page_idx)
        zoom = self.DPI / 72  # 72 DPI 기준 확대 비율
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        png_bytes = pix.tobytes("png")
        return base64.b64encode(png_bytes).decode("utf-8")

    def _call_vision_api(self, image_base64: str, page_num: int) -> str:
        """GPT-4o Vision API 호출 (exponential backoff 재시도 + 거부 응답 3단계 재시도).

        재시도 전략:
            1차: 기본 프롬프트 + detail: "high"
            2차: 교육자료 프롬프트 + detail: "high"
            3차: 교육자료 프롬프트 + detail: "low" (저해상도로 PII 감지 우회)
        """
        result = self._call_vision_api_inner(
            image_base64, page_num, _VISION_USER_PROMPT
        )

        # 거부 응답 감지 → 프롬프트 변경 후 재시도 (detail: high)
        if any(pat in result for pat in self._REFUSAL_PATTERNS):
            print(f"    거부 응답 감지 (p.{page_num}) - 프롬프트 변경 후 재시도")
            result = self._call_vision_api_inner(
                image_base64, page_num, self._VISION_RETRY_PROMPT
            )

        # 여전히 거부 → 저해상도로 재시도 (detail: low)
        if any(pat in result for pat in self._REFUSAL_PATTERNS):
            print(f"    2차 거부 (p.{page_num}) - 저해상도(detail=low)로 재시도")
            result = self._call_vision_api_inner(
                image_base64, page_num, self._VISION_RETRY_PROMPT,
                detail="low",
            )
            if any(pat in result for pat in self._REFUSAL_PATTERNS):
                print(f"    3차 재시도에도 거부 (p.{page_num}) - 빈 응답 반환")
                return ""

        return result

    def _call_vision_api_inner(
        self, image_base64: str, page_num: int, user_prompt: str,
        detail: str = "high", system_prompt: str | None = None,
    ) -> str:
        """GPT-4o Vision API 단일 호출 (exponential backoff 재시도)."""
        sys_prompt = system_prompt or _VISION_SYSTEM_PROMPT
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}",
                                        "detail": detail,
                                    },
                                },
                            ],
                        },
                    ],
                    max_tokens=4096,
                    temperature=0.0,
                )
                return response.choices[0].message.content or ""

            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                if attempt < self.MAX_RETRIES:
                    wait_time = 2 ** attempt
                    print(f"    API 오류 (p.{page_num}, 시도 {attempt}) - "
                          f"{wait_time}초 후 재시도: {type(e).__name__}")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"OpenAI Vision API 호출 실패 (p.{page_num}, "
                        f"{self.MAX_RETRIES}회 시도): {e}"
                    )
        return ""

    def reprocess_refused_pages(
        self, pages_data: list[dict[str, Any]], pdf_path: str,
    ) -> list[dict[str, Any]]:
        """캐시에서 거부 응답인 페이지만 선택적으로 재처리.

        Args:
            pages_data: 캐시에서 로드한 페이지별 데이터
            pdf_path: 원본 PDF 파일 경로

        Returns:
            거부 페이지가 재처리된 pages_data (in-place 수정 후 반환)
        """
        refused = [
            (i, p) for i, p in enumerate(pages_data)
            if any(pat in p.get("text", "") for pat in self._REFUSAL_PATTERNS)
        ]
        if not refused:
            return pages_data

        print(f"  거부 응답 {len(refused)}페이지 재처리 시도...")
        doc = fitz.open(pdf_path)
        try:
            for idx, page_data in refused:
                page_num = page_data["page"]
                print(f"    [{page_num}] 재처리 중...", end="", flush=True)
                try:
                    image_b64 = self._render_page_to_base64(doc, page_num - 1)
                    raw = self._call_vision_api(image_b64, page_num)
                    page_type, text = self._parse_vision_response(raw)
                    pages_data[idx] = {
                        "page": page_num,
                        "text": text,
                        "page_type": page_type,
                    }
                    print(f" [{page_type}] ({len(text)}자)")
                except RuntimeError as e:
                    print(f" 실패: {e}")
                time.sleep(0.5)
        finally:
            doc.close()

        # 재처리 후 남은 거부 페이지 수 보고
        still_refused = sum(
            1 for p in pages_data
            if any(pat in p.get("text", "") for pat in self._REFUSAL_PATTERNS)
        )
        print(f"  재처리 완료: 거부 {len(refused)} → {still_refused}페이지")
        return pages_data

    def reprocess_misclassified_pages(
        self, pages_data: list[dict[str, Any]], pdf_path: str,
    ) -> list[dict[str, Any]]:
        """form/cover로 분류되었지만 본문이 있을 수 있는 페이지를 재처리.

        선별 기준: form/cover 페이지(text 빈 문자열) 중, ±2 페이지 이내에
        content 페이지가 존재하는 경우 재처리 대상으로 선정.

        Args:
            pages_data: 캐시에서 로드한 페이지별 데이터
            pdf_path: 원본 PDF 파일 경로

        Returns:
            오분류 페이지가 재처리된 pages_data (in-place 수정 후 반환)
        """
        candidates: list[tuple[int, dict[str, Any]]] = []
        for i, p in enumerate(pages_data):
            if p.get("page_type") not in ("form", "cover"):
                continue
            if p.get("text", "").strip():
                continue  # 이미 텍스트 있으면 스킵
            # ±2 페이지 내에 content 페이지가 있는지 확인
            has_content_neighbor = False
            for j in range(max(0, i - 2), min(len(pages_data), i + 3)):
                if j == i:
                    continue
                neighbor = pages_data[j]
                if (neighbor.get("page_type") == "content"
                        and len(neighbor.get("text", "")) > 100):
                    has_content_neighbor = True
                    break
            if has_content_neighbor:
                candidates.append((i, p))

        if not candidates:
            return pages_data

        print(f"  오분류 의심 {len(candidates)}페이지 재처리 시도...")
        doc = fitz.open(pdf_path)
        updated = 0
        try:
            for idx, page_data in candidates:
                page_num = page_data["page"]
                print(f"    [{page_num}] 재확인 중...", end="", flush=True)
                try:
                    image_b64 = self._render_page_to_base64(doc, page_num - 1)
                    raw = self._call_vision_api_inner(
                        image_b64, page_num, self._VISION_FORCE_CONTENT_PROMPT,
                        system_prompt=self._VISION_FORCE_SYSTEM_PROMPT,
                    )
                    page_type, text = self._parse_vision_response(raw)
                    if len(text.strip()) > 50:
                        pages_data[idx] = {
                            "page": page_num, "text": text,
                            "page_type": "content",
                        }
                        updated += 1
                        print(f" → content ({len(text)}자)")
                    else:
                        print(f" → 유지 ({page_data['page_type']})")
                except RuntimeError as e:
                    print(f" 실패: {e}")
                time.sleep(0.5)
        finally:
            doc.close()

        print(f"  오분류 재처리 완료: {updated}/{len(candidates)}페이지 content로 변경")
        return pages_data

    def reprocess_force_pages(
        self, pages_data: list[dict[str, Any]], pdf_path: str,
        page_numbers: list[int],
    ) -> list[dict[str, Any]]:
        """지정된 페이지를 강제로 재추출.

        기존 분류(form/cover/content)에 관계없이, 지정된 페이지를 force 프롬프트로
        재호출하여 교육 본문 텍스트를 추출합니다.

        Args:
            pages_data: 캐시에서 로드한 페이지별 데이터
            pdf_path: 원본 PDF 파일 경로
            page_numbers: 재추출할 페이지 번호 리스트 (1-indexed)

        Returns:
            지정 페이지가 재추출된 pages_data (in-place 수정 후 반환)
        """
        page_idx_map = {p["page"]: i for i, p in enumerate(pages_data)}
        targets = []
        for pn in page_numbers:
            if pn not in page_idx_map:
                print(f"  경고: 페이지 {pn}은 데이터에 없습니다 (전체 {len(pages_data)}p)")
                continue
            idx = page_idx_map[pn]
            if pages_data[idx].get("page_type") == "divider":
                continue  # divider(챕터 구분 페이지)는 건드리지 않음
            targets.append((idx, pn))

        if not targets:
            return pages_data

        print(f"  지정 {len(targets)}페이지 강제 재추출...")
        doc = fitz.open(pdf_path)
        updated = 0
        try:
            for idx, page_num in targets:
                old = pages_data[idx]
                old_type = old.get("page_type", "?")
                old_len = len(old.get("text", ""))
                print(f"    [{page_num}] ({old_type}, {old_len}자) → ",
                      end="", flush=True)
                try:
                    image_b64 = self._render_page_to_base64(doc, page_num - 1)
                    raw = self._call_vision_api_inner(
                        image_b64, page_num, self._VISION_FORCE_CONTENT_PROMPT,
                        system_prompt=self._VISION_FORCE_SYSTEM_PROMPT,
                    )
                    page_type, text = self._parse_vision_response(raw)
                    new_len = len(text.strip())
                    if new_len > old_len:
                        pages_data[idx] = {
                            "page": page_num, "text": text,
                            "page_type": "content",
                        }
                        updated += 1
                        print(f"content ({new_len}자)")
                    else:
                        print(f"유지 ({old_type}, 기존 {old_len}자 ≥ 신규 {new_len}자)")
                except RuntimeError as e:
                    print(f"실패: {e}")
                time.sleep(0.5)
        finally:
            doc.close()

        print(f"  강제 재추출 완료: {updated}/{len(targets)}페이지 갱신")
        return pages_data

    def parse_document(
        self, pdf_path: str, use_cache: bool = True
    ) -> list[dict[str, Any]]:
        """PDF → 페이지별 Vision API 호출 → 텍스트 추출 결과 반환.

        모든 페이지를 GPT-4o Vision으로 처리하여 페이지 유형을 판별합니다.
        서식/캡처 페이지는 GPT-4o가 [TYPE: form]으로 분류하여 텍스트 추출을 거부합니다.

        Returns:
            [{"page": int (1-indexed), "text": str, "page_type": str}, ...]
        """
        if use_cache and _CACHE_PATH.exists():
            print(f"  캐시 파일 로드: {_CACHE_PATH}")
            try:
                with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
            except json.JSONDecodeError:
                print("  경고: 캐시 파일 손상 - 삭제 후 재생성합니다.")
                _CACHE_PATH.unlink(missing_ok=True)
                cached = None
            if cached is not None:
                # 이전 캐시 형식(skipped 필드, page_type 없음) 감지 → 자동 삭제
                if cached and "page_type" not in cached[0]:
                    print("  경고: 이전 형식 캐시 감지 (page_type 없음) - "
                          "삭제 후 재생성합니다.")
                    _CACHE_PATH.unlink(missing_ok=True)
                else:
                    return cached

        doc = fitz.open(pdf_path)
        try:
            total_pages = len(doc)
            print(f"  PDF 페이지 수: {total_pages}")

            pages_data: list[dict[str, Any]] = []

            for page_idx in range(total_pages):
                page_num = page_idx + 1  # 1-indexed

                print(f"  [{page_num}/{total_pages}] 페이지 처리 중...",
                      end="", flush=True)

                # 이미지 렌더링 + API 호출
                image_b64 = self._render_page_to_base64(doc, page_idx)
                raw_response = self._call_vision_api(image_b64, page_num)

                # 응답 파싱: 페이지 유형 태그 분리
                page_type, text = self._parse_vision_response(raw_response)

                pages_data.append({
                    "page": page_num,
                    "text": text,
                    "page_type": page_type,
                })
                print(f" [{page_type}] ({len(text)}자)")

                # Rate limit 방지 (페이지 사이 짧은 대기)
                if page_idx < total_pages - 1:
                    time.sleep(0.5)
        finally:
            doc.close()

        # 페이지 유형 분포 출력
        type_counts = _count_page_types(pages_data)
        print(f"  처리 완료: {total_pages}페이지")
        for t, cnt in sorted(type_counts.items()):
            print(f"    {t}: {cnt}페이지")

        # 캐시 저장
        if use_cache:
            _save_cache(pages_data)

        return pages_data

    # --- LLM 기반 대형 섹션 분할 ---

    _SPLIT_SYSTEM_PROMPT = """\
당신은 한국어 교육 자료의 구조 분석 전문가입니다.
주어진 텍스트를 의미 있는 하위 섹션으로 분할해주세요.

## 규칙
1. 각 섹션은 하나의 주제/절차/개념을 다뤄야 합니다
2. 섹션 제목은 내용을 명확히 설명해야 합니다
3. 원본 텍스트를 그대로 유지하세요 (수정/요약 금지)
4. 목표 섹션 크기: 500~1200자
5. 너무 짧은 섹션(<200자)은 인접 섹션과 병합하세요

## 응답 형식 (반드시 JSON)
{"sections": [{"title": "섹션 제목", "content": "원본 텍스트 그대로..."}, ...]}"""

    _SPLIT_USER_TEMPLATE = (
        '다음 "{title}" 섹션을 의미 단위로 분할해주세요.\n\n'
        "---\n{content}\n---"
    )

    def _load_split_cache(self) -> dict[str, list[dict[str, str]]]:
        """분할 캐시 로드."""
        if _SPLIT_CACHE_PATH.exists():
            try:
                with open(_SPLIT_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_split_cache(
        self, cache: dict[str, list[dict[str, str]]],
    ) -> None:
        """분할 캐시 저장."""
        temp = _SPLIT_CACHE_PATH.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        temp.replace(_SPLIT_CACHE_PATH)

    def split_large_section(
        self, content: str, title: str,
    ) -> list[dict[str, str]]:
        """LLM으로 대형 섹션을 하위 섹션으로 분할.

        Args:
            content: 분할할 텍스트 (title 미포함 본문)
            title: 원본 섹션 제목

        Returns:
            [{"title": str, "content": str}, ...] 분할 결과.
            분할 실패 시 원본 그대로 1개짜리 리스트 반환.
        """
        cache_key = hashlib.md5(content.encode("utf-8")).hexdigest()
        cache = self._load_split_cache()

        if cache_key in cache:
            return cache[cache_key]

        fallback = [{"title": title, "content": content}]

        try:
            user_msg = self._SPLIT_USER_TEMPLATE.format(
                title=title, content=content,
            )
            # max_tokens를 입력 길이에 비례하여 설정 (최소 4096, 최대 16384)
            est_tokens = min(max(len(content) * 2, 4096), 16384)
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._SPLIT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                max_tokens=est_tokens,
                temperature=0.0,
            )
            raw = response.choices[0].message.content or ""
            parsed = json.loads(raw)
            sections = parsed.get("sections", [])

            if not sections or not isinstance(sections, list):
                print(f"    분할 실패 (빈 결과): {title[:30]}")
                return fallback

            # 유효성 검증: 각 섹션에 title, content 필드 필수
            validated: list[dict[str, str]] = []
            for s in sections:
                if isinstance(s, dict) and "title" in s and "content" in s:
                    if len(s["content"].strip()) >= 50:
                        validated.append({
                            "title": s["title"],
                            "content": s["content"],
                        })

            if not validated:
                print(f"    분할 실패 (유효 섹션 없음): {title[:30]}")
                return fallback

            # 캐시 저장
            cache[cache_key] = validated
            self._save_split_cache(cache)
            print(f"    분할 성공: {title[:30]} → {len(validated)}개 하위 섹션")
            return validated

        except (json.JSONDecodeError, KeyError) as e:
            print(f"    분할 실패 (파싱 오류): {title[:30]} - {e}")
            return fallback
        except Exception as e:
            print(f"    분할 실패 (API 오류): {title[:30]} - {e}")
            return fallback


class HRInsuranceEduPreprocessor:
    """4대보험 사업자 교육 PDF 전처리 - 대제목 구분 페이지 + 중제목 기반."""

    def __init__(self, output_dir: str | None = None):
        self.output_dir = output_dir or str(
            _PROJECT_ROOT / "data" / "preprocessed" / "labor"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def clean_text(self, text: str) -> str:
        """텍스트 정제."""
        if not text:
            return ""
        text = text.replace("\x00", " ")
        # 마크다운 이미지 참조 제거
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

        # [TYPE: xxx] 태그 제거 (이스케이프된 버전 포함)
        text = re.sub(
            r"\\?\[TYPE:\s*(?:content|form|divider|cover)\\?\]",
            "", text,
        )

        # 마크다운 코드블록 마커 제거 (```markdown, ``` 등)
        text = re.sub(r"^```(?:markdown)?\s*$", "", text, flags=re.MULTILINE)

        # --- 수평선 단독 줄 제거
        text = re.sub(r"^-{3,}\s*$", "", text, flags=re.MULTILINE)

        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _detect_chapter_divider(self, text: str) -> tuple[str, str] | None:
        """대제목 구분 페이지 텍스트 감지.

        구분 페이지의 텍스트는 짧고 "제도 안내" 또는 "이용방법"을 포함.
        content 페이지에서도 호출되므로 길이/키워드 가드가 필수.

        Returns: (chapter_name, id_prefix) 또는 None
        """
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) > 50:
            return None
        if "제도 안내" not in normalized and "이용방법" not in normalized:
            return None

        for keyword, chapter_name, id_prefix in CHAPTER_DIVIDER_KEYWORDS:
            if keyword in normalized:
                return (chapter_name, id_prefix)
        return None

    def _detect_chapter_from_context(
        self,
        pages_data: list[dict[str, Any]],
        divider_idx: int,
        max_lookahead: int = 3,
    ) -> tuple[str, str] | None:
        """빈 텍스트의 divider 페이지: 후속 content 페이지에서 챕터 키워드 탐지.

        Args:
            pages_data: 전체 페이지 데이터
            divider_idx: divider 페이지의 인덱스
            max_lookahead: 탐색할 후속 페이지 수

        Returns:
            (chapter_name, id_prefix) 또는 None
        """
        for j in range(
            divider_idx + 1,
            min(divider_idx + max_lookahead + 1, len(pages_data)),
        ):
            page = pages_data[j]
            if page.get("page_type") in ("form", "cover"):
                continue
            text = page.get("text", "")
            if not text:
                continue
            for keyword, chapter_name, id_prefix in CHAPTER_DIVIDER_KEYWORDS:
                if keyword in text:
                    return (chapter_name, id_prefix)
        return None

    def _match_subtitle(self, text: str) -> tuple[str, str] | None:
        """중제목 텍스트 매칭. Returns (number, title_text) or None."""
        m = SUBTITLE_PATTERN.match(text.strip())
        if m and len(text.strip()) < 100:
            return (m.group(1), m.group(2).strip())
        return None

    def parse_pages(
        self, pages_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """페이지별 텍스트 → 대제목/중제목 기반 섹션 리스트.

        page_type 기반 필터링:
        - "form", "cover" → 스킵 (불필요 콘텐츠)
        - "divider" → 대제목 구분 페이지 감지
        - "content" → 중제목/콘텐츠 파싱

        Returns:
            [{"chapter": str, "chapter_prefix": str, "subtitle_num": str,
              "subtitle": str, "content_parts": list, "pages": set}]
        """
        sections: list[dict[str, Any]] = []
        current_chapter = ""
        current_prefix = ""
        current_subtitle_num = ""
        current_subtitle = ""
        current_parts: list[str] = []
        current_pages: set[int] = set()

        def _flush_section() -> None:
            if current_parts and current_subtitle and current_chapter:
                sections.append({
                    "chapter": current_chapter,
                    "chapter_prefix": current_prefix,
                    "subtitle_num": current_subtitle_num,
                    "subtitle": current_subtitle,
                    "content_parts": list(current_parts),
                    "pages": set(current_pages),
                })

        for page_idx, page_data in enumerate(pages_data):
            page_num = page_data["page"]
            text = page_data.get("text", "").strip()
            page_type = page_data.get("page_type", "content")

            # 이전 캐시 호환: skipped 필드가 있으면 그대로 처리
            if page_data.get("skipped", False):
                continue

            # form/cover 페이지는 스킵 (신고서, 신청서, 캡처본, 표지 등)
            if page_type in ("form", "cover"):
                continue

            # divider 페이지: 대제목 구분 페이지 감지 (텍스트 없어도 처리)
            if page_type == "divider":
                chapter_info = self._detect_chapter_divider(text)
                if not chapter_info:
                    # 키워드 미매칭 divider: 후속 페이지에서 챕터 키워드 탐지
                    chapter_info = self._detect_chapter_from_context(
                        pages_data, page_idx
                    )
                if chapter_info:
                    _flush_section()
                    current_chapter, current_prefix = chapter_info
                    current_subtitle_num = "00"
                    current_subtitle = f"{current_chapter} 개요"
                    current_parts = []
                    current_pages = set()
                continue

            # 텍스트 없는 content 페이지 스킵
            if not text:
                continue

            # 거부 응답 텍스트가 남아있으면 스킵
            if any(pat in text for pat in OpenAIVisionParser._REFUSAL_PATTERNS):
                continue

            # content 페이지: 대제목 구분 페이지일 수도 있음 (태그 오분류 대비)
            chapter_info = self._detect_chapter_divider(text)
            if chapter_info:
                _flush_section()
                current_chapter, current_prefix = chapter_info
                current_subtitle_num = "00"
                current_subtitle = f"{current_chapter} 개요"
                current_parts = []
                current_pages = set()
                continue

            # 아직 장이 시작되지 않았으면 스킵 (표지, 목차 등)
            if not current_chapter:
                continue

            # 페이지 텍스트를 줄 단위로 처리
            lines = text.split("\n")
            page_content_parts: list[str] = []

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # 중제목 감지
                subtitle_match = self._match_subtitle(stripped)
                if subtitle_match:
                    # 현재 페이지에서 축적된 내용을 현재 섹션에 추가
                    if page_content_parts:
                        combined = "\n".join(page_content_parts)
                        if combined.strip():
                            current_parts.append(combined.strip())
                            current_pages.add(page_num)
                        page_content_parts = []

                    _flush_section()
                    current_subtitle_num, current_subtitle = subtitle_match
                    current_parts = []
                    current_pages = set()
                    continue

                # 일반 콘텐츠 축적
                if current_subtitle:
                    page_content_parts.append(stripped)

            # 페이지 끝: 축적된 내용을 현재 섹션에 추가
            if page_content_parts and current_subtitle:
                combined = "\n".join(page_content_parts)
                if combined.strip():
                    current_parts.append(combined.strip())
                    current_pages.add(page_num)

        # 마지막 섹션 플러시
        _flush_section()

        return sections

    def build_documents(
        self,
        sections: list[dict[str, Any]],
        filename: str,
        parser: "OpenAIVisionParser | None" = None,
    ) -> list[dict[str, Any]]:
        """섹션 → 통합 스키마 JSONL 레코드 변환.

        Args:
            sections: parse_pages() 결과
            filename: 원본 PDF 파일명
            parser: OpenAIVisionParser 인스턴스 (대형 섹션 LLM 분할용)
        """
        documents: list[dict[str, Any]] = []
        collected_at = datetime.now().isoformat(timespec="seconds")

        chapter_seq: dict[str, int] = {}

        for section in sections:
            # 거부 텍스트 포함 파트 필터링
            content_parts = [
                p for p in section["content_parts"]
                if p and not any(kw in p for kw in REFUSAL_KEYWORDS)
            ]

            content_text = "\n\n".join(content_parts)
            content_text = self.clean_text(content_text)

            if len(content_text) < MIN_SECTION_LENGTH:
                continue

            prefix = section["chapter_prefix"]
            title = section["subtitle"]
            pages = section.get("pages", set())
            page_range = _format_page_range(sorted(pages)) if pages else ""
            chapter_title = section["chapter"]

            content_with_title = f"{title}\n\n{content_text}"

            # 대형 섹션 LLM 분할
            if len(content_with_title) > SPLIT_THRESHOLD and parser:
                sub_sections = parser.split_large_section(
                    content_text, title,
                )
                if len(sub_sections) > 1:
                    base_seq = chapter_seq.get(prefix, 0) + 1
                    chapter_seq[prefix] = base_seq
                    for i, sub in enumerate(sub_sections):
                        sub_id = f"{prefix}_{base_seq:03d}_{i + 1:02d}"
                        sub_title = sub["title"]
                        sub_content = self.clean_text(sub["content"])
                        if len(sub_content) < MIN_SECTION_LENGTH:
                            continue
                        sub_content_with_title = (
                            f"{sub_title}\n\n{sub_content}"
                        )
                        doc = {
                            "id": sub_id,
                            "type": "guide",
                            "domain": "hr_labor",
                            "title": sub_title,
                            "content": sub_content_with_title,
                            "source": {
                                "name": filename,
                                "url": "",
                                "collected_at": collected_at,
                            },
                            "effective_date": "",
                            "metadata": {
                                "category": "4대보험_교육",
                                "chapter_title": chapter_title,
                                "section_title": title,
                                "parent_section": f"{prefix}_{base_seq:03d}",
                                "page_range": page_range,
                            },
                        }
                        documents.append(doc)
                    continue  # 분할 성공 시 원본 생략

            # 분할 불필요 또는 분할 실패 → 원본 그대로
            chapter_seq[prefix] = chapter_seq.get(prefix, 0) + 1
            seq = chapter_seq[prefix]
            doc_id = f"{prefix}_{seq:03d}"

            doc = {
                "id": doc_id,
                "type": "guide",
                "domain": "hr_labor",
                "title": title,
                "content": content_with_title,
                "source": {
                    "name": filename,
                    "url": "",
                    "collected_at": collected_at,
                },
                "effective_date": "",
                "metadata": {
                    "category": "4대보험_교육",
                    "chapter_title": chapter_title,
                    "section_title": title,
                    "page_range": page_range,
                },
            }
            documents.append(doc)

        return documents

    def save_to_jsonl(
        self,
        documents: list[dict[str, Any]],
        output_filename: str = "hr_insurance_edu_openai.jsonl",
    ) -> str:
        """JSONL 저장."""
        output_path = os.path.join(self.output_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
        return output_path


def _parse_page_numbers(raw: str) -> list[int]:
    """'1,3,5-8,10' 형식 문자열 → 정렬된 페이지 번호 리스트."""
    pages: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start_s, end_s = start_s.strip(), end_s.strip()
                if not start_s or not end_s:
                    print(f"  경고: 잘못된 범위 '{part}' - 건너뜀")
                    continue
                start, end = int(start_s), int(end_s)
                if start < 1 or end < 1 or start > end:
                    print(f"  경고: 유효하지 않은 범위 '{part}' - 건너뜀")
                    continue
                pages.update(range(start, end + 1))
            else:
                val = int(part)
                if val < 1:
                    print(f"  경고: 음수/0 페이지 '{part}' - 건너뜀")
                    continue
                pages.add(val)
        except ValueError:
            print(f"  경고: 숫자가 아닌 입력 '{part}' - 건너뜀")
    return sorted(pages)


def main() -> None:
    """CLI 진입점."""
    arg_parser = argparse.ArgumentParser(
        description="4대보험 사업자 교육 PDF 전처리 (OpenAI GPT-4o Vision)"
    )
    arg_parser.add_argument(
        "--pages", type=str, default=None,
        help="강제 재추출할 페이지 번호 (예: 105,107 또는 100-110)",
    )
    args = arg_parser.parse_args()

    force_pages: list[int] | None = None
    if args.pages:
        force_pages = _parse_page_numbers(args.pages)

    # PDF 경로: scripts/ 폴더 또는 data/ 폴더
    scripts_pdf = _PROJECT_ROOT / "scripts" / "4대보험_사업자_교육.pdf"

    input_pdf = str(scripts_pdf)  # 캐시 사용 시 파일 없어도 진행 가능

    output_dir = str(_PROJECT_ROOT / "data" / "preprocessed" / "labor")
    preprocessor = HRInsuranceEduPreprocessor(output_dir=output_dir)

    print("=" * 60)
    print("4대보험 사업자 교육 PDF 전처리 (OpenAI GPT-4o Vision)")
    print("=" * 60)

    has_cache = _CACHE_PATH.exists()

    if not os.path.exists(input_pdf) and not has_cache:
        print(f"  입력 파일 없음: {input_pdf}")
        print(f"  캐시 파일도 없음: {_CACHE_PATH}")
        return

    # API 호출 (캐시 사용)
    parser: OpenAIVisionParser | None = None
    pages_data: list[dict[str, Any]] = []

    if has_cache:
        print(f"  캐시 파일 로드: {_CACHE_PATH}")
        try:
            with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                pages_data = json.load(f)
        except json.JSONDecodeError:
            print("  경고: 캐시 파일 손상 - 삭제 후 재생성합니다.")
            _CACHE_PATH.unlink(missing_ok=True)
            has_cache = False

    if not has_cache and not os.path.exists(input_pdf):
        print(f"  입력 파일 없음: {input_pdf}")
        return

    if has_cache:
        # 거부 응답 페이지 재처리
        refused_count = sum(
            1 for p in pages_data
            if any(
                pat in p.get("text", "")
                for pat in OpenAIVisionParser._REFUSAL_PATTERNS
            )
        )
        if refused_count > 0 and os.path.exists(input_pdf):
            print(f"  거부 응답 {refused_count}페이지 감지 - 재처리 시도")
            try:
                parser = OpenAIVisionParser()
                pages_data = parser.reprocess_refused_pages(
                    pages_data, input_pdf
                )
                _save_cache(pages_data)
            except (RuntimeError, ValueError) as e:
                print(f"  재처리 실패: {e}")
                print("  기존 캐시 유지")

        # 재처리 단계 간 rate limit 방지
        if refused_count > 0:
            time.sleep(2)

        # 오분류 페이지 재처리 (form/cover인데 실제 content인 페이지)
        if os.path.exists(input_pdf):
            try:
                if not parser:
                    parser = OpenAIVisionParser()
                pages_data = parser.reprocess_misclassified_pages(
                    pages_data, input_pdf
                )
                _save_cache(pages_data)
            except (RuntimeError, ValueError) as e:
                print(f"  오분류 재처리 실패: {e}")
    else:
        parser = OpenAIVisionParser()
        pages_data = parser.parse_document(input_pdf)

    # --pages 지정 시 강제 재추출
    if force_pages and os.path.exists(input_pdf):
        time.sleep(2)  # 재처리 단계 간 rate limit 방지
        print(f"  --pages 지정: {force_pages}")
        try:
            if not parser:
                parser = OpenAIVisionParser()
            pages_data = parser.reprocess_force_pages(
                pages_data, input_pdf, force_pages
            )
            _save_cache(pages_data)
        except (RuntimeError, ValueError) as e:
            print(f"  강제 재추출 실패: {e}")

    # 페이지 유형 분포 출력
    type_counts = _count_page_types(pages_data)
    content_pages = [
        p for p in pages_data
        if p.get("page_type", "content") == "content" and p.get("text")
    ]
    print(f"  유효 content 페이지 수: {len(content_pages)}/{len(pages_data)}")
    for t, cnt in sorted(type_counts.items()):
        print(f"    {t}: {cnt}페이지")

    # 파싱
    sections = preprocessor.parse_pages(pages_data)
    print(f"  중제목 섹션 수: {len(sections)}")

    # 챕터별 분포
    chapter_counts: dict[str, int] = {}
    for s in sections:
        ch = s["chapter_prefix"]
        chapter_counts[ch] = chapter_counts.get(ch, 0) + 1
    for ch, cnt in chapter_counts.items():
        print(f"    {ch}: {cnt}개 섹션")

    # 문서 빌드 (parser가 있으면 대형 섹션 LLM 분할)
    if not parser:
        try:
            parser = OpenAIVisionParser()
        except ValueError:
            pass  # API 키 없으면 분할 없이 진행
    filename = os.path.basename(input_pdf)
    documents = preprocessor.build_documents(sections, filename, parser=parser)

    if not documents:
        print("  생성된 문서 없음")
        return

    print(f"  총 문서 수: {len(documents)}")

    # JSONL 저장
    output_path = preprocessor.save_to_jsonl(documents, "hr_insurance_edu.jsonl")
    print(f"  JSONL 저장: {output_path}")

    # 검증 요약
    print("\n  === 검증 요약 ===")
    for doc in documents:
        ch = doc["metadata"].get("chapter_title", doc["metadata"].get("chapter", ""))
        pg = doc["metadata"]["page_range"]
        clen = len(doc["content"])
        print(f"    [{doc['id']:>8}] {doc['title']:<40s} ch={ch:<30s} "
              f"page={pg:<10s} len={clen}")


if __name__ == "__main__":
    main()
