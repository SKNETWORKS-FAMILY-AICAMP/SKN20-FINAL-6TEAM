# Bizi 데이터 통합 스키마

> 이 문서는 RAG 시스템에서 사용하는 모든 전처리 데이터의 스키마를 정의합니다.
> 모든 전처리기(`scripts/preprocessing/`)는 이 스키마를 따라야 합니다.

## 통합 스키마

모든 전처리된 문서는 동일한 JSON Lines(JSONL) 형식을 따릅니다.

```json
{
  "id": "TYPE_SOURCE_ID",
  "type": "law | interpretation | guide | schedule | labor_qa | court_case | ...",
  "domain": "legal | tax | labor | startup | funding | marketing",
  "title": "문서 제목",
  "content": "RAG 검색용 본문",
  "source": {
    "name": "출처명",
    "url": "원본 URL",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "YYYY-MM-DD",
  "related_laws": [
    {
      "law_id": "LAW_010719",
      "law_name": "근로기준법",
      "article_ref": "제15조"
    }
  ],
  "metadata": {}
}
```

---

## 필드 설명

### 필수 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 문서 고유 ID (ID 체계 참조) |
| `type` | string | 문서 유형 |
| `domain` | string | 도메인 분류 |
| `title` | string | 제목 |
| `content` | string | RAG 검색용 본문 |
| `source` | object | 출처 정보 |

### 선택 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `effective_date` | string | 시행일/마감일 (YYYY-MM-DD) |
| `related_laws` | array | 관련 법령 참조 목록 |
| `metadata` | object | 타입별 추가 데이터 |

---

## ID 체계

각 문서 타입별 고유 ID 형식입니다. 중복을 방지하기 위해 반드시 이 형식을 따라야 합니다.

| 타입 | ID 형식 | 예시 |
|------|---------|------|
| 법령 | `LAW_{law_id}` | `LAW_010719` |
| 해석례 | `INTERP_{기관}_{id}` | `INTERP_LABOR_313107` |
| 판례 | `COURT_{domain}_{id}` | `COURT_LABOR_12345` |
| 공고 | `ANNOUNCE_{source}_{id}` | `ANNOUNCE_BIZINFO_123` |
| 가이드 | `GUIDE_{업종코드}` | `GUIDE_011000` |
| 일정 | `SCHEDULE_TAX_{날짜}_{순번}` | `SCHEDULE_TAX_20260126_001` |
| 질의회시 | `LABOR_QA_{장}_{페이지}_{순번}` | `LABOR_QA_1_15_001` |

---

## 도메인 분류

| 도메인 | 설명 | 키워드 |
|--------|------|--------|
| `tax` | 세무/회계 | 세법, 소득세, 법인세, 부가가치세 |
| `labor` | 노동/인사 | 근로, 노동, 고용, 임금, 퇴직, 해고 |
| `startup` | 창업/사업자 | 사업자, 창업, 법인설립, 업종, 인허가 |
| `funding` | 지원사업 | 지원사업, 보조금, 정책자금, 공고 |
| `legal` | 법률 | 상법, 민법, 공정거래, 계약 |
| `marketing` | 마케팅 | 광고, 홍보, 브랜딩 |

---

## 타입별 상세

### law (법령)

```json
{
  "id": "LAW_010719",
  "type": "law",
  "domain": "labor",
  "title": "근로기준법",
  "content": "제1조(목적) 이 법은 헌법에 따라...\n제2조(정의)...",
  "source": {
    "name": "국가법령정보센터",
    "url": "https://law.go.kr/법령/근로기준법",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2024-02-09",
  "metadata": {
    "ministry": "고용노동부",
    "enforcement_date": "20240209",
    "article_count": 116
  }
}
```

### interpretation (해석례)

```json
{
  "id": "INTERP_LABOR_123456",
  "type": "interpretation",
  "domain": "labor",
  "title": "연장근로수당 산정 기준",
  "content": "질의: ... 회신: ...",
  "source": {
    "name": "고용노동부",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "related_laws": [
    {"law_id": "LAW_010719", "law_name": "근로기준법", "article_ref": "제56조"}
  ],
  "metadata": {
    "organization": "고용노동부",
    "case_no": "근로기준정책과-5076"
  }
}
```

### labor_qa (노동 질의회시)

