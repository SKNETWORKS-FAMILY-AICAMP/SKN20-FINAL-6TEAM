# Scripts - 데이터 크롤링 및 전처리 스크립트

> AI 에이전트(Claude Code) 전용 코드 작성 가이드입니다.
> 기술 스택, 실행 방법, 크롤러/전처리기 상세 사용법 등 일반 정보는 [README.md](./README.md)를 참조하세요.

---

## 통합 스키마

모든 전처리기는 동일한 스키마를 따릅니다. 상세 스키마 정의는 [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)를 참조하세요.

**필수 필드**: `id`, `type`, `domain`, `title`, `content`, `source`

### 새 전처리기 추가 시
1. `preprocessing/preprocess_{name}.py` 생성
2. 출력 포맷을 통합 스키마에 맞춰 JSONL로 저장
3. 출력 경로: `data/preprocessed/{domain}/` 하위

### 새 크롤러 추가 시
1. `crawling/collect_{name}.py` 생성
2. 출력 경로: `data/origin/` 하위
3. 아래 크롤링 에티켓 준수

---

## 코드 품질

`.claude/rules/coding-style.md`, `.claude/rules/security.md` 참조

### 크롤링 에티켓 (필수)
- robots.txt 준수
- 요청 간격: 최소 1초
- User-Agent 명시
- 에러 시 재시도 로직 (exponential backoff)

---

## 참고 문서

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) - 통합 스키마 정의
- [data_pipeline.md](./data_pipeline.md) - 전처리 파이프라인 상세 설명
- [data/CLAUDE.md](../data/CLAUDE.md) - 데이터 폴더 가이드
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 가이드
