# 도메인 분류 완성도 개선 플랜

> 검증일: 2026-03-10 (WebSearch 기반 2차 검증 완료)
> 대상: `rag/utils/domain_classifier.py`, `rag/utils/prompts.py`, `rag/agents/router.py`, `rag/tests/`

## 프로덕션 코드

### P1 — 프롬프트에 "인사+도메인 복합" 예시 추가
- **파일**: `rag/utils/prompts.py:510` (경계 케이스 섹션)
- **문제**: 규칙 10번에 명시되어 있지만 few-shot 예시 없음 → LLM 정확도 영향
- **수정**: 경계 케이스 예시에 추가
  ```
  - "안녕하세요 세무 관련 질문이 있는데요" → startup_funding이 아닌 finance_tax로 분류, intent: consultation
  - "반갑습니다 근로계약서 작성 방법 알려주세요" → hr_labor, intent: consultation
  ```

### P2 — 멀티 도메인 문서 도구 판별 개선
- **파일**: `rag/agents/router.py:472-476`
- **문제**: `classification.domains[0]`만 사용 → 두 번째 이후 도메인의 문서 생성 감지 누락
- **수정**: 전체 도메인 순회하여 문서 도구 판별
  ```python
  # Before
  should_doc, detected_doc_type = self.document_tool.should_invoke(
      classify_query, classification.domains[0] if classification.domains else ""
  )

  # After
  should_doc, detected_doc_type = False, None
  for d in classification.domains:
      _should, _type = self.document_tool.should_invoke(classify_query, d)
      if _should and _type:
          should_doc, detected_doc_type = _should, _type
          break
  ```
- **주의**: 순회 시 첫 번째 매칭만 사용하므로 도메인 순서에 의존. `classification.domains`가 confidence/relevance 순 정렬인지 구현 시 확인 필요.

### P3 — followup_fallback 시 intent 보존
- **파일**: `rag/agents/router.py:401-406`
- **문제**: 폴백 시 `intent=None` → 문서 생성 감지 경로 무시됨
- **수정**: 원본 classification의 intent를 보존
  ```python
  classification = DomainClassificationResult(
      domains=previous_domains,
      confidence=max(classification.confidence, 0.5),
      is_relevant=True,
      method="followup_fallback",
      intent=classification.intent,  # 추가
  )
  ```
- **검증 근거**: 멀티턴 intent 분류 연구에서 "폴백 시 이전 컨텍스트의 intent를 보존하지 않으면 도메인 전환 없이도 후속 질문이 잘못 처리된다"는 점이 확인됨. 단, `intent`가 `chitchat_*`인 상태에서 폴백되면 도메인 질문인데 chitchat intent를 갖게 되므로, **폴백 시 chitchat intent는 `"consultation"`으로 재설정**하는 것이 안전.
  ```python
  original_intent = classification.intent
  if original_intent and original_intent.startswith("chitchat"):
      original_intent = "consultation"
  classification = DomainClassificationResult(
      ...
      intent=original_intent,
  )
  ```

### P4 (LOW) — LLM 인스턴스 lazy init 스레드 안전
- **파일**: `rag/utils/domain_classifier.py:72-73`
- **문제**: `asyncio.to_thread` 호출 시 동시 초기화 가능 (중복 생성, 에러 아님)
- **수정**: 필요 시 `threading.Lock` 추가. 현재 위험 낮아 보류 가능.
- **검증 근거**: LangChain Runnable 공식 문서에서 "공유 가변 상태(shared mutable state)는 반드시 locking 메커니즘을 적용하라"고 권고. 다만 `_llm_instance`는 한번 생성 후 불변이므로 중복 생성만 발생하고 데이터 손상 없음. **보류 유지**.

### P5 (LOW) — temperature=0.0 결정론 미보장
- **문제**: seed 미지정으로 동일 쿼리에 다른 결과 가능
- **수정**: 실질적 영향 미미. 모니터링만.
- **검증 근거**: OpenAI 커뮤니티에서 "temperature=0 + seed 설정해도 GPT-4o 기준 10회 호출 시 5개 고유 응답이 나올 수 있다"는 보고 다수. seed 추가해도 완전 결정론은 불가. **보류 유지**.

