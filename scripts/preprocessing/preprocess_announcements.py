"""
지원사업 공고 데이터 전처리 파이프라인

data_pipeline.md 스키마를 따라 bizinfo/kstartup 공고 데이터를
통합 스키마로 변환합니다.

Usage:
    python announcement_preprocessor.py --input <input_dir> --output <output_dir>
    python announcement_preprocessor.py  # 기본 경로 사용
"""

import json
import re
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from html import unescape
import argparse

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================
# 스키마 정의 (data_pipeline.md 참조)
# ============================================================

@dataclass
class Source:
    """데이터 출처 정보"""
    name: str
    url: str
    collected_at: str


@dataclass
class AnnouncementMetadata:
    """공고 메타데이터"""
    organization: str  # 주관기관
    region: str  # 지역
    target_type: str  # 지원대상 유형 (중소기업, 예비창업자 등)
    support_type: str  # 지원유형 (수출, 기술, R&D 등)
    apply_method: str  # 신청방법
    contact: str  # 문의처
    target: str  # 지원대상
    exclusion: str  # 제외대상
    amount: str  # 지원금액
    hashtags: List[str] = field(default_factory=list)
    original_id: str = ""  # 원본 ID
    # 정규화 필드 (ChromaDB 메타데이터 필터링용)
    normalized_region: str = ""
    target_예비창업자: str = "false"
    target_창업기업: str = "false"
    target_중소기업: str = "false"
    target_소상공인: str = "false"
    target_전체: str = "false"


@dataclass
class AnnouncementDocument:
    """
    지원사업 공고 통합 스키마

    data_pipeline.md의 BaseDocument 구조를 따름:
    - id: ANNOUNCE_{SOURCE}_{original_id}
    - type: "startup_funding"
    - domain: "funding"
    """
    id: str
    type: str  # "startup_funding"
    domain: str  # "funding"
    title: str
    content: str  # RAG 검색용 본문 (요약 + 지원대상 + 지원금액 등 통합)
    source: Source
    effective_date: str  # "YYYY-MM-DD ~ YYYY-MM-DD" 형태
    metadata: AnnouncementMetadata

    def to_dict(self) -> Dict[str, Any]:
        """JSONL 출력용 딕셔너리 변환"""
        return {
            "id": self.id,
            "type": self.type,
            "domain": self.domain,
            "title": self.title,
            "content": self.content,
            "source": asdict(self.source),
            "effective_date": self.effective_date,
            "metadata": asdict(self.metadata)
        }


# ============================================================
# 유틸리티 함수
# ============================================================

# ============================================================
# 정규화 매핑 테이블 (메타데이터 필터링용)
# ============================================================

# 시도 17개 정규화 매핑
REGION_NORMALIZATION: Dict[str, str] = {
    # 약칭 → 정식명칭
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
    "강원": "강원특별자치도",
    "전북": "전북특별자치도",
    # 정식명칭 → 정식명칭 (idempotent)
    "서울특별시": "서울특별시",
    "부산광역시": "부산광역시",
    "대구광역시": "대구광역시",
    "인천광역시": "인천광역시",
    "광주광역시": "광주광역시",
    "대전광역시": "대전광역시",
    "울산광역시": "울산광역시",
    "세종특별자치시": "세종특별자치시",
    "경기도": "경기도",
    "충청북도": "충청북도",
    "충청남도": "충청남도",
    "전라남도": "전라남도",
    "경상북도": "경상북도",
    "경상남도": "경상남도",
    "제주특별자치도": "제주특별자치도",
    "강원특별자치도": "강원특별자치도",
    "전북특별자치도": "전북특별자치도",
    # 레거시 명칭
    "전라북도": "전북특별자치도",
    "강원도": "강원특별자치도",
}

# 부분 매칭용 키 (긴 키 우선 정렬)
_REGION_KEYS_BY_LENGTH = sorted(REGION_NORMALIZATION.keys(), key=len, reverse=True)

# 대상 유형 키워드 → 태그 매핑
TARGET_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "target_예비창업자": ["예비창업자", "예비 창업자", "예비창업"],
    "target_창업기업": ["창업기업", "초기창업", "창업초기", "신규창업", "창업 기업"],
    "target_중소기업": ["중소기업", "중견기업", "중소 기업"],
    "target_소상공인": ["소상공인", "소기업", "소규모"],
}

ALL_TARGET_FLAGS = [
    "target_예비창업자",
    "target_창업기업",
    "target_중소기업",
    "target_소상공인",
    "target_전체",
]


