# -*- coding: utf-8 -*-
"""
판례 수집 스크립트 (세무/회계, 노무/근로)

국가법령정보센터 Open API를 사용하여 판례를 수집합니다.
https://www.law.go.kr/LSW/openApi.do

사용법:
    전체 수집 (세무/회계 + 노무/근로):
    python collect_court_cases.py --all

    세무/회계만 수집:
    python collect_court_cases.py --tax

    노무/근로만 수집:
    python collect_court_cases.py --labor

    키워드 목록 표시:
    python collect_court_cases.py --list
"""

import os
import sys
import json
import asyncio
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import time

# 상위 디렉토리 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("경고: httpx가 설치되지 않았습니다. pip install httpx")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


# ============================================================
# 설정
# ============================================================
BASE_URL = "https://www.law.go.kr"
SEARCH_URL = f"{BASE_URL}/DRF/lawSearch.do"
DETAIL_URL = f"{BASE_URL}/DRF/lawService.do"

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "court_cases"

# API 호출 간격 (초)
API_DELAY = 0.3

# 수집 키워드 정의
TAX_KEYWORDS = [
    "법인세",
    "부가가치세",
    "소득세",
    "조세",
    "세금",
    "국세",
    "상속세",
    "증여세",
]

LABOR_KEYWORDS = [
    "근로",
    "임금",
    "해고",
    "노동",
    "퇴직",
    "산재",
    "고용",
]


