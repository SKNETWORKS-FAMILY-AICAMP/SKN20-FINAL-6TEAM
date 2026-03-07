"""Contextual Retrieval prefix 생성 모듈.

각 청크의 page_content 앞에 문서 맥락을 설명하는 prefix를 추가합니다.
LLM 호출 없이 JSONL 메타데이터만으로 생성합니다.

Anthropic 연구: 검색 실패율 49% 감소, reranking 병행 시 67% 감소.
"""

from typing import Any, Callable

# title 최대 길이 (prefix가 너무 길어지지 않도록)
_MAX_TITLE_LEN = 50


def _truncate(text: str, max_len: int = _MAX_TITLE_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _prefix_law(data: dict[str, Any]) -> str:
    """laws_full.jsonl / laws_etc.jsonl — 법령 조문."""
    meta = data.get("metadata", {})
    law_name = _truncate(meta.get("law_name") or data.get("title", ""))
    article_num = meta.get("article_number", "")
    article_title = meta.get("article_title", "")
    if article_num:
        if article_title:
            return f"[{law_name} > 제{article_num}조({article_title})]"
        return f"[{law_name} > 제{article_num}조]"
    return f"[{law_name}]" if law_name else ""


def _prefix_interpretation(data: dict[str, Any]) -> str:
    """interpretations.jsonl — 법제처/행정 해석례."""
    meta = data.get("metadata", {})
    answer_org = meta.get("answer_org", "법제처")
    title = _truncate(data.get("title", ""))
    return f"[{answer_org} 해석례 > {title}]" if title else ""


def _prefix_court_case(data: dict[str, Any]) -> str:
    """court_cases_*.jsonl — 판례."""
    meta = data.get("metadata", {})
    court = meta.get("court_name", "")
    case_no = meta.get("case_no", "")
    if court and case_no:
        return f"[{court} {case_no}]"
    return f"[{court or case_no}]" if (court or case_no) else ""


def _prefix_labor_interpretation(data: dict[str, Any]) -> str:
    """labor_interpretation.jsonl — 노무 질의회시."""
    meta = data.get("metadata", {})
    chapter = meta.get("chapter_title", "")
    section = meta.get("section_title", "")
    if chapter and section:
        return f"[{chapter} > {section}]"
    return f"[{chapter or section}]" if (chapter or section) else ""


def _prefix_hr_insurance(data: dict[str, Any]) -> str:
    """hr_insurance_edu.jsonl — 4대보험/교육."""
    meta = data.get("metadata", {})
    chapter = meta.get("chapter_title", "")
    section = meta.get("section_title", "")
    if chapter and section:
        return f"[{chapter} > {section}]"
    return f"[{chapter or section}]" if (chapter or section) else ""


def _prefix_tax_support(data: dict[str, Any]) -> str:
    """tax_support.jsonl — 세무 가이드."""
    meta = data.get("metadata", {})
    chapter = meta.get("chapter", "")
    return f"[세무 가이드 > {chapter}]" if chapter else ""


def _prefix_announcement(data: dict[str, Any]) -> str:
    """announcements.jsonl — 지원사업 공고."""
    meta = data.get("metadata", {})
    org = meta.get("organization", "")
    title = _truncate(data.get("title", ""))
    if org and title:
        return f"[{org} > {title}]"
    return f"[{org or title}]" if (org or title) else ""


def _prefix_startup_guide(data: dict[str, Any]) -> str:
    """industry_startup_guide_filtered.jsonl — 업종별 창업가이드."""
    title = data.get("title", "")
    return f"[업종별 창업가이드 > {title}]" if title else ""


def _prefix_startup_procedures(data: dict[str, Any]) -> str:
    """startup_procedures_filtered.jsonl — 창업절차."""
    title = data.get("title", "")
    return f"[창업절차 > {title}]" if title else ""


def _prefix_law_or_interpretation(data: dict[str, Any]) -> str:
    """법+해석례 병합 파일 (laws_finance_tax.jsonl 등) — type 필드로 분기."""
    if data.get("type") == "interpretation":
        return _prefix_interpretation(data)
    return _prefix_law(data)


_PREFIX_GENERATORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "laws_full.jsonl": _prefix_law,
    "laws_etc.jsonl": _prefix_law,
    "interpretations.jsonl": _prefix_interpretation,
    "court_cases_tax.jsonl": _prefix_court_case,
    "court_cases_labor.jsonl": _prefix_court_case,
    "labor_interpretation.jsonl": _prefix_labor_interpretation,
    "hr_insurance_edu.jsonl": _prefix_hr_insurance,
    "tax_support.jsonl": _prefix_tax_support,
    "announcements.jsonl": _prefix_announcement,
    "industry_startup_guide_filtered.jsonl": _prefix_startup_guide,
    "startup_procedures_filtered.jsonl": _prefix_startup_procedures,
    # law_common 분할 파일
    "laws_finance_tax.jsonl": _prefix_law_or_interpretation,
    "laws_hr_labor.jsonl": _prefix_law_or_interpretation,
    "laws_startup.jsonl": _prefix_law_or_interpretation,
    "laws_general.jsonl": _prefix_law,
    "interpretations_general.jsonl": _prefix_interpretation,
}


def generate_prefix(data: dict[str, Any], file_name: str) -> str:
    """JSONL 데이터와 파일명으로부터 contextual prefix를 생성합니다.

    Args:
        data: 파싱된 JSONL 데이터 딕셔너리
        file_name: 원본 파일 이름 (prefix 패턴 결정용)

    Returns:
        prefix 문자열 (빈 문자열이면 prefix 없음)
    """
    generator = _PREFIX_GENERATORS.get(file_name)
    if generator is None:
        return ""
    return generator(data).strip()
