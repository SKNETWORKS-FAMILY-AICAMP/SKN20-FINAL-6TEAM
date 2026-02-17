"""배포 전 .env 파일 유효성 검사 스크립트.

stdlib만 사용하는 독립 스크립트입니다.
.env 파일의 필수/권장 변수 존재 여부, 플레이스홀더 사용 여부,
JWT 키 길이를 검사합니다.

사용법:
    python scripts/validate_env.py               # 기본 검사
    python scripts/validate_env.py --production  # 프로덕션 필수 항목 엄격 검사
    python scripts/validate_env.py --env .env.staging  # 특정 파일 검사
"""

import argparse
import re
import sys
from pathlib import Path

# 플레이스홀더로 판단되는 패턴
PLACEHOLDER_PATTERNS = [
    re.compile(r"^your-", re.IGNORECASE),
    re.compile(r"^changeme", re.IGNORECASE),
    re.compile(r"^TODO", re.IGNORECASE),
    re.compile(r"^xxx", re.IGNORECASE),
    re.compile(r"^placeholder", re.IGNORECASE),
    re.compile(r"^example", re.IGNORECASE),
]

# 프로덕션 필수 변수
PRODUCTION_REQUIRED = [
    "MYSQL_HOST",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "JWT_SECRET_KEY",
    "OPENAI_API_KEY",
    "RAG_API_KEY",
]

# 프로덕션 권장 변수
PRODUCTION_RECOMMENDED = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "RUNPOD_API_KEY",
    "RUNPOD_ENDPOINT_ID",
    "CHROMA_AUTH_TOKEN",
]

# 공통 필수 변수 (모든 환경)
COMMON_REQUIRED = [
    "MYSQL_DATABASE",
    "JWT_SECRET_KEY",
]

MIN_JWT_KEY_LENGTH = 32


def parse_env_file(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a key-value dictionary."""
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Remove surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env_vars[key] = value

    return env_vars


def is_placeholder(value: str) -> bool:
    """Check if a value looks like a placeholder."""
    return any(p.match(value) for p in PLACEHOLDER_PATTERNS)


def validate(env_vars: dict[str, str], production: bool) -> tuple[list[str], list[str]]:
    """Validate environment variables.

    Returns:
        Tuple of (errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 공통 필수 변수 검사
    for key in COMMON_REQUIRED:
        value = env_vars.get(key, "")
        if not value:
            errors.append(f"[MISSING] {key} 가 설정되지 않았습니다.")
        elif is_placeholder(value):
            errors.append(f"[PLACEHOLDER] {key} 가 플레이스홀더 값입니다: {value}")

    # JWT 키 길이 검사
    jwt_key = env_vars.get("JWT_SECRET_KEY", "")
    if jwt_key and len(jwt_key) < MIN_JWT_KEY_LENGTH:
        errors.append(
            f"[WEAK] JWT_SECRET_KEY 길이가 {len(jwt_key)}자입니다. "
            f"최소 {MIN_JWT_KEY_LENGTH}자 이상이어야 합니다."
        )

    # ENVIRONMENT 값 검사
    env_val = env_vars.get("ENVIRONMENT", "development")
    if production and env_val != "production":
        warnings.append(
            f"[ENV] ENVIRONMENT={env_val} 입니다. "
            "프로덕션 배포 시 'production'으로 설정하세요."
        )

    # 프로덕션 모드 검사
    if production:
        for key in PRODUCTION_REQUIRED:
            value = env_vars.get(key, "")
            if not value:
                errors.append(f"[PROD-REQUIRED] {key} 가 설정되지 않았습니다.")
            elif is_placeholder(value):
                errors.append(f"[PROD-PLACEHOLDER] {key} 가 플레이스홀더 값입니다: {value}")

        for key in PRODUCTION_RECOMMENDED:
            value = env_vars.get(key, "")
            if not value:
                warnings.append(f"[PROD-RECOMMENDED] {key} 설정을 권장합니다.")

        # 프로덕션에서 테스트 로그인 비활성화 검사
        test_login = env_vars.get("ENABLE_TEST_LOGIN", "false").lower()
        if test_login == "true":
            errors.append(
                "[SECURITY] ENABLE_TEST_LOGIN=true 입니다. "
                "프로덕션에서는 반드시 false로 설정하세요."
            )

        # 프로덕션에서 COOKIE_SECURE 검사
        cookie_secure = env_vars.get("COOKIE_SECURE", "false").lower()
        if cookie_secure != "true":
            warnings.append(
                "[SECURITY] COOKIE_SECURE=true 를 권장합니다 (HTTPS 환경)."
            )

    # 모든 변수에 대해 플레이스홀더 경고
    for key, value in env_vars.items():
        if key not in COMMON_REQUIRED and key not in PRODUCTION_REQUIRED:
            if value and is_placeholder(value):
                warnings.append(f"[PLACEHOLDER] {key} 가 플레이스홀더로 보입니다: {value}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="배포 전 .env 파일 유효성 검사"
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="프로덕션 필수 항목 엄격 검사",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help=".env 파일 경로 (기본: .env)",
    )
    args = parser.parse_args()

    # 프로젝트 루트 기준 경로 해석
    env_path = Path(args.env)
    if not env_path.is_absolute():
        env_path = Path(__file__).parent.parent / env_path

    if not env_path.exists():
        print(f"ERROR: {env_path} 파일을 찾을 수 없습니다.")
        return 1

    env_vars = parse_env_file(env_path)
    mode = "PRODUCTION" if args.production else "DEVELOPMENT"
    print(f"=== .env 유효성 검사 ({mode} 모드) ===")
    print(f"파일: {env_path}")
    print(f"변수 수: {len(env_vars)}")
    print()

    errors, warnings = validate(env_vars, args.production)

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")
        print()

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        print()
        print("FAILED: 위 오류를 수정한 후 다시 실행하세요.")
        return 1

    print("PASSED: 모든 검사를 통과했습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