def format_time(seconds: float) -> str:
    """초를 시:분:초 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}시간 {minutes}분 {secs}초"
    elif minutes > 0:
        return f"{minutes}분 {secs}초"
    else:
        return f"{secs}초"


def print_progress_bar(current: int, total: int, prefix: str = "", suffix: str = "", length: int = 40):
    """진행률 바 출력"""
    if total == 0:
        percent = 0
        filled = 0
    else:
        percent = current / total * 100
        filled = int(length * current // total)

    bar = "#" * filled + "-" * (length - filled)
    print(f"\r  {prefix} |{bar}| {percent:5.1f}% ({current:,}/{total:,}) {suffix}", end="", flush=True)


class CourtCaseCollector:
    """판례 수집기"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.collected_ids: Set[str] = set()  # 중복 방지용

    def _get_text(self, element, tag: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        if element is None:
            return None
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return None

    async def get_total_count(self, query: str = "") -> int:
        """키워드별 판례 수 조회"""
        params = {
            "OC": self.api_key,
            "target": "prec",
            "type": "XML",
            "display": 1,
            "page": 1,
        }
        if query:
            params["query"] = query

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            total_count = self._get_text(root, ".//totalCnt")

            return int(total_count) if total_count else 0

    async def get_case_list(self, query: str, page: int = 1, display: int = 100) -> List[Dict]:
        """판례 목록 조회"""
        params = {
            "OC": self.api_key,
            "target": "prec",
            "type": "XML",
            "display": display,
            "page": page,
            "query": query,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            cases = []
            for case in root.findall(".//prec"):
                case_data = self._parse_case_summary(case)
                if case_data and case_data["id"] not in self.collected_ids:
                    cases.append(case_data)
                    self.collected_ids.add(case_data["id"])

            return cases

    async def get_case_detail(self, case_id: str) -> Optional[Dict]:
        """판례 상세 조회"""
        params = {
            "OC": self.api_key,
            "target": "prec",
            "type": "XML",
            "ID": case_id,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(DETAIL_URL, params=params)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                detail = {
                    "id": case_id,
                    "case_name": self._get_text(root, ".//사건명") or "",
                    "case_no": self._get_text(root, ".//사건번호") or "",
                    "decision_date": self._get_text(root, ".//선고일자") or "",
                    "court_name": self._get_text(root, ".//법원명") or "",
                    "court_type": self._get_text(root, ".//사건종류명") or "",
                    "decision_type": self._get_text(root, ".//판결유형") or "",
                    "decision": self._get_text(root, ".//선고") or "",
                    "summary": self._get_text(root, ".//판시사항") or "",
                    "decision_summary": self._get_text(root, ".//판결요지") or "",
                    "reference": self._get_text(root, ".//참조조문") or "",
                    "reference_cases": self._get_text(root, ".//참조판례") or "",
                    "full_text": self._get_text(root, ".//판례내용") or "",
                }

                return detail

        except Exception as e:
            return None

    def _parse_case_summary(self, case_elem) -> Optional[Dict]:
        """판례 요약 파싱"""
        try:
            case_data = {
                "id": self._get_text(case_elem, "판례일련번호") or "",
                "case_name": self._get_text(case_elem, "사건명") or "",
                "case_no": self._get_text(case_elem, "사건번호") or "",
                "decision_date": self._get_text(case_elem, "선고일자") or "",
                "court_name": self._get_text(case_elem, "법원명") or "",
                "court_type": self._get_text(case_elem, "사건종류명") or "",
                "decision_type": self._get_text(case_elem, "판결유형") or "",
                "decision": self._get_text(case_elem, "선고") or "",
            }

            if case_data["id"]:
                return case_data
            return None

        except Exception as e:
            return None

    async def collect_by_keyword(
        self,
        keyword: str,
        max_items: int = None,
        fetch_detail: bool = True,
    ) -> List[Dict]:
        """키워드로 판례 수집"""
        items = []
        page = 1
        display = 100
        start_time = time.time()

        total_count = await self.get_total_count(keyword)
        if max_items:
            total_count = min(total_count, max_items)

        print(f"\n    '{keyword}' 검색: {total_count:,}건")

        while len(items) < total_count:
            try:
                page_items = await self.get_case_list(keyword, page=page, display=display)

                if not page_items:
                    break

                for case in page_items:
                    if max_items and len(items) >= max_items:
                        break

                    if fetch_detail:
                        detail = await self.get_case_detail(case["id"])
                        if detail:
                            case.update(detail)
                        await asyncio.sleep(API_DELAY)

                    items.append(case)

                    # 진행 상황 출력
                    elapsed = time.time() - start_time
                    if len(items) > 0 and elapsed > 0:
                        rate = len(items) / elapsed
                        remaining = (total_count - len(items)) / rate if rate > 0 else 0
                        print_progress_bar(
                            len(items), total_count,
                            prefix=f"    {keyword}",
                            suffix=f"| 남은 시간: {format_time(remaining)}"
                        )

                if len(page_items) < display:
                    break

                page += 1
                await asyncio.sleep(API_DELAY)

            except Exception as e:
                print(f"\n    [ERROR] {keyword} 수집 오류: {e}")
                break

        print()  # 줄바꿈
        return items

    async def collect_by_category(
        self,
        keywords: List[str],
        category_name: str,
        max_per_keyword: int = None,
    ) -> List[Dict]:
        """카테고리별 판례 수집 (중복 제거)"""
        all_items = []

        print(f"\n  [{category_name}] 수집 시작")
        print(f"  키워드: {', '.join(keywords)}")
        print("  " + "-" * 50)

        for keyword in keywords:
            items = await self.collect_by_keyword(
                keyword,
                max_items=max_per_keyword,
                fetch_detail=True,
            )
            all_items.extend(items)
            print(f"    → {keyword}: {len(items):,}건 수집 (누적 고유: {len(self.collected_ids):,}건)")

        # 중복 제거는 collected_ids로 이미 처리됨
        print(f"\n  [{category_name}] 완료: 총 {len(all_items):,}건")

        return all_items

    def save_results(
        self,
        items: List[Dict],
        category: str,
        keywords: List[str],
        output_file: Path,
    ):
        """결과 저장"""
        result = {
            "type": "판례",
            "category": category,
            "keywords": keywords,
            "total_count": len(items),
            "collected_at": datetime.now().isoformat(),
            "items": items,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  저장 완료: {output_file}")
        print(f"  총 {len(items):,}건")


async def collect_tax_cases(collector: CourtCaseCollector, max_per_keyword: int = None):
    """세무/회계 판례 수집"""
    items = await collector.collect_by_category(
        keywords=TAX_KEYWORDS,
        category_name="세무/회계",
        max_per_keyword=max_per_keyword,
    )

    output_file = OUTPUT_DIR / "prec_tax_accounting.json"
    collector.save_results(
        items=items,
        category="세무/회계",
        keywords=TAX_KEYWORDS,
        output_file=output_file,
    )

    return items


async def collect_labor_cases(collector: CourtCaseCollector, max_per_keyword: int = None):
    """노무/근로 판례 수집"""
    # 새로운 collector로 중복 ID 초기화
    items = await collector.collect_by_category(
        keywords=LABOR_KEYWORDS,
        category_name="노무/근로",
        max_per_keyword=max_per_keyword,
    )

    output_file = OUTPUT_DIR / "prec_labor.json"
    collector.save_results(
        items=items,
        category="노무/근로",
        keywords=LABOR_KEYWORDS,
        output_file=output_file,
    )

    return items


async def main():
    parser = argparse.ArgumentParser(description="판례 수집 (세무/회계, 노무/근로)")
    parser.add_argument("--api-key", type=str, help="국가법령정보센터 API 키")
    parser.add_argument("--all", action="store_true", help="전체 수집 (세무/회계 + 노무/근로)")
    parser.add_argument("--tax", action="store_true", help="세무/회계 판례만 수집")
    parser.add_argument("--labor", action="store_true", help="노무/근로 판례만 수집")
    parser.add_argument("--max", type=int, help="키워드당 최대 수집 건수")
    parser.add_argument("--list", action="store_true", help="수집 키워드 목록 표시")

    args = parser.parse_args()

    # 키워드 목록 표시
    if args.list:
        print("\n[세무/회계 키워드]")
        print("-" * 40)
        for i, kw in enumerate(TAX_KEYWORDS, 1):
            print(f"  {i}. {kw}")

        print("\n[노무/근로 키워드]")
        print("-" * 40)
        for i, kw in enumerate(LABOR_KEYWORDS, 1):
            print(f"  {i}. {kw}")
        print()
        return

    # API 키 확인
    api_key = args.api_key or os.getenv("LAW_API_KEY")

    if not api_key:
        print("오류: API 키가 필요합니다.")
        print()
        print("사용법:")
        print("  python collect_court_cases.py --api-key YOUR_API_KEY --all")
        print("  또는 .env 파일에 LAW_API_KEY=YOUR_API_KEY 설정")
        sys.exit(1)

    if not HAS_HTTPX:
        print("오류: httpx 패키지가 필요합니다.")
        print("설치: pip install httpx")
        sys.exit(1)

    # 시작
    total_start_time = time.time()

    print()
    print("=" * 70)
    print("  판례 수집 시작 (세무/회계, 노무/근로)")
    print("=" * 70)
    print(f"  API 키: {api_key[:4]}****")
    print(f"  저장 위치: {OUTPUT_DIR}")
    if args.max:
        print(f"  키워드당 최대 수집: {args.max:,}건")
    print("=" * 70)

    tax_items = []
    labor_items = []

    if args.all or (not args.tax and not args.labor):
        # 전체 수집
        tax_collector = CourtCaseCollector(api_key)
        tax_items = await collect_tax_cases(tax_collector, args.max)

        labor_collector = CourtCaseCollector(api_key)
        labor_items = await collect_labor_cases(labor_collector, args.max)

    elif args.tax:
        tax_collector = CourtCaseCollector(api_key)
        tax_items = await collect_tax_cases(tax_collector, args.max)

    elif args.labor:
        labor_collector = CourtCaseCollector(api_key)
        labor_items = await collect_labor_cases(labor_collector, args.max)

    # 최종 요약
    total_elapsed = time.time() - total_start_time

    print()
    print("=" * 70)
    print("  [COMPLETE] 수집 완료!")
    print("=" * 70)
    if tax_items:
        print(f"  - 세무/회계 판례: {len(tax_items):,}건")
    if labor_items:
        print(f"  - 노무/근로 판례: {len(labor_items):,}건")
    print(f"  - 총 소요 시간: {format_time(total_elapsed)}")
    print(f"  - 저장 위치: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
