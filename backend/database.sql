-- ============================================
-- 프로젝트 데이터베이스 스키마
-- 명명 규칙: 테이블명_id (예: user_id, company_id)
-- 정규화 수준: 3NF/BCNF
-- ============================================

-- 한글 깨짐 방지를 위한 charset 설정
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

CREATE DATABASE IF NOT EXISTS final_test;
USE final_test;

-- ============================================
-- 1. Code 테이블 (가장 먼저 생성 - 다른 테이블에서 참조)
-- 업종, 권한, 에이전트, 주관기관 코드 통합 관리
-- ============================================
CREATE TABLE IF NOT EXISTS `code` (
    `code_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL DEFAULT '',
    `main_code` VARCHAR(1) NOT NULL COMMENT 'U:유저, B:업종, A:에이전트',
    `code` VARCHAR(4) NOT NULL UNIQUE,
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    INDEX `idx_code_main_code` (`main_code`),
    INDEX `idx_code_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 초기 Code 테이블 데이터 추가 (테이블이 비어있을 때만)
-- ============================================
INSERT INTO `code` (`name`, `main_code`, `code`)
SELECT * FROM (
    -- 사용자 코드
    SELECT '관리자' AS name, 'U' AS main_code, 'U001' AS code
    UNION ALL SELECT '예비 창업자', 'U', 'U002'
    UNION ALL SELECT '사업자', 'U', 'U003'
    -- 업종 코드
    UNION ALL SELECT '농업, 임엄 및 어업', 'B', 'B001'
    UNION ALL SELECT '광업', 'B', 'B002'
    UNION ALL SELECT '제조업', 'B', 'B003'
    UNION ALL SELECT '전기, 가스, 증기 및 공기 조절 공급업', 'B', 'B004'
    UNION ALL SELECT '수도, 하수 및 페기물 처리, 원료 재생업', 'B', 'B005'
    UNION ALL SELECT '건설업', 'B', 'B006'
    UNION ALL SELECT '도매 및 소매업', 'B', 'B007'
    UNION ALL SELECT '운수 및 창고업', 'B', 'B008'
    UNION ALL SELECT '숙박 및 임식점업', 'B', 'B009'
    UNION ALL SELECT '정보통신업', 'B', 'B010'
    UNION ALL SELECT '금융 및 보험업', 'B', 'B011'
    UNION ALL SELECT '부동산업', 'B', 'B012'
    UNION ALL SELECT '전문, 과학 및 기술 서비스업', 'B', 'B013'
    UNION ALL SELECT '사업시설 관리, 사업 지원 및 임대 서비스업', 'B', 'B014'
    UNION ALL SELECT '공공 행정, 국방 및 사회보장 행정', 'B', 'B015'
    UNION ALL SELECT '교육 서비스업', 'B', 'B016'
    UNION ALL SELECT '보건업 및 사회복지 서비스업', 'B', 'B017'
    UNION ALL SELECT '예술, 스포츠 및 여가관리 서비스업', 'B', 'B018'
    UNION ALL SELECT '협회 및 단체, 수리 및 기타 개인 서비스업', 'B', 'B019'
    UNION ALL SELECT '가구 내 고용활동 및 달리 분류되지 않은 자가소비 생산활동', 'B', 'B020'
    UNION ALL SELECT '국제 및 외국기관', 'B', 'B021'
    -- 에이전트 타입
    UNION ALL SELECT '메인', 'A', 'A001'
    UNION ALL SELECT '창업·지원', 'A', 'A002'
    UNION ALL SELECT '재무·세무', 'A', 'A003'
    UNION ALL SELECT '인사·노무', 'A', 'A004'
    UNION ALL SELECT '평가·검증', 'A', 'A005'
) AS init_data
WHERE NOT EXISTS (SELECT 1 FROM `code` LIMIT 1);

-- ============================================
-- 2. User 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `user` (
    `user_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `google_email` VARCHAR(255) NOT NULL UNIQUE,
    `username` VARCHAR(100) NOT NULL,
    `birth` DATETIME NOT NULL,
    `type_code` VARCHAR(4) NOT NULL DEFAULT 'U002' COMMENT 'U001:관리자, U002:예비창업자, U003:사업자',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`type_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_user_type_code` (`type_code`),
    INDEX `idx_user_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- Test용 User 데이터 추가 (테이블이 비어있을 때만)
-- ============================================
INSERT INTO `user` (`google_email`, `username`, `birth`, `type_code`)
SELECT 'test@bizmate.com', '테스트 사용자', '1990-01-01', 'U002'
WHERE NOT EXISTS (SELECT 1 FROM `user` LIMIT 1);	


-- ============================================
-- 3. Company 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `company` (
    `company_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `com_name` VARCHAR(255) NOT NULL DEFAULT '',
    `biz_num` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '사업자등록번호',
    `addr` VARCHAR(255) NOT NULL DEFAULT '',
    `open_date` DATETIME NOT NULL COMMENT '개업일',
    `biz_code` VARCHAR(4) NOT NULL COMMENT '업종코드',
    `file_path` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '사업자등록증 파일 경로',
    `main_yn` TINYINT(1) DEFAULT 0 COMMENT '0: 일반, 1: 대표 기업',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`biz_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_company_user_id` (`user_id`),
    INDEX `idx_company_biz_code` (`biz_code`),
    INDEX `idx_company_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 4. History 테이블 (상담 및 질문 이력)
-- ============================================
CREATE TABLE IF NOT EXISTS `history` (
    `history_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `agent_code` VARCHAR(4) NOT NULL COMMENT '답변 에이전트 코드',
    `question` LONGTEXT COMMENT '질문',
    `answer` LONGTEXT COMMENT 'JSON 형태 저장 가능',
    `parent_history_id` INT DEFAULT NULL COMMENT '부모 히스토리 ID (대화 연결)',
    -- `sequence` INT NOT NULL DEFAULT 0 COMMENT '순서',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`agent_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    FOREIGN KEY (`parent_history_id`) REFERENCES `history`(`history_id`) ON DELETE SET NULL,
    INDEX `idx_history_user_id` (`user_id`),
    INDEX `idx_history_agent_code` (`agent_code`),
    INDEX `idx_history_parent_id` (`parent_history_id`),
    -- INDEX `idx_history_sequence` (`sequence`),
    INDEX `idx_history_create_date` (`create_date`),
    INDEX `idx_history_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 5. File 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `file` (
    `file_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `file_name` VARCHAR(255) NOT NULL DEFAULT '',
    `file_path` VARCHAR(500) NOT NULL DEFAULT '',
    `history_id` INT DEFAULT 0,
    `company_id` INT DEFAULT 0,
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`history_id`) REFERENCES `history`(`history_id`) ON DELETE SET NULL,
    FOREIGN KEY (`company_id`) REFERENCES `company`(`company_id`) ON DELETE SET NULL,
    INDEX `idx_file_history_id` (`history_id`),
    INDEX `idx_file_company_id` (`company_id`),
    INDEX `idx_file_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 6. Announce 테이블 (공고)
-- ============================================
CREATE TABLE IF NOT EXISTS `announce` (
    `announce_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `ann_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '공고 제목',
    `file_id` INT DEFAULT 0 COMMENT '공고 첨부파일',
    `biz_code` VARCHAR(4) NOT NULL DEFAULT 'B000' COMMENT '관련 업종코드',
    `host_gov` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '주관기관',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`file_id`) REFERENCES `file`(`file_id`) ON DELETE SET NULL,
    FOREIGN KEY (`biz_code`) REFERENCES `code`(`code`) ON UPDATE CASCADE,
    INDEX `idx_announce_biz_code` (`biz_code`),
    INDEX `idx_announce_host_gov` (`host_gov`),
    INDEX `idx_announce_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- 7. Schedule 테이블
-- ============================================
CREATE TABLE IF NOT EXISTS `schedule` (
    `schedule_id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `company_id` INT NOT NULL,
    `announce_id` INT DEFAULT 0,
    `schedule_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '일정 제목',
    `start_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '시작일시',
    `end_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '종료일시',
    `memo` LONGTEXT COMMENT '메모',
    `create_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `update_date` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `use_yn` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0: 미사용, 1: 사용',
    
    FOREIGN KEY (`company_id`) REFERENCES `company`(`company_id`) ON DELETE CASCADE,
    FOREIGN KEY (`announce_id`) REFERENCES `announce`(`announce_id`) ON DELETE SET NULL,
    INDEX `idx_schedule_company_id` (`company_id`),
    INDEX `idx_schedule_announce_id` (`announce_id`),
    INDEX `idx_schedule_start_date` (`start_date`),
    INDEX `idx_schedule_end_date` (`end_date`),
    INDEX `idx_schedule_use_yn` (`use_yn`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
