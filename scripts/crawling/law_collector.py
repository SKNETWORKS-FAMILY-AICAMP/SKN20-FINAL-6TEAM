"""
법령 데이터 수집기

국가법령정보센터 Open API 활용
https://www.law.go.kr/LSW/openApi.do

수집 대상:
- 노동 관련 법률 (근로기준법, 최저임금법, 퇴직급여보장법 등)
- 시행령/시행규칙
- 고시/훈령
"""
import httpx
import asyncio
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
import json

from langchain_core.documents import Document
from app.rag.vectorstore import get_vectorstore_manager
from app.config import settings


@dataclass
class LawArticle:
    """법령 조문"""
    law_name: str           # 법령명
    article_no: str         # 조문 번호 (제1조, 제2조 등)
    article_title: str      # 조문 제목
    content: str            # 조문 내용
    law_type: str           # 법률/시행령/시행규칙
    enforcement_date: str   # 시행일
    law_id: str = ""        # 법령 ID
    keywords: List[str] = field(default_factory=list)


class LawCollector:
    """
    국가법령정보센터 API 기반 법령 수집기

    API 문서: https://www.law.go.kr/LSW/openApi.do
    """

    # 국가법령정보센터 Open API
    BASE_URL = "https://www.law.go.kr"
    API_URL = "https://www.law.go.kr/DRF/lawSearch.do"
    DETAIL_URL = "https://www.law.go.kr/DRF/lawService.do"

    # 노동 관련 주요 법령 목록
    LABOR_LAWS = [
        "근로기준법",
        "최저임금법",
        "근로자퇴직급여 보장법",
        "고용보험법",
        "산업재해보상보험법",
        "국민연금법",
        "국민건강보험법",
        "남녀고용평등과 일·가정 양립 지원에 관한 법률",
        "기간제 및 단시간근로자 보호 등에 관한 법률",
        "파견근로자 보호 등에 관한 법률",
        "근로자참여 및 협력증진에 관한 법률",
        "노동조합 및 노동관계조정법",
        "임금채권보장법",
        "고용정책 기본법",
        "직업안정법",
        "고용상 연령차별금지 및 고령자고용촉진에 관한 법률",
        "장애인고용촉진 및 직업재활법",
        "청년고용촉진 특별법",
    ]

    # 법령 유형 매핑
    LAW_TYPE_MAP = {
        "법률": "primary",
        "시행령": "secondary",
        "시행규칙": "secondary",
        "대통령령": "secondary",
        "총리령": "secondary",
        "부령": "secondary",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: 국가법령정보센터 API 키 (없으면 기본 검색 사용)
        """
        self.api_key = api_key or getattr(settings, 'LAW_API_KEY', None)
        self.vs_manager = get_vectorstore_manager()

    async def search_laws(
        self,
        query: str,
        target: str = "law",  # law, ordin, admrul
        display: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        법령 검색

        Args:
            query: 검색어
            target: 검색 대상 (law: 법령, ordin: 자치법규, admrul: 행정규칙)
            display: 결과 수
        """
        params = {
            "OC": self.api_key or "test",
            "target": target,
            "type": "XML",
            "query": query,
            "display": display,
            "sort": "effd",  # 시행일순
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.API_URL, params=params)
                response.raise_for_status()

                # XML 파싱
                root = ET.fromstring(response.text)

                laws = []
                for law in root.findall(".//law"):
                    laws.append({
                        "law_id": self._get_text(law, "법령ID") or self._get_text(law, "lawId"),
                        "law_name": self._get_text(law, "법령명한글") or self._get_text(law, "lawNameKr"),
                        "law_type": self._get_text(law, "법령종류") or self._get_text(law, "lawType"),
                        "enforcement_date": self._get_text(law, "시행일자") or self._get_text(law, "efforceDate"),
                        "ministry": self._get_text(law, "소관부처") or self._get_text(law, "ministry"),
                        "link": self._get_text(law, "법령상세링크") or self._get_text(law, "lawDetailLink"),
                    })

                return laws

            except Exception as e:
                print(f"Law search error: {e}")
                return []

    async def get_law_detail(self, law_id: str) -> Optional[Dict[str, Any]]:
        """
        법령 상세 조회 (조문 포함)

        Args:
            law_id: 법령 ID
        """
        params = {
            "OC": self.api_key or "test",
            "target": "law",
            "type": "XML",
            "ID": law_id,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(self.DETAIL_URL, params=params)
                response.raise_for_status()

                root = ET.fromstring(response.text)

                # 기본 정보
                law_info = {
                    "law_id": law_id,
                    "law_name": self._get_text(root, ".//법령명_한글") or self._get_text(root, ".//법령명한글"),
                    "law_type": self._get_text(root, ".//법령종류"),
                    "enforcement_date": self._get_text(root, ".//시행일자"),
                    "ministry": self._get_text(root, ".//소관부처명"),
                    "articles": [],
                }

                # 조문 추출
                for article in root.findall(".//조문"):
                    article_data = {
                        "article_no": self._get_text(article, "조문번호") or "",
                        "article_title": self._get_text(article, "조문제목") or "",
                        "content": self._get_text(article, "조문내용") or "",
                    }

                    # 항 추출
                    paragraphs = []
                    for para in article.findall(".//항"):
                        para_content = self._get_text(para, "항내용") or para.text or ""
                        if para_content:
                            paragraphs.append(para_content)

                    if paragraphs:
                        article_data["paragraphs"] = paragraphs
                        article_data["content"] = "\n".join(paragraphs)

                    if article_data["content"]:
                        law_info["articles"].append(article_data)

                return law_info

            except Exception as e:
                print(f"Law detail error for {law_id}: {e}")
                return None

    def _get_text(self, element, tag: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        if element is None:
            return None
        found = element.find(tag)
        if found is not None and found.text:
            return found.text.strip()
        return None

    async def collect_labor_laws(
        self,
        include_enforcement: bool = True,  # 시행령 포함
        save_to_vectorstore: bool = True,
    ) -> Dict[str, int]:
        """
        노동 관련 법령 전체 수집

        Args:
            include_enforcement: 시행령/시행규칙 포함 여부
            save_to_vectorstore: 벡터스토어에 저장 여부
        """
        collected = {"primary": 0, "secondary": 0, "total_articles": 0}
        all_documents = {"primary": [], "secondary": []}

        for law_name in self.LABOR_LAWS:
            print(f"Collecting: {law_name}")

            # 법령 검색
            laws = await self.search_laws(law_name)

            for law in laws:
                if not law.get("law_name"):
                    continue

                # 정확한 법령명 매칭
                if law_name not in law["law_name"]:
                    continue

                # 법령 유형 확인
                law_type = law.get("law_type", "")
                collection_type = self.LAW_TYPE_MAP.get(law_type, "primary")

                if collection_type == "secondary" and not include_enforcement:
                    continue

                # 상세 조문 수집
                detail = await self.get_law_detail(law["law_id"])

                if detail and detail.get("articles"):
                    for article in detail["articles"]:
                        # Document 생성
                        content = self._format_article(
                            law_name=detail["law_name"],
                            article_no=article.get("article_no", ""),
                            article_title=article.get("article_title", ""),
                            content=article.get("content", ""),
                        )

                        doc = Document(
                            page_content=content,
                            metadata={
                                "source": detail["law_name"],
                                "article": article.get("article_no", ""),
                                "article_title": article.get("article_title", ""),
                                "law_type": law_type,
                                "layer": collection_type,
                                "enforcement_date": detail.get("enforcement_date", ""),
                                "ministry": detail.get("ministry", ""),
                                "law_id": detail["law_id"],
                            }
                        )

                        all_documents[collection_type].append(doc)
                        collected["total_articles"] += 1

                # API 부하 방지
                await asyncio.sleep(0.5)

        # 벡터스토어에 저장
        if save_to_vectorstore:
            if all_documents["primary"]:
                self.vs_manager.add_documents("laws_primary", all_documents["primary"])
                collected["primary"] = len(all_documents["primary"])
                print(f"Saved {collected['primary']} primary documents")

            if all_documents["secondary"]:
                self.vs_manager.add_documents("laws_secondary", all_documents["secondary"])
                collected["secondary"] = len(all_documents["secondary"])
                print(f"Saved {collected['secondary']} secondary documents")

        return collected

    def _format_article(
        self,
        law_name: str,
        article_no: str,
        article_title: str,
        content: str,
    ) -> str:
        """조문 포맷팅"""
        parts = [f"{law_name} {article_no}"]

        if article_title:
            parts[0] += f" ({article_title})"

        parts.append(content)

        return "\n".join(parts)

    async def collect_specific_law(
        self,
        law_name: str,
        collection: str = "laws_primary",
    ) -> int:
        """
        특정 법령만 수집

        Args:
            law_name: 법령명
            collection: 저장할 컬렉션
        """
        laws = await self.search_laws(law_name)

        if not laws:
            print(f"Law not found: {law_name}")
            return 0

        # 가장 관련성 높은 법령 선택
        target_law = None
        for law in laws:
            if law.get("law_name") and law_name in law["law_name"]:
                if law.get("law_type") == "법률":
                    target_law = law
                    break
                elif target_law is None:
                    target_law = law

        if not target_law:
            target_law = laws[0]

        detail = await self.get_law_detail(target_law["law_id"])

        if not detail or not detail.get("articles"):
            return 0

        documents = []
        for article in detail["articles"]:
            content = self._format_article(
                law_name=detail["law_name"],
                article_no=article.get("article_no", ""),
                article_title=article.get("article_title", ""),
                content=article.get("content", ""),
            )

            doc = Document(
                page_content=content,
                metadata={
                    "source": detail["law_name"],
                    "article": article.get("article_no", ""),
                    "article_title": article.get("article_title", ""),
                    "law_type": target_law.get("law_type", ""),
                    "layer": "primary" if collection == "laws_primary" else "secondary",
                    "enforcement_date": detail.get("enforcement_date", ""),
                    "law_id": detail["law_id"],
                }
            )
            documents.append(doc)

        if documents:
            self.vs_manager.add_documents(collection, documents)

        return len(documents)


class LawCollectorFallback:
    """
    법령 수집기 (Fallback - 웹 크롤링)

    API 키가 없거나 API 장애 시 사용
    국가법령정보센터 웹페이지 크롤링
    """

    BASE_URL = "https://www.law.go.kr"

    # 주요 노동법령 직접 링크
    DIRECT_LINKS = {
        "근로기준법": "/법령/근로기준법",
        "최저임금법": "/법령/최저임금법",
        "근로자퇴직급여보장법": "/법령/근로자퇴직급여보장법",
        "고용보험법": "/법령/고용보험법",
        "국민연금법": "/법령/국민연금법",
        "국민건강보험법": "/법령/국민건강보험법",
        "산업재해보상보험법": "/법령/산업재해보상보험법",
    }

    def __init__(self):
        self.vs_manager = get_vectorstore_manager()

    async def collect_from_web(
        self,
        law_name: str,
        collection: str = "laws_primary",
    ) -> int:
        """웹 크롤링으로 법령 수집"""
        from bs4 import BeautifulSoup

        url = f"{self.BASE_URL}{self.DIRECT_LINKS.get(law_name, f'/법령/{law_name}')}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # 조문 추출 (사이트 구조에 따라 조정 필요)
                articles = soup.select('.law_article, .lawcon, .jo')

                documents = []
                for article in articles:
                    content = article.get_text(strip=True)
                    if content and len(content) > 20:
                        doc = Document(
                            page_content=f"{law_name}\n{content}",
                            metadata={
                                "source": law_name,
                                "layer": "primary",
                            }
                        )
                        documents.append(doc)

                if documents:
                    self.vs_manager.add_documents(collection, documents)

                return len(documents)

            except Exception as e:
                print(f"Web crawling error for {law_name}: {e}")
                return 0


# 편의 함수
async def collect_all_labor_laws(api_key: Optional[str] = None) -> Dict[str, int]:
    """모든 노동 관련 법령 수집"""
    collector = LawCollector(api_key=api_key)
    return await collector.collect_labor_laws()


async def collect_law(law_name: str, api_key: Optional[str] = None) -> int:
    """특정 법령 수집"""
    collector = LawCollector(api_key=api_key)
    return await collector.collect_specific_law(law_name)
