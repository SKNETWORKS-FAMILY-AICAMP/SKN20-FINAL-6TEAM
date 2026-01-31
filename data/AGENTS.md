# Data AI 에이전트 가이드

> **이 문서는 RAG 에이전트 및 다른 AI 시스템을 위한 가이드입니다.**
> Claude Code 개발 가이드는 [CLAUDE.md](./CLAUDE.md)를 참조하세요.

## 개요

`data/` 폴더는 Bizi RAG 시스템에서 사용하는 모든 데이터를 저장합니다.
- `origin/`: 원본 데이터 (크롤링 결과, PDF 파일 등)
- `preprocessed/`: 전처리된 데이터 (JSONL 형식, RAG 입력용)

## 프로젝트 구조

```
data/
├── CLAUDE.md                  # 상세 개발 가이드
├── AGENTS.md                  # 이 파일
│
├── origin/                    # 원본 데이터
│   ├── 근로기준법 질의회시집.pdf
│   ├── law/                   # 법령 원본
│   ├── startup_support/       # 창업 가이드 원본
│   ├── finance/               # 세무/회계 원본
│   └── labor/                 # 노동/인사 원본
│
└── preprocessed/              # 전처리된 데이터 (JSONL)
    ├── law/                   # 법령, 해석례, 판례
    ├── labor/                 # 노동 질의회시
    ├── finance/               # 세무일정, 가이드
    └── startup_support/       # 창업 가이드
```

## 통합 스키마

상세 스키마 정의는 [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md)를 참조하세요.

**필수 필드**: `id`, `type`, `domain`, `title`, `content`, `source`

## 출력 파일 목록

### law/

| 파일 | 설명 | 예상 수 |
|------|------|---------|
| `laws_full.jsonl` | 전체 법령 | ~5,500 |
| `law_lookup.json` | 법령명 → law_id 매핑 | - |
| `interpretations.jsonl` | 법령해석례 | ~8,600 |
| `court_cases_labor.jsonl` | 노동 판례 | ~1,000 |
| `court_cases_tax.jsonl` | 세무 판례 | ~2,000 |

### labor/

| 파일 | 설명 | 예상 수 |
|------|------|---------|
| `labor_qa.jsonl` | 질의회시 (PDF 추출) | ~500 |

### finance/

| 파일 | 설명 | 예상 수 |
|------|------|---------|
| `tax_schedule.jsonl` | 세무 신고 일정 | ~240 |

### startup_support/

| 파일 | 설명 | 예상 수 |
|------|------|---------|
| `industries.jsonl` | 업종별 창업 가이드 | ~1,600 |
| `startup_procedures.jsonl` | 창업 절차 가이드 | - |

## 파일 수정 시 확인사항

### 새 데이터 타입 추가

1. `scripts/preprocessing/{type}_preprocessor.py` 생성
2. 통합 스키마 준수
3. 적절한 `preprocessed/{domain}/` 폴더에 출력
4. 이 문서의 출력 파일 목록 업데이트

### 스키마 변경

1. 이 문서와 `CLAUDE.md` 스키마 정의 업데이트
2. 모든 전처리기 수정
3. 벡터DB 재인덱싱 필요

### 법령 참조 연결

해석례/판례에서 법령을 참조할 때:
1. `law_lookup.json`에서 법령명으로 law_id 조회
2. `related_laws` 필드에 추가
3. 법령명만 있고 ID가 없는 경우 `law_id: null` 허용

## 데이터 품질 검증

### 검증 체크리스트

- [ ] 모든 JSONL 레코드가 통합 스키마 준수
- [ ] 필수 필드 (id, type, domain, title, content, source) 존재
- [ ] ID 형식 규칙 준수 (중복 없음)
- [ ] `related_laws[].law_id`가 유효한 값
- [ ] 한글 인코딩 정상 (UTF-8)

### 검증 스크립트

```bash
# JSONL 형식 확인
head -3 data/preprocessed/law/laws_full.jsonl | jq .

# 레코드 수 확인
wc -l data/preprocessed/*/*.jsonl

# ID 중복 확인
jq -r '.id' data/preprocessed/law/laws_full.jsonl | sort | uniq -d
```

## 주의사항

### .gitignore 설정

대용량 원본 데이터는 git에서 제외:

```gitignore
origin/law/*.json
origin/**/*.pdf
origin/**/*.csv
```

### 인코딩

- 모든 파일은 UTF-8 인코딩
- CSV 파일이 EUC-KR인 경우 변환 필요

### 용량

- `origin/law/01_laws_full.json`: 304MB
- 전체 origin: ~500MB
- 전체 preprocessed: ~50MB

## 참고 문서

- [docs/DATA_SCHEMA.md](../docs/DATA_SCHEMA.md) - 통합 스키마 정의
- [CLAUDE.md](./CLAUDE.md) - 상세 개발 가이드
- [scripts/CLAUDE.md](../scripts/CLAUDE.md) - 크롤링/전처리 스크립트 가이드
- [scripts/data_pipeline.md](../scripts/data_pipeline.md) - 전처리 파이프라인 상세 설명
- [rag/CLAUDE.md](../rag/CLAUDE.md) - RAG 시스템 가이드
