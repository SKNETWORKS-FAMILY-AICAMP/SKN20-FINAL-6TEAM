"""VectorDB용 데이터 로더 모듈.

이 모듈은 전처리된 JSONL 데이터를 로드하고 LangChain Document로 변환합니다.
파일별 청킹 전략에 따라 텍스트를 분할하여 벡터DB에 저장할 수 있도록 합니다.

주요 기능:
    - JSONL 파일 파싱 및 Document 생성
    - 파일별 맞춤 청킹 전략 적용 (default, table_aware, qa_aware)
    - 도메인별 데이터 로드
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

from vectorstores.config import (
    ANNOUNCEMENT_CHUNKING_CONFIG,
    ANNOUNCEMENT_FULLTEXT_CHUNK_THRESHOLD,
    CHILD_CHUNK_SIZE,
    CHILD_CHUNK_OVERLAP,
    ChunkingConfig,
    DATA_SOURCES,
    FILE_CHUNKING_CONFIG,
    FILE_SOURCE_DIR,
    FILE_TO_COLLECTION_MAPPING,
    OPTIONAL_CHUNK_THRESHOLD,
)
from .contextual_prefix import generate_prefix

# 마크다운 테이블 행 패턴 (| 로 시작하는 행)
_TABLE_ROW_RE = re.compile(r"^\|.*\|$", re.MULTILINE)
# Q&A 패턴 (질의/회시 구분자)
_QA_SPLIT_RE = re.compile(r"(?=질의\s*:)|(?=회시\s*:)")


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

    def _parse_jsonl_line(
        self, line: str, line_num: int = 0, file_name: str = ""
    ) -> dict[str, Any] | None:
        """JSONL 한 줄을 파싱합니다.

        Args:
            line: JSON 문자열 한 줄
            line_num: 줄 번호 (에러 로깅용)
            file_name: 파일 이름 (에러 로깅용)

        Returns:
            파싱된 딕셔너리 또는 유효하지 않으면 None
        """
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning("JSONL 파싱 실패 [%s:%d]: %s", file_name, line_num, e)
            return None

    def _create_document(
        self,
        data: dict[str, Any],
        file_name: str,
        chunk_index: int | None = None,
        child_index: int | None = None,
        collection_domain: str = "",
        chunk_type: str = "standalone",
        parent_id: str = "",
    ) -> Document:
        """데이터로부터 LangChain Document를 생성합니다.

        Args:
            data: 문서 데이터 딕셔너리
            file_name: 원본 파일 이름
            chunk_index: 청킹된 경우 청크 인덱스
            child_index: child 청크인 경우 자식 인덱스
            collection_domain: 적재 대상 컬렉션 도메인 키
            chunk_type: 청크 유형 ("parent", "child", "standalone")
            parent_id: child 청크의 부모 ID

        Returns:
            LangChain Document 인스턴스
        """
        # Build metadata
        metadata = {
            "id": data.get("id", ""),
            "type": data.get("type", ""),
            "domain": data.get("domain", ""),
            "collection": collection_domain,
            "title": data.get("title", ""),
            "source_file": file_name,
            "chunk_type": chunk_type,
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

        # P2-3: ID 및 인덱스 설정 (chunk_type에 따라 분기)
        if chunk_type == "child" and chunk_index is not None and child_index is not None:
            metadata["chunk_index"] = chunk_index
            metadata["child_index"] = child_index
            metadata["original_id"] = data.get("id", "")
            metadata["parent_id"] = parent_id
            metadata["id"] = f"{data.get('id', '')}_{chunk_index}_c{child_index}"
        elif chunk_index is not None:
            metadata["chunk_index"] = chunk_index
            metadata["original_id"] = data.get("id", "")
            metadata["id"] = f"{data.get('id', '')}_{chunk_index}"

        # Add parent_id for child chunks
        if parent_id and "parent_id" not in metadata:
            metadata["parent_id"] = parent_id

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

    def _split_text(self, content: str, config: ChunkingConfig) -> list[str]:
        """splitter_type에 따라 적절한 분할 전략을 적용합니다.

        Args:
            content: 분할할 텍스트
            config: 청킹 설정 (splitter_type 포함)

        Returns:
            분할된 텍스트 청크 리스트
        """
        if config.splitter_type == "table_aware":
            return self._split_with_table_awareness(content, config)
        elif config.splitter_type == "qa_aware":
            return self._split_preserving_qa(content, config)
        else:
            splitter = self._get_splitter(config)
            return splitter.split_text(content)

    def _split_child_text(self, parent_text: str) -> list[str]:
        """부모 청크를 검색용 자식 청크로 분할합니다.

        Parent-Child 검색에서 child는 500자 단위로 분할되어
        정밀한 벡터 검색에 사용됩니다.

        Args:
            parent_text: 부모 청크 텍스트 (prefix 제외 원본)

        Returns:
            자식 청크 리스트. 부모가 CHILD_CHUNK_SIZE 이하이면 [parent_text] 반환.
        """
        if len(parent_text) <= CHILD_CHUNK_SIZE:
            return [parent_text]
        config = ChunkingConfig(
            chunk_size=CHILD_CHUNK_SIZE,
            chunk_overlap=CHILD_CHUNK_OVERLAP,
        )
        splitter = self._get_splitter(config)
        return splitter.split_text(parent_text)

    def _split_with_table_awareness(
        self, content: str, config: ChunkingConfig
    ) -> list[str]:
        """마크다운 테이블을 보존하며 분할합니다.

        테이블 블록(| 시작 연속 행)은 하나의 단위로 보존하고,
        테이블 외 텍스트만 RecursiveCharacterTextSplitter로 분할합니다.

        Args:
            content: 분할할 텍스트
            config: 청킹 설정

        Returns:
            분할된 텍스트 청크 리스트
        """
        # 테이블 블록과 일반 텍스트를 분리
        blocks: list[tuple[str, str]] = []  # (type, text)
        lines = content.split("\n")
        current_type = "text"
        current_lines: list[str] = []

        for line in lines:
            is_table_line = line.strip().startswith("|") and line.strip().endswith("|")
            if is_table_line:
                if current_type == "text" and current_lines:
                    blocks.append(("text", "\n".join(current_lines)))
                    current_lines = []
                current_type = "table"
                current_lines.append(line)
            else:
                if current_type == "table" and current_lines:
                    blocks.append(("table", "\n".join(current_lines)))
                    current_lines = []
                current_type = "text"
                current_lines.append(line)

        if current_lines:
            blocks.append((current_type, "\n".join(current_lines)))

        # 블록을 chunk_size 이내로 병합
        splitter = self._get_splitter(config)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for block_type, block_text in blocks:
            block_len = len(block_text)

            if block_type == "table":
                # 테이블 블록은 절대 분할하지 않음
                if current_len + block_len > config.chunk_size and current_chunk:
                    # 현재 축적된 텍스트 먼저 출력
                    chunks.extend(splitter.split_text("\n".join(current_chunk)))
                    current_chunk = []
                    current_len = 0

                if block_len > config.chunk_size:
                    # 테이블 자체가 chunk_size 초과: 그래도 보존
                    chunks.append(block_text)
                else:
                    current_chunk.append(block_text)
                    current_len += block_len
            else:
                # 일반 텍스트
                if current_len + block_len > config.chunk_size and current_chunk:
                    combined = "\n".join(current_chunk)
                    chunks.extend(splitter.split_text(combined))
                    current_chunk = []
                    current_len = 0

                current_chunk.append(block_text)
                current_len += block_len

        # 남은 블록 처리
        if current_chunk:
            combined = "\n".join(current_chunk)
            if len(combined) > config.chunk_size:
                chunks.extend(splitter.split_text(combined))
            else:
                chunks.append(combined)

        return [c for c in chunks if c.strip()]

    def _split_preserving_qa(
        self, content: str, config: ChunkingConfig
    ) -> list[str]:
        """질의-회시 쌍을 보존하며 분할합니다.

        "질의 :"와 "회시 :" 패턴을 감지하여 Q&A 쌍을 하나의 단위로 보존합니다.
        chunk_size 초과 시 회시 부분만 추가 분할하되, 질의를 prefix로 유지합니다.

        Args:
            content: 분할할 텍스트
            config: 청킹 설정

        Returns:
            분할된 텍스트 청크 리스트
        """
        # "질의 :" 또는 "회시 :" 로 블록 분리
        parts = _QA_SPLIT_RE.split(content)
        parts = [p for p in parts if p.strip()]

        if len(parts) <= 1:
            # Q&A 패턴이 없으면 기본 splitter 사용
            splitter = self._get_splitter(config)
            return splitter.split_text(content)

        # Q&A 쌍 구성: (질의, 회시)
        qa_pairs: list[tuple[str, str]] = []
        header = ""  # 질의/회시 이전 텍스트 (제목 등)
        current_question = ""

        for part in parts:
            stripped = part.strip()
            if stripped.startswith("질의"):
                if current_question:
                    # 이전 질의가 회시 없이 끝남 → 단독 저장
                    qa_pairs.append((current_question, ""))
                current_question = stripped
            elif stripped.startswith("회시"):
                qa_pairs.append((current_question, stripped))
                current_question = ""
            else:
                # Q&A 이전의 헤더/컨텍스트
                header = stripped

        if current_question:
            qa_pairs.append((current_question, ""))

        chunks: list[str] = []
        splitter = self._get_splitter(config)

        for question, answer in qa_pairs:
            qa_text = question
            if answer:
                qa_text += "\n\n" + answer
            if header:
                qa_text = header + "\n\n" + qa_text

            if len(qa_text) <= config.chunk_size:
                chunks.append(qa_text)
            else:
                # chunk_size 초과: 회시 부분만 분할, 질의를 prefix로 유지
                if answer:
                    prefix = header + "\n\n" + question + "\n\n" if header else question + "\n\n"
                    answer_chunks = splitter.split_text(answer)
                    for ac in answer_chunks:
                        chunks.append(prefix + ac)
                else:
                    # 질의만 있고 chunk_size 초과 → 기본 분할
                    chunks.extend(splitter.split_text(qa_text))

        return [c for c in chunks if c.strip()]

    def load_file(
        self,
        file_path: Path,
        collection_domain: str = "",
        enable_prefix: bool = True,
        enable_parent_child: bool = True,
        include_full_content: bool = False,
    ) -> Iterator[Document]:
        """파일에서 문서를 로드합니다.

        JSONL 파일을 읽어 각 줄을 Document로 변환합니다.
        파일별 청킹 설정에 따라 텍스트를 분할할 수 있습니다.

        Args:
            file_path: 파일 경로
            collection_domain: 적재 대상 컬렉션 도메인 키
            enable_prefix: True이면 contextual prefix를 page_content에 추가
            enable_parent_child: True이면 parent/child 2단계 분할 적용
            include_full_content: True이면 청킹된 문서의 metadata["_full_content"]에
                원본 content 전문을 첨부 (Contextual Retrieval용, standalone은 스킵)

        Yields:
            LangChain Document 인스턴스
        """
        file_name = file_path.name
        chunk_config = FILE_CHUNKING_CONFIG.get(file_name)

        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                data = self._parse_jsonl_line(line, line_num, file_name)
                if data is None:
                    continue

                content = data.get("content", "")
                original_content = content  # 청킹 전 원본 전문 보존

                # P2-2: Contextual prefix 생성
                prefix = generate_prefix(data, file_name) if enable_prefix else ""

                if self._should_chunk(content, file_name, chunk_config):
                    # Parent 청크 생성 (기존 chunk_size 유지)
                    parent_chunks = self._split_text(content, chunk_config)

                    for p_idx, parent_text in enumerate(parent_chunks):
                        parent_content = f"{prefix} {parent_text}" if prefix else parent_text
                        parent_data = data.copy()
                        parent_data["content"] = parent_content
                        p_id = f"{data.get('id', '')}_{p_idx}"

                        # Parent Document
                        parent_doc = self._create_document(
                            parent_data, file_name,
                            chunk_index=p_idx,
                            collection_domain=collection_domain,
                            chunk_type="parent",
                        )
                        if include_full_content:
                            parent_doc.metadata["_full_content"] = original_content
                        yield parent_doc

                        # P2-3: Child 청크 생성 (500자, 정밀 검색용)
                        if enable_parent_child:
                            child_chunks = self._split_child_text(parent_text)
                            for c_idx, child_text in enumerate(child_chunks):
                                child_content = f"{prefix} {child_text}" if prefix else child_text
                                child_data = data.copy()
                                child_data["content"] = child_content

                                child_doc = self._create_document(
                                    child_data, file_name,
                                    chunk_index=p_idx,
                                    child_index=c_idx,
                                    collection_domain=collection_domain,
                                    chunk_type="child",
                                    parent_id=p_id,
                                )
                                yield child_doc
                else:
                    # 공고 원문(_full_text) 청킹 분기
                    full_text = data.get("_full_text", "")
                    if (
                        full_text
                        and file_name == "announcements.jsonl"
                        and len(full_text) > ANNOUNCEMENT_FULLTEXT_CHUNK_THRESHOLD
                    ):
                        # _full_text를 청크로 분할, 각 청크에 구조화 header 포함
                        ft_chunks = self._split_text(
                            full_text, ANNOUNCEMENT_CHUNKING_CONFIG,
                        )
                        header = f"{prefix} {content}" if prefix else content
                        doc_id = data.get("id", "")

                        for p_idx, ft_chunk in enumerate(ft_chunks):
                            parent_content = f"{header}\n\n[공고 원문]\n{ft_chunk}"
                            parent_data = data.copy()
                            parent_data["content"] = parent_content
                            p_id = f"{doc_id}_{p_idx}"

                            parent_doc = self._create_document(
                                parent_data, file_name,
                                chunk_index=p_idx,
                                collection_domain=collection_domain,
                                chunk_type="parent",
                            )
                            yield parent_doc

                            # Child 청크 생성 (정밀 검색용)
                            if enable_parent_child:
                                child_chunks = self._split_child_text(ft_chunk)
                                for c_idx, child_text in enumerate(child_chunks):
                                    child_content = (
                                        f"{prefix} {child_text}"
                                        if prefix else child_text
                                    )
                                    child_data = data.copy()
                                    child_data["content"] = child_content

                                    yield self._create_document(
                                        child_data, file_name,
                                        chunk_index=p_idx,
                                        child_index=c_idx,
                                        collection_domain=collection_domain,
                                        chunk_type="child",
                                        parent_id=p_id,
                                    )
                        continue

                    # _full_text가 짧으면 content에 합침
                    if full_text and file_name == "announcements.jsonl":
                        content = f"{content}\n\n[공고 원문]\n{full_text}"

                    # Standalone: 청킹 불필요한 문서 (include_full_content 스킵)
                    if prefix:
                        standalone_data = data.copy()
                        standalone_data["content"] = f"{prefix} {content}"
                    else:
                        standalone_data = data
                    yield self._create_document(
                        standalone_data, file_name,
                        collection_domain=collection_domain,
                        chunk_type="standalone",
                    )

    def load_db_documents(
        self,
        domain: str,
        source_files: list[str] | None = None,
        enable_prefix: bool = True,
        enable_parent_child: bool = True,
        include_full_content: bool = False,
    ) -> Iterator[Document]:
        """특정 도메인의 문서를 로드합니다.

        도메인에 매핑된 데이터 파일을 읽어 Document로 변환합니다.
        FILE_SOURCE_DIR로 소스 디렉토리를 명시적으로 결정합니다.

        Args:
            domain: 도메인 키 (startup_funding, finance_tax, hr_labor, law_common)
            source_files: 로드할 파일명 목록. None이면 도메인 전체 파일 로드.
            enable_prefix: True이면 contextual prefix를 page_content에 추가
            enable_parent_child: True이면 parent/child 2단계 분할 적용
            include_full_content: True이면 청킹된 문서의 metadata["_full_content"]에 원본 전문 첨부

        Yields:
            LangChain Document 인스턴스

        Raises:
            ValueError: 유효하지 않은 도메인인 경우
        """
        if domain not in DATA_SOURCES:
            raise ValueError(f"유효하지 않은 도메인: {domain}")

        for file_name, target_domain in FILE_TO_COLLECTION_MAPPING.items():
            if target_domain != domain:
                continue
            if source_files is not None and file_name not in source_files:
                continue

            source_key = FILE_SOURCE_DIR.get(file_name, domain)
            source_dir = DATA_SOURCES.get(source_key)
            if source_dir is None:
                logger.warning("소스 디렉토리 없음: %s (key: %s)", file_name, source_key)
                continue

            file_path = source_dir / file_name
            if not file_path.exists():
                logger.warning("파일 없음: %s (경로: %s)", file_name, file_path)
                continue

            logger.info("Loading %s → %s_db [source: %s/]", file_name, domain, source_key)
            yield from self.load_file(
                file_path,
                collection_domain=domain,
                enable_prefix=enable_prefix,
                enable_parent_child=enable_parent_child,
                include_full_content=include_full_content,
            )

    def get_file_stats(
        self,
        domain: str,
        enable_prefix: bool = True,
        enable_parent_child: bool = True,
    ) -> dict[str, int]:
        """도메인의 파일별 문서 수 통계를 반환합니다.

        Args:
            domain: 도메인 키
            enable_prefix: True이면 contextual prefix 적용
            enable_parent_child: True이면 parent/child 분할 적용

        Returns:
            파일 이름별 문서 수 딕셔너리
        """
        stats: dict[str, int] = {}

        if domain not in DATA_SOURCES:
            return stats

        for file_name, target_domain in FILE_TO_COLLECTION_MAPPING.items():
            if target_domain != domain:
                continue

            source_key = FILE_SOURCE_DIR.get(file_name, domain)
            source_dir = DATA_SOURCES.get(source_key)
            if source_dir is None:
                continue

            file_path = source_dir / file_name
            if file_path.exists():
                count = sum(1 for _ in self.load_file(
                    file_path,
                    collection_domain=domain,
                    enable_prefix=enable_prefix,
                    enable_parent_child=enable_parent_child,
                ))
                stats[file_name] = count

        return stats
