# Release Notes

## [2026-02-09] - RAG 품질 개선

### Features
- 법령 필터링 기능 추가
- 5단계 평가 시스템 도입 (search_quality_eval)
- 출처 URL 응답 필드 추가
- RAGAS 평가기 추가 (ragas_evaluator.py)
- 네거티브 테스트 케이스 추가 (negative_test_cases.py)
- 검색 품질 리포트 생성 기능

## [2026-02-08] - 초기 릴리즈

### 핵심 기능
- **LangGraph 5단계 파이프라인**: 분류 > 분해 > 검색 > 생성 > 평가
- **3개 도메인 에이전트**: 창업/지원사업, 재무/세무, 인사/노무 전문 상담
- **벡터 기반 도메인 분류**: 키워드 매칭 + VectorDomainClassifier (LLM 미사용)
- **Hybrid Search**: BM25 + Vector + RRF 앙상블 검색
- **Cross-encoder Re-ranking**: 검색 결과 재정렬
- **LLM 쿼리 재작성**: 검색 품질 향상
- **Multi-Query 재검색**: 검색 품질 미달 시 자동 재검색
- **복합 질문 분해**: LLM 기반 QuestionDecomposer
- **3중 평가 체계**: 규칙 기반 검색 평가 + LLM 평가 + RAGAS 정량 평가
- **도메인 외 질문 거부**: 상담 범위 밖 질문 자동 필터링
- **문서 생성**: 근로계약서, 사업계획서 등 PDF/HWP
- **응답 캐싱**: LRU 캐시 (500건, 1시간 TTL)
- **CLI 테스트 모드**: 서버 없이 터미널에서 RAG 파이프라인 테스트
- **SSE 스트리밍**: 실시간 응답 스트리밍

### 기술 스택
- FastAPI + LangChain + LangGraph
- OpenAI GPT-4o-mini
- ChromaDB + BAAI/bge-m3 임베딩
- RAGAS 평가 라이브러리

### 파일 통계
- 총 파일: 205개
