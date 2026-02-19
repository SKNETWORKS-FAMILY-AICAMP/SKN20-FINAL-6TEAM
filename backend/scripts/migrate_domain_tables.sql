-- ============================================================
-- 마이그레이션: domain 테이블 구조 변경
-- 커밋: ed4b03f [feat] 도메인 설정 리팩토링
-- 변경 내용:
--   - domain 테이블 삭제
--   - domain_keyword, domain_compound_rule, domain_representative_query
--     테이블의 FK를 domain_id → code_id 로 변경
-- 실행 방법: MySQL Workbench 또는 mysql 클라이언트에서 실행
-- ============================================================

USE bizi_db;

-- 1. 기존 테이블 삭제 (FK 의존성 순서 역순)
DROP TABLE IF EXISTS `domain_representative_query`;
DROP TABLE IF EXISTS `domain_compound_rule`;
DROP TABLE IF EXISTS `domain_keyword`;
DROP TABLE IF EXISTS `domain`;

-- 2. domain_keyword 테이블 재생성 (code 테이블 PK 참조)
CREATE TABLE IF NOT EXISTS `domain_keyword` (
    `keyword_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `code_id` INT NOT NULL COMMENT 'code 테이블 PK (에이전트 코드 참조)',
    `keyword` VARCHAR(100) NOT NULL COMMENT '키워드',
    `keyword_type` VARCHAR(20) DEFAULT 'noun' COMMENT 'noun: 명사, verb: 동사',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY `uq_code_keyword` (`code_id`, `keyword`),
    INDEX `idx_domain_keyword_code_id` (`code_id`),
    INDEX `idx_domain_keyword_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. domain_compound_rule 테이블 재생성
CREATE TABLE IF NOT EXISTS `domain_compound_rule` (
    `rule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `code_id` INT NOT NULL COMMENT 'code 테이블 PK (에이전트 코드 참조)',
    `required_lemmas` JSON NOT NULL COMMENT '필수 lemma 목록 (JSON 배열)',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '규칙 설명',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_domain_compound_rule_code_id` (`code_id`),
    INDEX `idx_domain_compound_rule_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. domain_representative_query 테이블 재생성
CREATE TABLE IF NOT EXISTS `domain_representative_query` (
    `query_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `code_id` INT NOT NULL COMMENT 'code 테이블 PK (에이전트 코드 참조)',
    `query_text` VARCHAR(500) NOT NULL COMMENT '대표 질문',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',

    FOREIGN KEY (`code_id`) REFERENCES `code`(`code_id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_domain_rep_query_code_id` (`code_id`),
    INDEX `idx_domain_rep_query_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Domain Keyword 초기 데이터 삽입
INSERT INTO `domain_keyword` (`code_id`, `keyword`, `keyword_type`)
SELECT c.code_id, kw.keyword, kw.keyword_type
FROM `code` c
CROSS JOIN (
    SELECT '창업' AS keyword, 'noun' AS keyword_type
    UNION ALL SELECT '사업자등록', 'noun'
    UNION ALL SELECT '법인설립', 'noun'
    UNION ALL SELECT '업종', 'noun'
    UNION ALL SELECT '인허가', 'noun'
    UNION ALL SELECT '지원사업', 'noun'
    UNION ALL SELECT '보조금', 'noun'
    UNION ALL SELECT '정책자금', 'noun'
    UNION ALL SELECT '공고', 'noun'
    UNION ALL SELECT '지원금', 'noun'
    UNION ALL SELECT '마케팅', 'noun'
    UNION ALL SELECT '광고', 'noun'
    UNION ALL SELECT '홍보', 'noun'
    UNION ALL SELECT '브랜딩', 'noun'
    UNION ALL SELECT '스타트업', 'noun'
    UNION ALL SELECT '개업', 'noun'
    UNION ALL SELECT '가게', 'noun'
    UNION ALL SELECT '매장', 'noun'
    UNION ALL SELECT '점포', 'noun'
    UNION ALL SELECT '프랜차이즈', 'noun'
    UNION ALL SELECT '사업계획', 'noun'
    UNION ALL SELECT '사업자', 'noun'
    UNION ALL SELECT '폐업', 'noun'
    UNION ALL SELECT '휴업', 'noun'
    UNION ALL SELECT '업종변경', 'noun'
    UNION ALL SELECT '차리다', 'verb'
) kw
WHERE c.code = 'A0000002'
UNION ALL
SELECT c.code_id, kw.keyword, kw.keyword_type
FROM `code` c
CROSS JOIN (
    SELECT '세금' AS keyword, 'noun' AS keyword_type
    UNION ALL SELECT '부가세', 'noun'
    UNION ALL SELECT '법인세', 'noun'
    UNION ALL SELECT '소득세', 'noun'
    UNION ALL SELECT '회계', 'noun'
    UNION ALL SELECT '세무', 'noun'
    UNION ALL SELECT '재무', 'noun'
    UNION ALL SELECT '결산', 'noun'
    UNION ALL SELECT '세무조정', 'noun'
    UNION ALL SELECT '세액', 'noun'
    UNION ALL SELECT '공제', 'noun'
    UNION ALL SELECT '감면', 'noun'
    UNION ALL SELECT '원천징수', 'noun'
    UNION ALL SELECT '종소세', 'noun'
    UNION ALL SELECT '종합소득', 'noun'
    UNION ALL SELECT '양도세', 'noun'
    UNION ALL SELECT '증여세', 'noun'
    UNION ALL SELECT '상속세', 'noun'
    UNION ALL SELECT '부가가치세', 'noun'
    UNION ALL SELECT '세율', 'noun'
    UNION ALL SELECT '세무사', 'noun'
    UNION ALL SELECT '연말정산', 'noun'
    UNION ALL SELECT '간이과세', 'noun'
    UNION ALL SELECT '일반과세', 'noun'
    UNION ALL SELECT '세금계산서', 'noun'
    UNION ALL SELECT '신고하다', 'verb'
    UNION ALL SELECT '납부하다', 'verb'
    UNION ALL SELECT '절세하다', 'verb'
) kw
WHERE c.code = 'A0000003'
UNION ALL
SELECT c.code_id, kw.keyword, kw.keyword_type
FROM `code` c
CROSS JOIN (
    SELECT '근로' AS keyword, 'noun' AS keyword_type
    UNION ALL SELECT '채용', 'noun'
    UNION ALL SELECT '해고', 'noun'
    UNION ALL SELECT '급여', 'noun'
    UNION ALL SELECT '퇴직금', 'noun'
    UNION ALL SELECT '연차', 'noun'
    UNION ALL SELECT '인사', 'noun'
    UNION ALL SELECT '노무', 'noun'
    UNION ALL SELECT '4대보험', 'noun'
    UNION ALL SELECT '근로계약', 'noun'
    UNION ALL SELECT '취업규칙', 'noun'
    UNION ALL SELECT '권고사직', 'noun'
    UNION ALL SELECT '정리해고', 'noun'
    UNION ALL SELECT '월급', 'noun'
    UNION ALL SELECT '임금', 'noun'
    UNION ALL SELECT '최저임금', 'noun'
    UNION ALL SELECT '수당', 'noun'
    UNION ALL SELECT '주휴', 'noun'
    UNION ALL SELECT '짜르다', 'verb'
    UNION ALL SELECT '짤리다', 'verb'
) kw
WHERE c.code = 'A0000004'
UNION ALL
SELECT c.code_id, kw.keyword, kw.keyword_type
FROM `code` c
CROSS JOIN (
    SELECT '법률' AS keyword, 'noun' AS keyword_type
    UNION ALL SELECT '법령', 'noun'
    UNION ALL SELECT '조문', 'noun'
    UNION ALL SELECT '판례', 'noun'
    UNION ALL SELECT '법규', 'noun'
    UNION ALL SELECT '규정', 'noun'
    UNION ALL SELECT '상법', 'noun'
    UNION ALL SELECT '민법', 'noun'
    UNION ALL SELECT '행정법', 'noun'
    UNION ALL SELECT '공정거래법', 'noun'
    UNION ALL SELECT '소송', 'noun'
    UNION ALL SELECT '분쟁', 'noun'
    UNION ALL SELECT '소장', 'noun'
    UNION ALL SELECT '고소', 'noun'
    UNION ALL SELECT '고발', 'noun'
    UNION ALL SELECT '항소', 'noun'
    UNION ALL SELECT '상고', 'noun'
    UNION ALL SELECT '손해배상', 'noun'
    UNION ALL SELECT '배상', 'noun'
    UNION ALL SELECT '합의', 'noun'
    UNION ALL SELECT '조정', 'noun'
    UNION ALL SELECT '중재', 'noun'
    UNION ALL SELECT '특허', 'noun'
    UNION ALL SELECT '상표', 'noun'
    UNION ALL SELECT '저작권', 'noun'
    UNION ALL SELECT '지식재산', 'noun'
    UNION ALL SELECT '출원', 'noun'
    UNION ALL SELECT '침해', 'noun'
    UNION ALL SELECT '변호사', 'noun'
    UNION ALL SELECT '법무사', 'noun'
    UNION ALL SELECT '변리사', 'noun'
    UNION ALL SELECT '계약법', 'noun'
    UNION ALL SELECT '약관', 'noun'
    UNION ALL SELECT '채무불이행', 'noun'
    UNION ALL SELECT '고소하다', 'verb'
    UNION ALL SELECT '소송하다', 'verb'
    UNION ALL SELECT '항소하다', 'verb'
) kw
WHERE c.code = 'A0000007';

-- 6. Domain Compound Rule 초기 데이터 삽입
INSERT INTO `domain_compound_rule` (`code_id`, `required_lemmas`, `description`)
SELECT c.code_id, cr.required_lemmas, cr.description
FROM `code` c
CROSS JOIN (
    SELECT '[\"기업\", \"지원\"]' AS required_lemmas, '지원+기업 → startup_funding' AS description
    UNION ALL SELECT '[\"사업\", \"지원\"]', '지원+사업 → startup_funding'
    UNION ALL SELECT '[\"중소\", \"지원\"]', '지원+중소 → startup_funding'
    UNION ALL SELECT '[\"소상공인\", \"지원\"]', '지원+소상공인 → startup_funding'
    UNION ALL SELECT '[\"벤처\", \"지원\"]', '지원+벤처 → startup_funding'
    UNION ALL SELECT '[\"등록\", \"사업\"]', '등록+사업 → startup_funding'
    UNION ALL SELECT '[\"등록\", \"법인\"]', '등록+법인 → startup_funding'
) cr
WHERE c.code = 'A0000002'
UNION ALL
SELECT c.code_id, cr.required_lemmas, cr.description
FROM `code` c
CROSS JOIN (
    SELECT '[\"법\", \"위반\"]' AS required_lemmas, '법+위반 → law_common' AS description
    UNION ALL SELECT '[\"법\", \"적용\"]', '법+적용 → law_common'
    UNION ALL SELECT '[\"법적\", \"절차\"]', '법적+절차 → law_common'
    UNION ALL SELECT '[\"법적\", \"문제\"]', '법적+문제 → law_common'
) cr
WHERE c.code = 'A0000007';

-- 7. Domain Representative Query 초기 데이터 삽입
INSERT INTO `domain_representative_query` (`code_id`, `query_text`)
SELECT c.code_id, rq.query_text
FROM `code` c
CROSS JOIN (
    SELECT '사업자등록 절차가 궁금합니다' AS query_text
    UNION ALL SELECT '창업 지원사업 추천해주세요'
    UNION ALL SELECT '법인 설립 방법을 알려주세요'
    UNION ALL SELECT '정부 보조금 신청 방법'
    UNION ALL SELECT '마케팅 전략 조언'
    UNION ALL SELECT '스타트업 초기 자금 조달'
    UNION ALL SELECT '업종별 인허가 필요한가요'
    UNION ALL SELECT '창업 아이템 검증 방법'
    UNION ALL SELECT '예비창업자 지원 프로그램'
    UNION ALL SELECT '소상공인 지원정책'
    UNION ALL SELECT '가게 어떻게 차려요'
    UNION ALL SELECT '카페 창업 비용이 얼마나 드나요'
    UNION ALL SELECT '음식점 개업 절차 알려주세요'
    UNION ALL SELECT '프랜차이즈 가맹점 열고 싶어요'
    UNION ALL SELECT '헬스장 차리려면 뭐가 필요해요'
    UNION ALL SELECT '우리 지역에 기업 지원해주는 사업 있나요'
    UNION ALL SELECT 'IT 기업 대상 정부 지원 프로그램 알려주세요'
) rq
WHERE c.code = 'A0000002'
UNION ALL
SELECT c.code_id, rq.query_text
FROM `code` c
CROSS JOIN (
    SELECT '부가세 신고 방법' AS query_text
    UNION ALL SELECT '법인세 계산 방법'
    UNION ALL SELECT '세금 절세 방법'
    UNION ALL SELECT '회계 처리 방법'
    UNION ALL SELECT '재무제표 작성법'
    UNION ALL SELECT '원천징수 신고 절차'
    UNION ALL SELECT '세무조정 어떻게 하나요'
    UNION ALL SELECT '종합소득세 신고 기한'
    UNION ALL SELECT '매입세액 공제 조건'
    UNION ALL SELECT '결산 절차가 궁금합니다'
    UNION ALL SELECT '종소세 언제 내야 하나요'
    UNION ALL SELECT '부가세 납부 기한이 언제예요'
    UNION ALL SELECT '양도세 얼마나 나와요'
    UNION ALL SELECT '연말정산 어떻게 해요'
    UNION ALL SELECT '간이과세자 기준이 뭐예요'
) rq
WHERE c.code = 'A0000003'
UNION ALL
SELECT c.code_id, rq.query_text
FROM `code` c
CROSS JOIN (
    SELECT '퇴직금 계산 방법' AS query_text
    UNION ALL SELECT '근로계약서 작성법'
    UNION ALL SELECT '4대보험 가입 방법'
    UNION ALL SELECT '연차 계산 방법'
    UNION ALL SELECT '해고 절차'
    UNION ALL SELECT '최저임금 적용 기준'
    UNION ALL SELECT '야근 수당 계산'
    UNION ALL SELECT '취업규칙 작성 방법'
    UNION ALL SELECT '근로시간 단축 제도'
    UNION ALL SELECT '채용 공고 작성법'
    UNION ALL SELECT '직원 짤랐는데 퇴직금 얼마 줘야 해요'
    UNION ALL SELECT '월급에서 세금 얼마나 떼나요'
    UNION ALL SELECT '주휴수당 계산법 알려주세요'
    UNION ALL SELECT '권고사직 시 절차가 어떻게 되나요'
    UNION ALL SELECT '알바 4대보험 가입해야 하나요'
) rq
WHERE c.code = 'A0000004'
UNION ALL
SELECT c.code_id, rq.query_text
FROM `code` c
CROSS JOIN (
    SELECT '소송 절차가 어떻게 되나요' AS query_text
    UNION ALL SELECT '분쟁 해결 방법 알려주세요'
    UNION ALL SELECT '특허 출원 방법이 궁금합니다'
    UNION ALL SELECT '상표 등록 절차 안내해주세요'
    UNION ALL SELECT '저작권 침해 시 대응 방법'
    UNION ALL SELECT '상법에서 이사의 의무는 무엇인가요'
    UNION ALL SELECT '민법상 계약 해제 요건'
    UNION ALL SELECT '손해배상 청구 방법'
    UNION ALL SELECT '지식재산권 보호 방법'
    UNION ALL SELECT '법인 이사의 책임에 대해 알려주세요'
    UNION ALL SELECT '계약서 분쟁 시 어떻게 해야 하나요'
    UNION ALL SELECT '특허 침해 소송 절차가 궁금합니다'
    UNION ALL SELECT '회사 관련 법적 분쟁 해결'
) rq
WHERE c.code = 'A0000007';

-- 8. 결과 확인
SELECT '=== 마이그레이션 완료 ===' AS status;
SELECT 'domain_keyword' AS table_name, COUNT(*) AS row_count FROM domain_keyword
UNION ALL SELECT 'domain_compound_rule', COUNT(*) FROM domain_compound_rule
UNION ALL SELECT 'domain_representative_query', COUNT(*) FROM domain_representative_query;
