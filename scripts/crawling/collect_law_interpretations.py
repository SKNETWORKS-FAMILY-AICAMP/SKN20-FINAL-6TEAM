# -*- coding: utf-8 -*-
"""
법령해석례 수집 스크립트

국가법령정보센터 Open API를 사용하여 법령해석례를 수집합니다.
https://www.law.go.kr/LSW/openApi.do

사용법:
    python collect_law_interpretations.py --all

    특정 기관만 수집:
    python collect_law_interpretations.py --org 고용노동부

    기관 목록 표시:
    python collect_law_interpretations.py --list
"""

import os
import sys
import json
import asyncio
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
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

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "law"

# API 호출 간격 (초)
API_DELAY = 0.3


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

# 수집 대상 기관 목록 (질의기관명 기준 분류)
# aliases: 과거 명칭 또는 유사 명칭 포함
TARGET_ORGS = {
    "고용노동부": {
        "aliases": ["고용노동부", "노동부"],
        "filename": "expc_고용노동부.json"
    },
    "국토교통부": {
        "aliases": ["국토교통부", "국토해양부", "건설교통부"],
        "filename": "expc_국토교통부.json"
    },
    "기획재정부": {
        "aliases": ["기획재정부", "재정경제부", "기획예산처"],
        "filename": "expc_기획재정부.json"
    },
    "해양수산부": {
        "aliases": ["해양수산부"],
        "filename": "expc_해양수산부.json"
    },
    "행정안전부": {
        "aliases": ["행정안전부", "행정자치부", "안전행정부"],
        "filename": "expc_행정안전부.json"
    },
    "기후에너지환경부": {
        "aliases": ["기후에너지환경부", "환경부"],
        "filename": "expc_기후에너지환경부.json"
    },
    "관세청": {
        "aliases": ["관세청"],
        "filename": "expc_관세청.json"
    },
    "국세청": {
        "aliases": ["국세청"],
        "filename": "expc_국세청.json"
    },
    "교육부": {
        "aliases": ["교육부", "교육과학기술부", "교육인적자원부"],
        "filename": "expc_교육부.json"
    },
    "과학기술정보통신부": {
        "aliases": ["과학기술정보통신부", "미래창조과학부", "정보통신부", "과학기술부"],
        "filename": "expc_과학기술정보통신부.json"
    },
    "국가보훈부": {
        "aliases": ["국가보훈부", "국가보훈처"],
        "filename": "expc_국가보훈부.json"
    },
    "국방부": {
        "aliases": ["국방부"],
        "filename": "expc_국방부.json"
    },
    "농림축산식품부": {
        "aliases": ["농림축산식품부", "농림수산식품부", "농림부"],
        "filename": "expc_농림축산식품부.json"
    },
    "문화체육관광부": {
        "aliases": ["문화체육관광부", "문화관광부"],
        "filename": "expc_문화체육관광부.json"
    },
    "법무부": {
        "aliases": ["법무부"],
        "filename": "expc_법무부.json"
    },
    "보건복지부": {
        "aliases": ["보건복지부", "보건복지가족부"],
        "filename": "expc_보건복지부.json"
    },
    "산업통상자원부": {
        "aliases": ["산업통상자원부", "지식경제부", "산업자원부"],
        "filename": "expc_산업통상자원부.json"
    },
    "여성가족부": {
        "aliases": ["여성가족부", "성평등가족부"],
        "filename": "expc_여성가족부.json"
    },
    "외교부": {
        "aliases": ["외교부", "외교통상부"],
        "filename": "expc_외교부.json"
    },
    "중소벤처기업부": {
        "aliases": ["중소벤처기업부", "중소기업청"],
        "filename": "expc_중소벤처기업부.json"
    },
    "통일부": {
        "aliases": ["통일부"],
        "filename": "expc_통일부.json"
    },
    "법제처": {
        "aliases": ["법제처"],
        "filename": "expc_법제처.json"
    },
    "식품의약품안전처": {
        "aliases": ["식품의약품안전처", "식품의약품안전청"],
        "filename": "expc_식품의약품안전처.json"
    },
    "인사혁신처": {
        "aliases": ["인사혁신처", "중앙인사위원회"],
        "filename": "expc_인사혁신처.json"
    },
    "기상청": {
        "aliases": ["기상청"],
        "filename": "expc_기상청.json"
    },
    "국가유산청": {
        "aliases": ["국가유산청", "문화재청"],
        "filename": "expc_국가유산청.json"
    },
    "농촌진흥청": {
        "aliases": ["농촌진흥청"],
        "filename": "expc_농촌진흥청.json"
    },
    "경찰청": {
        "aliases": ["경찰청"],
        "filename": "expc_경찰청.json"
    },
    "방위사업청": {
        "aliases": ["방위사업청"],
        "filename": "expc_방위사업청.json"
    },
    "병무청": {
        "aliases": ["병무청"],
        "filename": "expc_병무청.json"
    },
    "산림청": {
        "aliases": ["산림청"],
        "filename": "expc_산림청.json"
    },
    "소방청": {
        "aliases": ["소방청", "소방방재청"],
        "filename": "expc_소방청.json"
    },
    "재외동포청": {
        "aliases": ["재외동포청"],
        "filename": "expc_재외동포청.json"
    },
    "조달청": {
        "aliases": ["조달청"],
        "filename": "expc_조달청.json"
    },
    "질병관리청": {
        "aliases": ["질병관리청", "질병관리본부"],
        "filename": "expc_질병관리청.json"
    },
    "국가데이터청": {
        "aliases": ["국가데이터청", "통계청"],
        "filename": "expc_국가데이터청.json"
    },
    "지식재산처": {
        "aliases": ["지식재산처", "특허청"],
        "filename": "expc_지식재산처.json"
    },
    "해양경찰청": {
        "aliases": ["해양경찰청"],
        "filename": "expc_해양경찰청.json"
    },
    "행정중심복합도시건설청": {
        "aliases": ["행정중심복합도시건설청"],
        "filename": "expc_행정중심복합도시건설청.json"
    },
}


