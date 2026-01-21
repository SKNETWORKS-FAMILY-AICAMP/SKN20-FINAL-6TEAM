"""
대한민국 전체 법령 수집 스크립트

국가법령정보센터 Open API를 사용하여 모든 현행 법령을 수집합니다.
https://www.law.go.kr/LSW/openApi.do

사용법:
    python collect_all_laws.py --api-key YOUR_API_KEY
    또는 .env 파일에 LAW_API_KEY 설정 후:
    python collect_all_laws.py
"""

import os
import sys
import json
import time
import asyncio
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# 상위 디렉토리 추가 (app 모듈 import용)
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
OUTPUT_FILE = OUTPUT_DIR / "01_laws_full.json"
CHECKPOINT_FILE = OUTPUT_DIR / "collection_checkpoint.json"

# API 호출 간격 (초) - 서버 부하 방지
API_DELAY = 0.3


class LawCollectorAll:
    """전체 법령 수집기"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.collected_laws = []
        self.failed_laws = []
        self.checkpoint = {"last_page": 0, "total_collected": 0}

    def _get_text(self, element, tag: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        if element is None:
            return None
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return None

    async def get_total_count(self) -> int:
        """전체 법령 수 조회"""
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "XML",
            "display": 1,
            "page": 1,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)
            total_count = self._get_text(root, ".//totalCnt")

            return int(total_count) if total_count else 0

    async def get_law_list(self, page: int = 1, display: int = 100) -> List[Dict]:
        """법령 목록 조회 (페이지 단위)"""
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "XML",
            "display": display,
            "page": page,
            "sort": "lasc",  # 법령명 오름차순
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(SEARCH_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            laws = []
            for law in root.findall(".//law"):
                law_data = {
                    "law_id": self._get_text(law, "법령ID") or self._get_text(law, "lawId") or "",
                    "name": self._get_text(law, "법령명한글") or self._get_text(law, "법령명_한글") or "",
                    "law_type": self._get_text(law, "법령종류") or "",
                    "ministry": self._get_text(law, "소관부처") or self._get_text(law, "소관부처명") or "",
                    "enforcement_date": self._get_text(law, "시행일자") or "",
                    "promulgation_date": self._get_text(law, "공포일자") or "",
                    "promulgation_no": self._get_text(law, "공포번호") or "",
                }
                if law_data["law_id"] and law_data["name"]:
                    laws.append(law_data)

            return laws

    async def get_law_detail(self, law_id: str) -> Optional[Dict]:
        """법령 상세 조회 (조문 포함)"""
        params = {
            "OC": self.api_key,
            "target": "law",
            "type": "XML",
            "ID": law_id,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.get(DETAIL_URL, params=params)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                # 기본 정보
                law_info = {
                    "law_id": law_id,
                    "name": self._get_text(root, ".//법령명_한글") or self._get_text(root, ".//법령명한글") or "",
                    "ministry": self._get_text(root, ".//소관부처명") or self._get_text(root, ".//소관부처") or "",
                    "enforcement_date": self._get_text(root, ".//시행일자") or "",
                    "articles": [],
                }

                # 조문 추출
                for article in root.findall(".//조문단위"):
                    article_data = self._parse_article(article)
                    if article_data:
                        law_info["articles"].append(article_data)

                # 조문단위가 없으면 조문으로 시도
                if not law_info["articles"]:
                    for article in root.findall(".//조문"):
                        article_data = self._parse_article_simple(article)
                        if article_data:
                            law_info["articles"].append(article_data)

                return law_info

            except Exception as e:
                print(f"    상세 조회 실패 ({law_id}): {e}")
                return None

    def _parse_article(self, article_elem) -> Optional[Dict]:
        """조문 파싱 (조문단위 구조)"""
        article_no = self._get_text(article_elem, "조문번호") or ""
        article_title = self._get_text(article_elem, "조문제목") or ""
        article_content = self._get_text(article_elem, "조문내용") or ""

        # 항 추출
        clauses = []
        for clause in article_elem.findall(".//항"):
            clause_data = self._parse_clause(clause)
            if clause_data:
                clauses.append(clause_data)

        if article_content or clauses:
            return {
                "number": article_no,
                "title": article_title,
                "content": article_content,
                "clauses": clauses,
            }
        return None

    def _parse_article_simple(self, article_elem) -> Optional[Dict]:
        """조문 파싱 (단순 구조)"""
        article_no = self._get_text(article_elem, "조문번호") or ""
        article_title = self._get_text(article_elem, "조문제목") or ""
        article_content = self._get_text(article_elem, "조문내용") or ""

        if not article_content:
            # 직접 텍스트 추출
            article_content = article_elem.text or ""

        if article_content:
            return {
                "number": article_no,
                "title": article_title,
                "content": article_content,
                "clauses": [],
            }
        return None

    def _parse_clause(self, clause_elem) -> Optional[Dict]:
        """항 파싱"""
        clause_no = self._get_text(clause_elem, "항번호") or ""
        clause_content = self._get_text(clause_elem, "항내용") or ""

        # 호 추출
        items = []
        for item in clause_elem.findall(".//호"):
            item_no = self._get_text(item, "호번호") or ""
            item_content = self._get_text(item, "호내용") or ""
            if item_content:
                items.append({
                    "number": item_no,
                    "content": item_content,
                })

        if clause_content or items:
            return {
                "number": clause_no,
                "content": clause_content,
                "items": items,
            }
        return None

    def save_checkpoint(self, page: int, total_collected: int):
        """체크포인트 저장"""
        self.checkpoint = {
            "last_page": page,
            "total_collected": total_collected,
            "timestamp": datetime.now().isoformat(),
        }
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.checkpoint, f, ensure_ascii=False, indent=2)

    def load_checkpoint(self) -> Dict:
        """체크포인트 로드"""
        if CHECKPOINT_FILE.exists():
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"last_page": 0, "total_collected": 0}

    def save_results(self, laws: List[Dict], output_file: Path = OUTPUT_FILE):
        """결과 저장"""
        result = {
            "type": "현행법령",
            "description": "대한민국 전체 현행 법령",
            "total_count": len(laws),
            "collected_at": datetime.now().isoformat(),
            "laws": laws,
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n저장 완료: {output_file}")
        print(f"총 {len(laws)}개 법령")

    async def collect_all(self, resume: bool = True, max_laws: int = None):
        """전체 법령 수집"""
        print("=" * 60)
        print("대한민국 전체 법령 수집")
        print("=" * 60)

        # 체크포인트 확인
        start_page = 1
        if resume:
            checkpoint = self.load_checkpoint()
            if checkpoint.get("last_page", 0) > 0:
                start_page = checkpoint["last_page"] + 1
                print(f"이전 작업 재개: 페이지 {start_page}부터")

                # 기존 결과 로드
                if OUTPUT_FILE.exists():
                    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                        self.collected_laws = existing.get("laws", [])
                    print(f"기존 수집 데이터: {len(self.collected_laws)}개")

        # 전체 법령 수 확인
        print("\n[1] 전체 법령 수 조회 중...")
        total_count = await self.get_total_count()
        print(f"    전체 법령 수: {total_count}개")

        if max_laws:
            total_count = min(total_count, max_laws)
            print(f"    수집 제한: {max_laws}개")

        # 페이지 계산
        display = 100
        total_pages = (total_count + display - 1) // display

        print(f"\n[2] 법령 수집 시작 (페이지 {start_page}/{total_pages})")

        try:
            for page in range(start_page, total_pages + 1):
                print(f"\n--- 페이지 {page}/{total_pages} ---")

                # 법령 목록 조회
                laws = await self.get_law_list(page=page, display=display)
                print(f"    {len(laws)}개 법령 발견")

                # 각 법령의 상세 정보 조회
                for i, law in enumerate(laws, 1):
                    if max_laws and len(self.collected_laws) >= max_laws:
                        print(f"\n최대 수집 수 도달: {max_laws}개")
                        self.save_results(self.collected_laws)
                        return

                    print(f"    [{i}/{len(laws)}] {law['name'][:40]}...", end="")

                    detail = await self.get_law_detail(law["law_id"])

                    if detail:
                        self.collected_laws.append(detail)
                        print(f" OK ({len(detail.get('articles', []))}개 조문)")
                    else:
                        self.failed_laws.append(law)
                        print(" FAILED")

                    await asyncio.sleep(API_DELAY)

                # 페이지 완료 후 체크포인트 저장
                self.save_checkpoint(page, len(self.collected_laws))
                print(f"    체크포인트 저장: {len(self.collected_laws)}개 수집됨")

                # 중간 저장 (10페이지마다)
                if page % 10 == 0:
                    self.save_results(self.collected_laws)
                    print(f"    중간 저장 완료")

        except KeyboardInterrupt:
            print("\n\n중단됨. 현재까지 수집된 데이터를 저장합니다...")

        finally:
            # 최종 저장
            self.save_results(self.collected_laws)

            if self.failed_laws:
                failed_file = OUTPUT_DIR / "failed_laws.json"
                with open(failed_file, 'w', encoding='utf-8') as f:
                    json.dump(self.failed_laws, f, ensure_ascii=False, indent=2)
                print(f"실패 목록 저장: {failed_file}")

        print("\n" + "=" * 60)
        print(f"수집 완료!")
        print(f"총 수집: {len(self.collected_laws)}개")
        print(f"실패: {len(self.failed_laws)}개")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="대한민국 전체 법령 수집")
    parser.add_argument("--api-key", type=str, help="국가법령정보센터 API 키")
    parser.add_argument("--max", type=int, help="최대 수집 법령 수 (테스트용)")
    parser.add_argument("--no-resume", action="store_true", help="처음부터 다시 수집")

    args = parser.parse_args()

    # API 키 확인
    api_key = args.api_key or os.getenv("LAW_API_KEY")

    if not api_key or api_key == "여기에_API_키_입력":
        print("오류: API 키가 필요합니다.")
        print()
        print("사용법:")
        print("  1. python collect_all_laws.py --api-key YOUR_API_KEY")
        print("  2. 또는 .env 파일에 LAW_API_KEY=YOUR_API_KEY 설정")
        print()
        print("API 키 발급: https://www.law.go.kr/LSW/openApi.do")
        sys.exit(1)

    if not HAS_HTTPX:
        print("오류: httpx 패키지가 필요합니다.")
        print("설치: pip install httpx")
        sys.exit(1)

    collector = LawCollectorAll(api_key)
    await collector.collect_all(
        resume=not args.no_resume,
        max_laws=args.max,
    )


if __name__ == "__main__":
    asyncio.run(main())