def normalize_region(raw: str) -> str:
    """지역 문자열을 시도 17개 정규화 값으로 변환합니다.

    Args:
        raw: 원본 지역 문자열 (예: "서울", "서울특별시 강남구", "전국")

    Returns:
        정규화된 시도명 또는 "" (전국/미매칭)
    """
    if not raw:
        return ""

    raw = raw.strip()

    # "전국" 또는 "전 지역" → 빈 문자열 (필터 제외 = 전국 공고)
    if raw in ("전국", "전 지역", "전지역", "전체", "해당없음"):
        return ""

    # 1. 정확 매칭
    if raw in REGION_NORMALIZATION:
        return REGION_NORMALIZATION[raw]

    # 2. 부분 문자열 매칭 (긴 키 우선)
    for key in _REGION_KEYS_BY_LENGTH:
        if key in raw:
            return REGION_NORMALIZATION[key]

    return ""


def get_target_type_flags(target_type: str) -> Dict[str, str]:
    """대상 유형 문자열을 Boolean 플래그 딕셔너리로 변환합니다.

    ChromaDB가 $contains 미지원이므로, 콤마 구분 대신 개별 Boolean 필드로 저장합니다.

    Args:
        target_type: 원본 대상 유형 문자열 (예: "중소기업, 예비창업자")

    Returns:
        {"target_예비창업자": "true"/"false", ...} 딕셔너리
    """
    flags = {flag: "false" for flag in ALL_TARGET_FLAGS}

    if not target_type:
        flags["target_전체"] = "true"
        return flags

    matched = False
    for flag_key, keywords in TARGET_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in target_type:
                flags[flag_key] = "true"
                matched = True
                break

    # 매칭 없으면 전체 대상으로 간주
    if not matched:
        flags["target_전체"] = "true"

    return flags