class LawInterpretationCollector:
    """법령해석례 수집기"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.collected_items = []

    def _get_text(self, element, tag: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        if element is None:
            return None
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return None

    async def get_total_count(self, query: str = "") -> int:
        """전체 법령해석례 수 조회"""
        params = {
            "OC": self.api_key,
            "target": "expc",
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

    async def get_detail(self, expc_id: str) -> Optional[Dict]:
        """법령해석례 상세 조회"""
        params = {
            "OC": self.api_key,
            "target": "expc",
            "type": "XML",
            "ID": expc_id,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(DETAIL_URL, params=params)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                detail = {
                    "id": expc_id,
                    "title": (self._get_text(root, ".//안건명") or ""),
                    "case_no": (self._get_text(root, ".//안건번호") or ""),
                    "answer_date": (self._get_text(root, ".//해석일자") or ""),
                    "answer_org": (self._get_text(root, ".//해석기관명") or ""),
                    "question_org": (self._get_text(root, ".//질의기관명") or ""),
                    "question_summary": (self._get_text(root, ".//질의요지") or ""),
                    "answer": (self._get_text(root, ".//회답") or ""),
                    "reason": (self._get_text(root, ".//이유") or ""),
                }

                return detail

        except Exception as e:
            return None

    async def collect_all_interpretations(
        self,
        max_items: int = None,
        display: int = 100,
        fetch_detail: bool = True,
    ) -> List[Dict]:
        """전체 법령해석례 수집 (검색어 없이)"""
        items = []
        page = 1
        start_time = time.time()

        total_count = await self.get_total_count()
        print(f"\n  +{'-' * 60}+")
        print(f"  | 전체 법령해석례 건수: {total_count:,}건".ljust(62) + "|")

        if max_items:
            total_count = min(total_count, max_items)
            print(f"  | 수집 제한: {max_items:,}건".ljust(62) + "|")

        total_pages = (total_count + display - 1) // display
        print(f"  | 총 페이지 수: {total_pages:,} 페이지 (페이지당 {display}건)".ljust(62) + "|")
        print(f"  +{'-' * 60}+\n")

        while True:
            if max_items and len(items) >= max_items:
                break

            elapsed = time.time() - start_time
            elapsed_str = format_time(elapsed)

            # 남은 시간 추정
            if len(items) > 0:
                rate = len(items) / elapsed
                remaining = (total_count - len(items)) / rate if rate > 0 else 0
                remaining_str = format_time(remaining)
                eta_str = f"예상 남은 시간: {remaining_str}"
            else:
                eta_str = "계산 중..."

            print_progress_bar(
                len(items), total_count,
                prefix=f"수집",
                suffix=f"| 경과: {elapsed_str} | {eta_str}".ljust(45)
            )

            params = {
                "OC": self.api_key,
                "target": "expc",
                "type": "XML",
                "display": display,
                "page": page,
                "sort": "date",
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(SEARCH_URL, params=params)
                    response.raise_for_status()

                    root = ET.fromstring(response.text)

                    page_items = []
                    for item in root.findall(".//expc"):
                        item_data = self._parse_item(item)
                        if item_data:
                            page_items.append(item_data)

                    if not page_items:
                        print(f"\n  [OK] 완료 (더 이상 데이터 없음)")
                        break

                    if fetch_detail:
                        for i, item in enumerate(page_items):
                            if max_items and len(items) + i >= max_items:
                                break

                            detail = await self.get_detail(item["id"])
                            if detail:
                                item.update(detail)

                            await asyncio.sleep(API_DELAY)

                            # 상세 조회 진행 상황 업데이트
                            current_total = len(items) + i + 1
                            elapsed = time.time() - start_time
                            elapsed_str = format_time(elapsed)

                            if current_total > 0:
                                rate = current_total / elapsed
                                remaining = (total_count - current_total) / rate if rate > 0 else 0
                                remaining_str = format_time(remaining)
                                eta_str = f"예상 남은 시간: {remaining_str}"
                            else:
                                eta_str = "계산 중..."

                            print_progress_bar(
                                current_total, total_count,
                                prefix=f"수집",
                                suffix=f"| 경과: {elapsed_str} | {eta_str}".ljust(45)
                            )

                    items.extend(page_items)

                    if len(page_items) < display:
                        break

                    page += 1
                    await asyncio.sleep(API_DELAY)

            except Exception as e:
                print(f"\n  [ERROR] 오류 발생: {e}")
                break

        # 완료 메시지
        elapsed = time.time() - start_time
        print(f"\n\n  [OK] 수집 완료! 총 {len(items):,}건, 소요 시간: {format_time(elapsed)}")

        return items[:max_items] if max_items else items

    def _parse_item(self, item_elem) -> Optional[Dict]:
        """법령해석례 항목 파싱"""
        try:
            item_data = {
                "id": (self._get_text(item_elem, "법령해석례일련번호") or ""),
                "title": (self._get_text(item_elem, "안건명") or ""),
                "case_no": (self._get_text(item_elem, "안건번호") or ""),
                "answer_date": (self._get_text(item_elem, "회신일자") or ""),
                "answer_org": (self._get_text(item_elem, "회신기관명") or ""),
                "question_org": (self._get_text(item_elem, "질의기관명") or ""),
                "question_summary": (self._get_text(item_elem, "질의요지") or ""),
                "answer": (self._get_text(item_elem, "회답") or ""),
                "reason": (self._get_text(item_elem, "이유") or ""),
            }

            if item_data["id"] or item_data["title"]:
                return item_data
            return None

        except Exception as e:
            print(f"    파싱 오류: {e}")
            return None

    def save_results(
        self,
        items: List[Dict],
        org_name: str,
        output_file: Path,
    ):
        """결과 저장"""
        result = {
            "type": "법령해석례",
            "org": org_name,
            "collected_count": len(items),
            "collected_at": datetime.now().isoformat(),
            "items": items,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"  저장: {output_file.name} ({len(items)}건)")


def classify_by_question_org(items: List[Dict]) -> Dict[str, List[Dict]]:
    """수집된 항목을 질의기관명 기준으로 분류"""
    classified = {org_name: [] for org_name in TARGET_ORGS.keys()}
    classified["기타"] = []
    classified["민원인"] = []

    for item in items:
        question_org = item.get("question_org", "")

        if not question_org:
            classified["기타"].append(item)
            continue

        if question_org == "민원인":
            classified["민원인"].append(item)
            continue

        matched = False
        for org_name, org_info in TARGET_ORGS.items():
            for alias in org_info["aliases"]:
                # 질의기관명이 alias로 시작하는 경우 (하위 부서 포함)
                if question_org.startswith(alias):
                    classified[org_name].append(item)
                    matched = True
                    break
            if matched:
                break

        if not matched:
            classified["기타"].append(item)

    return classified


async def collect_and_classify_all(
    collector: LawInterpretationCollector,
    max_items: int = None,
):
    """전체 수집 후 질의기관별 분류"""
    total_start_time = time.time()

    print("\n" + "=" * 70)
    print("  [전체 법령해석례 수집 및 질의기관별 분류]")
    print("=" * 70)

    # 1. 전체 수집
    print("\n" + "─" * 70)
    print("  [1단계] 전체 법령해석례 수집")
    print("─" * 70)

    items = await collector.collect_all_interpretations(max_items=max_items)

    # 2. 질의기관별 분류
    print("\n" + "─" * 70)
    print("  [2단계] 질의기관별 분류")
    print("─" * 70)

    classified = classify_by_question_org(items)

    # 통계 출력 (테이블 형식)
    print("\n  +---------------------------------+----------+----------+")
    print("  | 기관명                          |    건수  |   비율   |")
    print("  +---------------------------------+----------+----------+")

    total_items = len(items)
    total_classified = 0

    for org_name in TARGET_ORGS.keys():
        count = len(classified[org_name])
        if count > 0:
            pct = (count / total_items * 100) if total_items > 0 else 0
            print(f"  | {org_name:<30} | {count:>7,} | {pct:>6.1f}% |")
            total_classified += count

    # 민원인
    minwon_count = len(classified['민원인'])
    if minwon_count > 0:
        pct = (minwon_count / total_items * 100) if total_items > 0 else 0
        print(f"  | {'민원인':<30} | {minwon_count:>7,} | {pct:>6.1f}% |")

    # 기타
    etc_count = len(classified['기타'])
    if etc_count > 0:
        pct = (etc_count / total_items * 100) if total_items > 0 else 0
        print(f"  | {'기타':<30} | {etc_count:>7,} | {pct:>6.1f}% |")

    print("  +---------------------------------+----------+----------+")
    print(f"  | {'합계':<30} | {total_items:>7,} | {100.0:>6.1f}% |")
    print("  +---------------------------------+----------+----------+")

    # 3. 기관별 파일 저장
    print("\n" + "─" * 70)
    print("  [3단계] 기관별 파일 저장")
    print("─" * 70)

    saved_count = 0
    total_orgs_to_save = sum(1 for org in TARGET_ORGS if classified[org]) + \
                         (1 if classified["민원인"] else 0) + \
                         (1 if classified["기타"] else 0) + 1  # +1 for 전체

    for org_name, org_info in TARGET_ORGS.items():
        org_items = classified[org_name]
        if org_items:
            output_file = OUTPUT_DIR / org_info["filename"]
            collector.save_results(
                items=org_items,
                org_name=org_name,
                output_file=output_file,
            )
            saved_count += 1
            print_progress_bar(saved_count, total_orgs_to_save, prefix="저장 진행", suffix="")
            print()

    # 민원인 저장
    if classified["민원인"]:
        output_file = OUTPUT_DIR / "expc_민원인.json"
        collector.save_results(
            items=classified["민원인"],
            org_name="민원인",
            output_file=output_file,
        )
        saved_count += 1
        print_progress_bar(saved_count, total_orgs_to_save, prefix="저장 진행", suffix="")
        print()

    # 기타 저장
    if classified["기타"]:
        output_file = OUTPUT_DIR / "expc_기타.json"
        collector.save_results(
            items=classified["기타"],
            org_name="기타",
            output_file=output_file,
        )
        saved_count += 1
        print_progress_bar(saved_count, total_orgs_to_save, prefix="저장 진행", suffix="")
        print()

    # 전체 저장
    output_file = OUTPUT_DIR / "expc_전체.json"
    collector.save_results(
        items=items,
        org_name="전체",
        output_file=output_file,
    )
    saved_count += 1
    print_progress_bar(saved_count, total_orgs_to_save, prefix="저장 진행", suffix="")
    print()

    # 최종 요약
    total_elapsed = time.time() - total_start_time
    print("\n" + "=" * 70)
    print("  [COMPLETE] 전체 작업 완료!")
    print("=" * 70)
    print(f"  - 총 수집 건수: {len(items):,}건")
    print(f"  - 분류된 기관 수: {saved_count}개")
    print(f"  - 저장 위치: {OUTPUT_DIR}")
    print(f"  - 총 소요 시간: {format_time(total_elapsed)}")
    print("=" * 70)

    return classified


async def main():
    parser = argparse.ArgumentParser(description="법령해석례 수집 (질의기관별 분류)")
    parser.add_argument("--api-key", type=str, help="국가법령정보센터 API 키")
    parser.add_argument("--org", type=str, help="특정 기관만 조회 (수집 후 필터링)")
    parser.add_argument("--max", type=int, help="최대 수집 건수")
    parser.add_argument("--all", action="store_true", help="전체 수집 및 기관별 분류")
    parser.add_argument("--list", action="store_true", help="수집 대상 기관 목록 표시")

    args = parser.parse_args()

    # 기관 목록 표시
    if args.list:
        print("\n수집 대상 기관 목록 (39개):")
        print("-" * 60)
        for i, (org_name, org_info) in enumerate(TARGET_ORGS.items(), 1):
            aliases = ", ".join(org_info["aliases"])
            print(f"  {i:2}. {org_name}")
            if len(org_info["aliases"]) > 1:
                print(f"      (포함: {aliases})")
        print()
        return

    # API 키 확인
    api_key = args.api_key or os.getenv("LAW_API_KEY")

    if not api_key:
        print("오류: API 키가 필요합니다.")
        print()
        print("사용법:")
        print("  python collect_law_interpretations.py --api-key YOUR_API_KEY --all")
        print("  또는 .env 파일에 LAW_API_KEY=YOUR_API_KEY 설정")
        sys.exit(1)

    if not HAS_HTTPX:
        print("오류: httpx 패키지가 필요합니다.")
        print("설치: pip install httpx")
        sys.exit(1)

    collector = LawInterpretationCollector(api_key)

    print()
    print("=" * 70)
    print("법령해석례 수집 시작")
    print(f"API 키: {api_key[:4]}****")
    print("=" * 70)

    if args.all:
        await collect_and_classify_all(collector, args.max)
    else:
        # 기본: 전체 수집 및 분류
        await collect_and_classify_all(collector, args.max)

    print()
    print("=" * 70)
    print("수집 완료!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
