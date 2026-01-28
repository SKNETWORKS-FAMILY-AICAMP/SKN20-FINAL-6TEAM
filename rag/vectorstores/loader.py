"""VectorDB용 데이터 로더 모듈.

이 모듈은 전처리된 JSONL 데이터를 로드하고 LangChain Document로 변환합니다.
파일별 청킹 전략에 따라 텍스트를 분할하여 벡터DB에 저장할 수 있도록 합니다.

주요 기능:
    - JSONL 파일 파싱 및 Document 생성
    - 파일별 맞춤 청킹 전략 적용
    - 도메인별 데이터 로드
"""

import json
from pathlib import Path
from typing import Any, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from .config import (
    ChunkingConfig,
    DATA_SOURCES,
    FILE_CHUNKING_CONFIG,
    FILE_TO_COLLECTION_MAPPING,
    OPTIONAL_CHUNK_THRESHOLD,
)


class DataLoader:
    """VectorDB용 데이터 로더 클래스.

    전처리된 JSONL 파일을 읽어 LangChain Document로 변환합니다.
    파일별로 다른 청킹 전략을 적용하여 최적의 검색 성능을 보장합니다.

    Attributes:
        _splitters: 청킹 설정별 텍스트 분할기 캐시

    Example:
        >>> loader = DataLoader()
        >>> for doc in loader.load_db_documents("startup_funding"):
        ...     print(doc.page_content[:100])
    """

    def __init__(self):
        """DataLoader를 초기화합니다."""
        self._splitters: dict[str, RecursiveCharacterTextSplitter] = {}

    def _get_splitter(self, config: ChunkingConfig) -> RecursiveCharacterTextSplitter:
        """청킹 설정에 맞는 텍스트 분할기를 가져오거나 생성합니다.

        Args:
            config: 청킹 설정 객체

        Returns:
            RecursiveCharacterTextSplitter 인스턴스
        """
        key = f"{config.chunk_size}_{config.chunk_overlap}"
        if key not in self._splitters:
            self._splitters[key] = RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                separators=config.separators,
                length_function=len,
            )
        return self._splitters[key]

    def _parse_jsonl_line(self, line: str) -> dict[str, Any] | None:
        """JSONL 한 줄을 파싱합니다.

        Args:
            line: JSON 문자열 한 줄

        Returns:
            파싱된 딕셔너리 또는 유효하지 않으면 None
        """
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _create_document(
        self,
        data: dict[str, Any],
        file_name: str,
        chunk_index: int | None = None,
    ) -> Document:
        """데이터로부터 LangChain Document를 생성합니다.

        Args:
            data: 문서 데이터 딕셔너리
            file_name: 원본 파일 이름
            chunk_index: 청킹된 경우 청크 인덱스

        Returns:
            LangChain Document 인스턴스
        """
        # Build metadata
        metadata = {
            "id": data.get("id", ""),
            "type": data.get("type", ""),
            "domain": data.get("domain", ""),
            "title": data.get("title", ""),
            "source_file": file_name,
        }

        # Add source info if available
        source_info = data.get("source", {})
        if isinstance(source_info, dict):
            metadata["source_name"] = source_info.get("name", "")
            metadata["source_url"] = source_info.get("url", "")
            metadata["collected_at"] = source_info.get("collected_at", "")

        # Add effective date if available
        if "effective_date" in data:
            metadata["effective_date"] = data["effective_date"]

        # Add chunk index if chunked
        if chunk_index is not None:
            metadata["chunk_index"] = chunk_index
            metadata["original_id"] = data.get("id", "")
            metadata["id"] = f"{data.get('id', '')}_{chunk_index}"

        # Add additional metadata fields
        extra_metadata = data.get("metadata", {})
        if isinstance(extra_metadata, dict):
            for key, value in extra_metadata.items():
                if key not in metadata and isinstance(value, (str, int, float, bool)):
                    metadata[f"meta_{key}"] = value

        # Content is the main text
        content = data.get("content", "")

        return Document(page_content=content, metadata=metadata)

    def _should_chunk(
        self,
        content: str,
        file_name: str,
        config: ChunkingConfig | None,
    ) -> bool:
        """콘텐츠를 청킹해야 하는지 결정합니다.

        파일 유형과 콘텐츠 크기에 따라 청킹 여부를 결정합니다.
        - NO_CHUNK_FILES: 청킹하지 않음
        - OPTIONAL_CHUNK_FILES: 임계값 초과 시에만 청킹
        - CHUNK_FILES: 항상 청킹

        Args:
            content: 텍스트 콘텐츠
            file_name: 원본 파일 이름
            config: 청킹 설정 객체

        Returns:
            청킹해야 하면 True, 아니면 False
        """
        if config is None:
            return False

        # Check if file is in optional chunk list
        chunk_config = ChunkingConfig()
        if file_name in chunk_config.NO_CHUNK_FILES:
            return False

        if file_name in chunk_config.OPTIONAL_CHUNK_FILES:
            return len(content) > OPTIONAL_CHUNK_THRESHOLD

        if file_name in chunk_config.CHUNK_FILES:
            return True

        return False

    def load_file(self, file_path: Path) -> Iterator[Document]:
        """파일에서 문서를 로드합니다.

        JSONL 파일을 읽어 각 줄을 Document로 변환합니다.
        파일별 청킹 설정에 따라 텍스트를 분할할 수 있습니다.

        Args:
            file_path: 파일 경로

        Yields:
            LangChain Document 인스턴스
        """
        file_name = file_path.name
        chunk_config = FILE_CHUNKING_CONFIG.get(file_name)

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                data = self._parse_jsonl_line(line)
                if data is None:
                    continue

                content = data.get("content", "")

                # Check if we should chunk this content
                if self._should_chunk(content, file_name, chunk_config):
                    splitter = self._get_splitter(chunk_config)
                    chunks = splitter.split_text(content)

                    for i, chunk in enumerate(chunks):
                        chunk_data = data.copy()
                        chunk_data["content"] = chunk
                        yield self._create_document(chunk_data, file_name, chunk_index=i)
                else:
                    yield self._create_document(data, file_name)

    def load_db_documents(self, domain: str) -> Iterator[Document]:
        """특정 도메인의 모든 문서를 로드합니다.

        도메인에 매핑된 모든 데이터 파일을 읽어 Document로 변환합니다.

        Args:
            domain: 도메인 키 (startup_funding, finance_tax, hr_labor, law_common)

        Yields:
            LangChain Document 인스턴스

        Raises:
            ValueError: 유효하지 않은 도메인이거나 소스 디렉토리가 없는 경우
        """
        source_dir = DATA_SOURCES.get(domain)
        if source_dir is None or not source_dir.exists():
            raise ValueError(f"유효하지 않은 도메인이거나 소스 디렉토리가 없습니다: {domain}")

        # 도메인에 해당하는 모든 파일 찾기
        for file_name, target_domain in FILE_TO_COLLECTION_MAPPING.items():
            if target_domain != domain:
                continue

            file_path = source_dir / file_name
            if not file_path.exists():
                # Check other directories
                for _, other_dir in DATA_SOURCES.items():
                    alt_path = other_dir / file_name
                    if alt_path.exists():
                        file_path = alt_path
                        break

            if file_path.exists():
                print(f"Loading {file_name}...")
                yield from self.load_file(file_path)

    def get_file_stats(self, domain: str) -> dict[str, int]:
        """도메인의 파일별 문서 수 통계를 반환합니다.

        Args:
            domain: 도메인 키

        Returns:
            파일 이름별 문서 수 딕셔너리
        """
        stats = {}
        source_dir = DATA_SOURCES.get(domain)

        if source_dir is None or not source_dir.exists():
            return stats

        for file_name, target_domain in FILE_TO_COLLECTION_MAPPING.items():
            if target_domain != domain:
                continue

            file_path = source_dir / file_name
            if not file_path.exists():
                for _, other_dir in DATA_SOURCES.items():
                    alt_path = other_dir / file_name
                    if alt_path.exists():
                        file_path = alt_path
                        break

            if file_path.exists():
                count = sum(1 for doc in self.load_file(file_path))
                stats[file_name] = count

        return stats
