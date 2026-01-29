"""VectorDB 및 청킹 전략 설정 모듈.

이 모듈은 Bizi RAG 시스템의 벡터 데이터베이스 설정을 관리합니다.
ChromaDB를 사용하여 하나의 데이터베이스에 여러 컬렉션(테이블)을 저장합니다.

컬렉션 구성:
    - startup_funding_db: 창업/지원사업/마케팅 데이터
    - finance_tax_db: 재무/세무 데이터
    - hr_labor_db: 인사/노무 데이터
    - law_common_db: 법령/법령해석 데이터 (공통)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# 기본 경로 설정
BASE_DIR = Path(__file__).parent.parent.parent
DATA_PREPROCESSED_DIR = BASE_DIR / "data" / "preprocessed"
VECTORDB_DIR = Path(__file__).parent.parent / "vectordb"

# 컬렉션(테이블) 이름 매핑
# 하나의 ChromaDB 안에 여러 컬렉션으로 저장됨
COLLECTION_NAMES = {
    "startup_funding": "startup_funding_db",
    "finance_tax": "finance_tax_db",
    "hr_labor": "hr_labor_db",
    "law_common": "law_common_db",
}

# 데이터 소스 경로 매핑
DATA_SOURCES = {
    "startup_funding": DATA_PREPROCESSED_DIR / "startup_support",
    "finance_tax": DATA_PREPROCESSED_DIR / "finance",
    "hr_labor": DATA_PREPROCESSED_DIR / "labor",
    "law_common": DATA_PREPROCESSED_DIR / "law",
}


@dataclass
class ChunkingConfig:
    """텍스트 청킹 설정 클래스.

    긴 텍스트를 임베딩에 적합한 크기로 분할하기 위한 설정입니다.
    RecursiveCharacterTextSplitter를 사용합니다.

    Attributes:
        chunk_size: 청크의 최대 문자 수
        chunk_overlap: 청크 간 겹치는 문자 수 (문맥 유지용)
        separators: 텍스트 분할에 사용할 구분자 목록 (우선순위 순)
    """

    chunk_size: int = 800
    chunk_overlap: int = 100
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", ".", " "])

    # 청킹하지 않을 파일 목록
    NO_CHUNK_FILES: list[str] = field(default_factory=lambda: [
        "announcements.jsonl",
        "industry_startup_guide_filtered.jsonl",
    ])

    # 조건부 청킹 파일 목록 (콘텐츠 크기에 따라 결정)
    OPTIONAL_CHUNK_FILES: list[str] = field(default_factory=lambda: [
        "startup_procedures_filtered.jsonl",
        "laws_full.jsonl",
        "interpretations.jsonl",
        "labor_interpretation.jsonl",
        "hr_major_insurance.jsonl"
    ])

    # 필수 청킹 파일 목록
    CHUNK_FILES: list[str] = field(default_factory=lambda: [
        "court_cases_tax.jsonl",
        "extracted_documents_final.jsonl",
        "court_cases_labor.jsonl",
    ])


@dataclass
class VectorDBConfig:
    """VectorDB 설정 클래스.

    ChromaDB 벡터 데이터베이스의 설정을 관리합니다.
    하나의 persist_directory에 여러 컬렉션(테이블)을 저장합니다.

    Attributes:
        embedding_model: OpenAI 임베딩 모델 이름
        persist_directory: ChromaDB 데이터 저장 경로
        collection_metadata: 컬렉션 메타데이터 (유사도 측정 방식 등)
        batch_size: 임베딩 배치 크기
    """

    # 임베딩 모델 설정
    embedding_model: str = "text-embedding-3-small"

    # ChromaDB 저장 경로 (하나의 디렉토리에 모든 컬렉션 저장)
    persist_directory: Path = field(default_factory=lambda: VECTORDB_DIR)

    # 컬렉션 메타데이터 설정
    collection_metadata: dict = field(default_factory=lambda: {
        "hnsw:space": "cosine",  # 코사인 유사도 사용
    })

    # 임베딩 배치 크기
    batch_size: int = 100

    @property
    def openai_api_key(self) -> str:
        """환경변수에서 OpenAI API 키를 가져옵니다.

        Returns:
            OpenAI API 키 문자열

        Raises:
            ValueError: OPENAI_API_KEY 환경변수가 설정되지 않은 경우
        """
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        return key


# 파일별 컬렉션 매핑
FILE_TO_COLLECTION_MAPPING = {
    # startup_funding_db 컬렉션
    "announcements.jsonl": "startup_funding",
    "industry_startup_guide_filtered.jsonl": "startup_funding",
    "startup_procedures_filtered.jsonl": "startup_funding",

    # finance_tax_db 컬렉션
    "court_cases_tax.jsonl": "finance_tax",
    "extracted_documents_final.jsonl": "finance_tax",

    # hr_labor_db 컬렉션
    "court_cases_labor.jsonl": "hr_labor",
    "labor_interpretation.jsonl": "hr_labor",
    "hr_major_insurance.jsonl": "hr_labor",

    # law_common_db 컬렉션
    "laws_full.jsonl": "law_common",
    "interpretations.jsonl": "law_common",
}

# 파일별 청킹 설정
FILE_CHUNKING_CONFIG = {
    # 청킹 안함
    "announcements.jsonl": None,
    "industry_startup_guide_filtered.jsonl": None,

    # 조건부 청킹 (콘텐츠가 임계값 초과 시 청킹)
    "startup_procedures_filtered.jsonl": ChunkingConfig(chunk_size=1000, chunk_overlap=200),
    "laws_full.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
    "interpretations.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
    "labor_interpretation.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
    "hr_major_insurance.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),

    # 필수 청킹
    "court_cases_tax.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
    "extracted_documents_final.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
    "court_cases_labor.jsonl": ChunkingConfig(chunk_size=800, chunk_overlap=100),
}

# 조건부 청킹 임계값 (문자 수)
OPTIONAL_CHUNK_THRESHOLD = 1500