---

## 테스트 코드

### T1 — chitchat_gibberish 테스트 추가
- **파일**: `rag/tests/test_chitchat.py:16-23`
- **문제**: `expected_intents`에 `"chitchat_gibberish"` 누락
- **수정**: 리스트에 추가
  ```python
  expected_intents = [
      "chitchat_greeting", "chitchat_farewell", "chitchat_thanks",
      "chitchat_bot_identity", "chitchat_affirmative", "chitchat_emotional",
      "chitchat_gibberish",  # 추가
  ]
  ```

### T2 — JSON 파싱 유닛 테스트 추가
- **파일**: `rag/tests/test_domain_classifier.py` (새 클래스)
- **문제**: `_llm_classify`의 JSON 파싱 로직 미검증
- **수정**: `TestLLMResponseParsing` 클래스 추가
  - 정상 JSON 응답 파싱
  - 코드 블록(` ```json ... ``` `) 포함 응답
  - 깨진 JSON + regex fallback
  - intent 필드 누락 시 기본값 `"consultation"`

### T3 — followup_fallback 라우터 통합 테스트 추가
- **파일**: `rag/tests/test_chitchat.py` (새 클래스)
- **문제**: `router.py:380-408` 폴백 분기 미검증
- **수정**: `TestFollowupFallbackRouter` 클래스 추가
  - 재작성 성공 + 거부 + 이전 도메인 → 폴백
  - 재작성 실패(timeout) + history + 이전 도메인 → 폴백
  - topic_changed=True → 폴백 안 함

---

## 작업 순서

1. P1 (프롬프트 예시) — 독립, 즉시 적용
2. P3 (intent 보존 + chitchat 가드) — 독립, 즉시 적용
3. P2 (멀티 도메인 문서 도구) — document_tool.should_invoke 동작 확인 후 적용
4. T1 (gibberish 테스트) — 독립, 즉시 적용
5. T2 (JSON 파싱 테스트) — 독립, 즉시 적용
6. T3 (폴백 통합 테스트) — P3 적용 후

---

## 2차 검증 요약 (WebSearch 기반)

| 항목 | 검증 결과 | 근거 |
|------|-----------|------|
| P1 프롬프트 예시 | **유효** | LangChain 라우터 패턴 문서에서 few-shot 예시가 분류 정확도에 직접 영향함을 확인 |
| P2 멀티 도메인 순회 | **유효 + 주의사항 타당** | LangChain 공식 라우터 패턴은 decompose→parallel route 구조. domains 순서 비보장은 LLM 출력 의존이므로 주의사항 적절 |
| P3 intent 보존 | **유효 + 보강 필요** | 멀티턴 intent 연구에서 폴백 시 컨텍스트 손실이 캐스케이드 오류 유발. **chitchat intent 가드** 추가 필요 (신규 발견) |
| P4 스레드 안전 | **보류 유지** | LangChain 권고는 lock 사용이지만, 불변 객체 중복 생성 수준이므로 위험 낮음 |
| P5 결정론 | **보류 유지** | OpenAI 커뮤니티에서 seed+temp=0도 결정론 불가 확인. 실질적 해결 불가 |
| T1~T3 테스트 | **유효** | 변경 없음 |

### 참고 자료
- [LangChain Multi-source Router Pattern](https://docs.langchain.com/oss/python/langchain/multi-agent/router-knowledge-base)
- [Multi-Agent Architecture 선택 가이드](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/)
- [멀티턴 Intent Classification 연구](https://arxiv.org/html/2411.12307v1)
- [LLM Intent Classification 오류 핸들링](https://medium.com/@mr.murga/enhancing-intent-classification-and-error-handling-in-agentic-llm-applications-df2917d0a3cc)
- [OpenAI temperature=0 비결정론 이슈](https://community.openai.com/t/chatcompletions-are-not-deterministic-even-with-seed-set-temperature-0-top-p-0-n-1/685769)
- [LangChain Runnable 동시성 패턴](https://apxml.com/courses/langchain-production-llm/chapter-1-advanced-langchain-architecture/async-concurrency)