```json
{
  "id": "LABOR_QA_1_15_001",
  "type": "labor_qa",
  "domain": "labor",
  "title": "연장근로 계산 방법",
  "content": "[질의] 연장근로수당은 어떻게 계산하나요?\n[회시] 연장근로수당은...",
  "source": {
    "name": "근로기준법 질의회시집",
    "url": null,
    "collected_at": "2026-01-20T11:43:48"
  },
  "metadata": {
    "chapter": "1",
    "section": "근로시간",
    "admin_no": "근로기준정책과-5076",
    "admin_date": "2018.8.1"
  }
}
```

### court_case (판례)

```json
{
  "id": "COURT_LABOR_12345",
  "type": "court_case",
  "domain": "labor",
  "title": "부당해고 무효 확인",
  "content": "사건번호: 2023다12345\n주문: ...\n이유: ...",
  "source": {
    "name": "대법원",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "related_laws": [
    {"law_id": "LAW_010719", "law_name": "근로기준법", "article_ref": "제23조"}
  ],
  "metadata": {
    "court": "대법원",
    "case_no": "2023다12345",
    "judgment_date": "2024-03-15"
  }
}
```

### guide (창업 가이드)

```json
{
  "id": "GUIDE_011000",
  "type": "guide",
  "domain": "startup",
  "title": "음식점업 창업 가이드",
  "content": "[개요] 음식점업은...\n[인허가] 영업신고...",
  "source": {
    "name": "창업진흥원",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "metadata": {
    "industry_code": "011000",
    "category": "음식점업"
  }
}
```

### schedule (세무 일정)

```json
{
  "id": "SCHEDULE_TAX_20260126_001",
  "type": "schedule",
  "domain": "tax",
  "title": "법인세 신고",
  "content": "법인세 신고 및 납부 마감일입니다.",
  "source": {
    "name": "국세청",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2026-01-26",
  "metadata": {
    "tax_type": "법인세",
    "deadline_type": "신고"
  }
}
```

### announce (지원사업 공고)

```json
{
  "id": "ANNOUNCE_BIZINFO_123",
  "type": "announce",
  "domain": "funding",
  "title": "2026년 창업성장기술개발사업",
  "content": "[지원대상] 창업 7년 이내 중소기업\n[지원금액] 최대 3억원...",
  "source": {
    "name": "기업마당",
    "url": "https://...",
    "collected_at": "2026-01-20T11:43:48"
  },
  "effective_date": "2026-02-28",
  "metadata": {
    "host_organization": "중소벤처기업부",
    "support_amount": "최대 3억원",
    "target_audience": ["창업기업", "중소기업"]
  }
}
```

---

## 출력 파일 위치

| 경로 | 설명 | 예상 레코드 수 |
|------|------|---------------|
| `data/preprocessed/law/laws_full.jsonl` | 전체 법령 | ~5,500 |
| `data/preprocessed/law/law_lookup.json` | 법령명 → law_id 매핑 | - |
| `data/preprocessed/law/interpretations.jsonl` | 법령해석례 | ~8,600 |
| `data/preprocessed/law/court_cases_labor.jsonl` | 노동 판례 | ~1,000 |
| `data/preprocessed/law/court_cases_tax.jsonl` | 세무 판례 | ~2,000 |
| `data/preprocessed/labor/labor_qa.jsonl` | 질의회시 (PDF 추출) | ~500 |
| `data/preprocessed/finance/tax_schedule.jsonl` | 세무 신고 일정 | ~240 |
| `data/preprocessed/startup_support/industries.jsonl` | 업종별 창업 가이드 | ~1,600 |
| `data/preprocessed/startup_support/startup_procedures.jsonl` | 창업 절차 가이드 | - |

---

## 데이터 품질 검증

### 검증 체크리스트

- [ ] 모든 JSONL 레코드가 통합 스키마 준수
- [ ] 필수 필드 (id, type, domain, title, content, source) 존재
- [ ] ID 형식 규칙 준수 (중복 없음)
- [ ] `related_laws[].law_id`가 `law_lookup.json`에 존재
- [ ] 한글 인코딩 정상 (UTF-8)

### 검증 명령어

```bash
# JSONL 형식 확인
head -3 data/preprocessed/law/laws_full.jsonl | jq .

# 레코드 수 확인
wc -l data/preprocessed/*/*.jsonl

# ID 중복 확인
jq -r '.id' data/preprocessed/law/laws_full.jsonl | sort | uniq -d
```

---

## 참고 문서

- [scripts/CLAUDE.md](../scripts/CLAUDE.md) - 크롤링/전처리 스크립트 개발 가이드
- [data/CLAUDE.md](../data/CLAUDE.md) - 데이터 폴더 개발 가이드
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 개발 가이드