def remove_html_tags(text: str) -> str:
    """HTML 태그 제거 및 엔티티 디코딩"""
    if not text:
        return ""

    # HTML 엔티티 디코딩
    text = unescape(text)

    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)

    # 연속 공백/줄바꿈 정리
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def parse_date(date_str: str) -> Optional[str]:
    """
    다양한 날짜 형식을 YYYY-MM-DD로 변환

    지원 형식:
    - "20260120"
    - "2026-01-20"
    - "2026.01.20"
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # 이미 YYYY-MM-DD 형식
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    # YYYYMMDD 형식
    if re.match(r'^\d{8}$', date_str):
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    # YYYY.MM.DD 형식
    if re.match(r'^\d{4}\.\d{2}\.\d{2}$', date_str):
        return date_str.replace('.', '-')

    return None


def parse_date_range(date_range: str) -> tuple[Optional[str], Optional[str]]:
    """
    날짜 범위 문자열 파싱

    예: "20260120 ~ 20260210" -> ("2026-01-20", "2026-02-10")
    """
    if not date_range:
        return None, None

    # ~ 또는 - 로 분리
    parts = re.split(r'\s*[~\-]\s*', date_range)

    if len(parts) == 2:
        return parse_date(parts[0]), parse_date(parts[1])
    elif len(parts) == 1:
        return parse_date(parts[0]), None

    return None, None


def clean_value(value: Any) -> str:
    """값 정제 - "정보 없음" 처리 및 공백 정리"""
    if value is None:
        return ""

    value = str(value).strip()

    # "정보 없음" 변환
    if value in ["정보 없음", "정보없음", "없음", "-", "N/A", "n/a"]:
        return ""

    return value


def generate_content_hash(title: str, org: str) -> str:
    """중복 체크용 해시 생성"""
    content = f"{title}|{org}".lower()
    return hashlib.md5(content.encode()).hexdigest()[:12]


def build_rag_content(doc: Dict[str, Any], source: str) -> str:
    """
    RAG 검색용 통합 본문 생성

    공고명, 요약, 지원대상, 제외대상, 지원금액을 하나의 텍스트로 통합
    """
    parts = []

    # 공고명
    title = doc.get("title", "")
    if title:
        parts.append(f"[공고명] {title}")

    # 요약
    if source == "bizinfo":
        summary = remove_html_tags(doc.get("bsnsSumryCn", ""))
    else:  # kstartup
        summary = clean_value(doc.get("pbanc_ctnt", ""))

    if summary:
        parts.append(f"[요약] {summary}")

    # 지원대상
    target = clean_value(doc.get("지원대상", ""))
    if target:
        parts.append(f"[지원대상] {target}")

    # 제외대상
    exclusion = clean_value(doc.get("제외대상", ""))
    if exclusion:
        parts.append(f"[제외대상] {exclusion}")

    # 지원금액
    amount = clean_value(doc.get("지원금액", ""))
    if amount:
        parts.append(f"[지원금액] {amount}")

    return "\n\n".join(parts)


# ============================================================
# 프로세서 클래스
# ============================================================

class BizinfoProcessor:
    """기업마당 공고 처리"""

    def process(self, raw_data: Dict[str, Any]) -> List[AnnouncementDocument]:
        """원본 데이터를 통합 스키마로 변환"""
        documents = []
        data_list = raw_data.get("data", [])

        for item in data_list:
            try:
                doc = self._process_item(item)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"bizinfo 항목 처리 실패: {e}")
                continue

        return documents

    def _process_item(self, item: Dict[str, Any]) -> Optional[AnnouncementDocument]:
        """개별 항목 처리"""
        original_id = item.get("pblancId", item.get("id", ""))
        if not original_id:
            return None

        # ID 생성
        doc_id = f"ANNOUNCE_BIZINFO_{original_id}"

        # 제목
        title = clean_value(item.get("pblancNm", ""))
        if not title:
            return None

        # 날짜 파싱
        date_range = item.get("reqstBeginEndDe", "")
        apply_start, apply_end = parse_date_range(date_range)

        # 지역 추출 (제목에서 [지역] 패턴)
        region = ""
        region_match = re.search(r'\[([^\]]+)\]', title)
        if region_match:
            region = region_match.group(1)
        if not region:
            region = clean_value(item.get("jrsdInsttNm", ""))

        # 해시태그 파싱
        hashtags_str = item.get("hashtags", "")
        hashtags = [h.strip() for h in hashtags_str.split(",") if h.strip()]

        # URL 생성
        pbanc_url = item.get("pblancUrl", "")
        if pbanc_url and not pbanc_url.startswith("http"):
            pbanc_url = f"https://www.bizinfo.go.kr{pbanc_url}"

        # Source 객체
        source = Source(
            name="기업마당",
            url=pbanc_url,
            collected_at=item.get("creatPnttm", datetime.now().isoformat())
        )

        # target, exclusion, amount 추출
        target = clean_value(item.get("지원대상", ""))
        exclusion = clean_value(item.get("제외대상", ""))
        amount = clean_value(item.get("지원금액", ""))

        # 정규화 처리
        target_type_raw = clean_value(item.get("trgetNm", ""))
        normalized_region = normalize_region(region)
        target_flags = get_target_type_flags(target_type_raw)

        # Metadata 객체 (target, exclusion, amount 포함)
        metadata = AnnouncementMetadata(
            organization=clean_value(item.get("excInsttNm", "")),
            region=region,
            target_type=target_type_raw,
            support_type=clean_value(item.get("pldirSportRealmLclasCodeNm", "")),
            apply_method=clean_value(item.get("reqstMthPapersCn", "")),
            contact=clean_value(item.get("refrncNm", "")),
            target=target,
            exclusion=exclusion,
            amount=amount,
            hashtags=hashtags,
            original_id=original_id,
            normalized_region=normalized_region,
            **target_flags,
        )

        # effective_date 생성: "YYYY-MM-DD ~ YYYY-MM-DD" 형태
        start_str = apply_start if apply_start else ""
        end_str = apply_end if apply_end else ""
        if start_str and end_str:
            effective_date = f"{start_str} ~ {end_str}"
        elif start_str:
            effective_date = f"{start_str} ~"
        elif end_str:
            effective_date = f"~ {end_str}"
        else:
            effective_date = ""

        # RAG 검색용 본문
        item["title"] = title
        content = build_rag_content(item, "bizinfo")

        return AnnouncementDocument(
            id=doc_id,
            type="startup_funding",
            domain="funding",
            title=title,
            content=content,
            source=source,
            effective_date=effective_date,
            metadata=metadata
        )


class KstartupProcessor:
    """K-Startup 공고 처리"""

    def process(self, raw_data: Dict[str, Any]) -> List[AnnouncementDocument]:
        """원본 데이터를 통합 스키마로 변환"""
        documents = []
        data_list = raw_data.get("data", [])

        for item in data_list:
            try:
                doc = self._process_item(item)
                if doc:
                    documents.append(doc)
            except Exception as e:
                logger.warning(f"kstartup 항목 처리 실패: {e}")
                continue

        return documents

    def _process_item(self, item: Dict[str, Any]) -> Optional[AnnouncementDocument]:
        """개별 항목 처리"""
        original_id = item.get("pbanc_sn", item.get("id", ""))
        if not original_id:
            return None

        # ID 생성
        doc_id = f"ANNOUNCE_KSTARTUP_{original_id}"

        # 제목
        title = clean_value(item.get("biz_pbanc_nm", item.get("intg_pbanc_biz_nm", "")))
        if not title:
            return None

        # 날짜 파싱
        apply_start = parse_date(item.get("pbanc_rcpt_bgng_dt", ""))
        apply_end = parse_date(item.get("pbanc_rcpt_end_dt", ""))

        # 지역
        region = clean_value(item.get("supt_regin", ""))

        # URL
        detail_url = item.get("detl_pg_url", "")
        if not detail_url:
            detail_url = f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={original_id}"

        # Source 객체
        source = Source(
            name="K-Startup",
            url=detail_url,
            collected_at=datetime.now().isoformat()
        )

        # 신청방법 통합
        apply_methods = []
        if item.get("aply_mthd_onli_rcpt_istc"):
            apply_methods.append(f"온라인: {item.get('aply_mthd_onli_rcpt_istc')}")
        if item.get("aply_mthd_vst_rcpt_istc"):
            apply_methods.append(f"방문: {item.get('aply_mthd_vst_rcpt_istc')}")
        if item.get("aply_mthd_eml_rcpt_istc"):
            apply_methods.append(f"이메일: {item.get('aply_mthd_eml_rcpt_istc')}")

        # target, exclusion, amount 추출
        target = clean_value(item.get("지원대상", item.get("aply_trgt_ctnt", "")))
        exclusion = clean_value(item.get("제외대상", item.get("aply_excl_trgt_ctnt", "")))
        amount = clean_value(item.get("지원금액", ""))

        # 정규화 처리
        target_type_raw = clean_value(item.get("aply_trgt", ""))
        normalized_region = normalize_region(region)
        target_flags = get_target_type_flags(target_type_raw)

        # Metadata 객체 (target, exclusion, amount 포함)
        metadata = AnnouncementMetadata(
            organization=clean_value(item.get("pbanc_ntrp_nm", "")),
            region=region,
            target_type=target_type_raw,
            support_type=clean_value(item.get("supt_biz_clsfc", "")),
            apply_method=" / ".join(apply_methods) if apply_methods else "",
            contact=clean_value(item.get("prch_cnpl_no", "")),
            target=target,
            exclusion=exclusion,
            amount=amount,
            hashtags=[],
            original_id=str(original_id),
            normalized_region=normalized_region,
            **target_flags,
        )

        # effective_date 생성: "YYYY-MM-DD ~ YYYY-MM-DD" 형태
        start_str = apply_start if apply_start else ""
        end_str = apply_end if apply_end else ""
        if start_str and end_str:
            effective_date = f"{start_str} ~ {end_str}"
        elif start_str:
            effective_date = f"{start_str} ~"
        elif end_str:
            effective_date = f"~ {end_str}"
        else:
            effective_date = ""

        # RAG 검색용 본문
        item["title"] = title
        content = build_rag_content(item, "kstartup")

        return AnnouncementDocument(
            id=doc_id,
            type="startup_funding",
            domain="funding",
            title=title,
            content=content,
            source=source,
            effective_date=effective_date,
            metadata=metadata
        )


# ============================================================
# 파이프라인 메인 클래스
# ============================================================

class AnnouncementPreprocessor:
    """지원사업 공고 전처리 파이프라인"""

    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.bizinfo_processor = BizinfoProcessor()
        self.kstartup_processor = KstartupProcessor()

        # 중복 체크용
        self.seen_hashes: set = set()

        # 통계
        self.stats = {
            "bizinfo_total": 0,
            "bizinfo_processed": 0,
            "kstartup_total": 0,
            "kstartup_processed": 0,
            "duplicates_removed": 0
        }

    def run(self) -> Dict[str, Any]:
        """전처리 파이프라인 실행"""
        logger.info("=" * 60)
        logger.info("지원사업 공고 전처리 시작")
        logger.info("=" * 60)

        all_documents: List[AnnouncementDocument] = []

        # 1. Bizinfo 처리
        bizinfo_files = list(self.input_dir.glob("bizinfo_*.json"))
        for file_path in bizinfo_files:
            logger.info(f"처리 중: {file_path.name}")
            docs = self._process_bizinfo(file_path)
            all_documents.extend(docs)

        # 2. K-Startup 처리
        kstartup_files = list(self.input_dir.glob("kstartup_*.json"))
        for file_path in kstartup_files:
            logger.info(f"처리 중: {file_path.name}")
            docs = self._process_kstartup(file_path)
            all_documents.extend(docs)

        # 3. 중복 제거
        unique_documents = self._remove_duplicates(all_documents)

        # 4. JSONL 출력
        output_path = self.output_dir / "announcements.jsonl"
        self._write_jsonl(unique_documents, output_path)

        # 5. 통계 JSON 출력
        stats_path = self.output_dir / "preprocessing_stats.json"
        self._write_stats(stats_path)

        # 6. 결과 출력
        self._print_summary()

        return self.stats

    def _process_bizinfo(self, file_path: Path) -> List[AnnouncementDocument]:
        """Bizinfo 파일 처리"""
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        self.stats["bizinfo_total"] = raw_data.get("total_count", 0)
        documents = self.bizinfo_processor.process(raw_data)
        self.stats["bizinfo_processed"] = len(documents)

        logger.info(f"  Bizinfo: {len(documents)}건 처리됨")
        return documents

    def _process_kstartup(self, file_path: Path) -> List[AnnouncementDocument]:
        """K-Startup 파일 처리"""
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        self.stats["kstartup_total"] = raw_data.get("total_count", 0)
        documents = self.kstartup_processor.process(raw_data)
        self.stats["kstartup_processed"] = len(documents)

        logger.info(f"  K-Startup: {len(documents)}건 처리됨")
        return documents

    def _remove_duplicates(self, documents: List[AnnouncementDocument]) -> List[AnnouncementDocument]:
        """
        중복 공고 제거

        같은 제목 + 주관기관 조합은 중복으로 판단
        """
        unique_docs = []

        for doc in documents:
            content_hash = generate_content_hash(
                doc.title,
                doc.metadata.organization
            )

            if content_hash not in self.seen_hashes:
                self.seen_hashes.add(content_hash)
                unique_docs.append(doc)
            else:
                self.stats["duplicates_removed"] += 1

        logger.info(f"중복 제거: {self.stats['duplicates_removed']}건")
        return unique_docs

    def _write_jsonl(self, documents: List[AnnouncementDocument], output_path: Path):
        """JSONL 형식으로 출력"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in documents:
                json_line = json.dumps(doc.to_dict(), ensure_ascii=False)
                f.write(json_line + '\n')

        logger.info(f"출력 완료: {output_path}")
        logger.info(f"  총 {len(documents)}건 저장됨")

    def _write_stats(self, stats_path: Path):
        """통계 정보 저장"""
        stats_output = {
            **self.stats,
            "total_processed": (
                self.stats["bizinfo_processed"] +
                self.stats["kstartup_processed"] -
                self.stats["duplicates_removed"]
            ),
            "processed_at": datetime.now().isoformat()
        }

        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats_output, f, ensure_ascii=False, indent=2)

        logger.info(f"통계 저장: {stats_path}")

    def _print_summary(self):
        """결과 요약 출력"""
        total = (
            self.stats["bizinfo_processed"] +
            self.stats["kstartup_processed"] -
            self.stats["duplicates_removed"]
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("전처리 완료!")
        logger.info("=" * 60)
        logger.info(f"  기업마당: {self.stats['bizinfo_processed']}/{self.stats['bizinfo_total']}건")
        logger.info(f"  K-Startup: {self.stats['kstartup_processed']}/{self.stats['kstartup_total']}건")
        logger.info(f"  중복 제거: {self.stats['duplicates_removed']}건")
        logger.info(f"  최종 출력: {total}건")
        logger.info("=" * 60)


# ============================================================
# CLI 진입점
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="지원사업 공고 데이터 전처리 파이프라인"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data",
        help="입력 디렉토리 (기본: test/data)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(__file__).parent.parent.parent / "data" / "processed",
        help="출력 디렉토리 (기본: test/data/processed)"
    )

    args = parser.parse_args()

    preprocessor = AnnouncementPreprocessor(
        input_dir=args.input,
        output_dir=args.output
    )

    preprocessor.run()


if __name__ == "__main__":
    main()
