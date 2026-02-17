#!/usr/bin/env bash
# =============================================================================
# AWS Secrets Manager에서 시크릿을 가져와 .env 파일에 병합하는 헬퍼 스크립트
#
# 사용법:
#   ./scripts/load_secrets.sh <secret-name> [--env-file .env]
#
# 예시:
#   ./scripts/load_secrets.sh bizi/production
#   ./scripts/load_secrets.sh bizi/staging --env-file .env.staging
#
# 요구사항:
#   - AWS CLI v2 (aws secretsmanager)
#   - jq (JSON 파싱)
#   - IAM Role 또는 AWS credentials 설정
# =============================================================================

set -euo pipefail

# --- Arguments ---
SECRET_NAME="${1:-}"
ENV_FILE=".env"

if [ -z "$SECRET_NAME" ]; then
    echo "ERROR: secret name is required"
    echo "Usage: $0 <secret-name> [--env-file <path>]"
    exit 1
fi

shift
while [ $# -gt 0 ]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# --- Dependency check ---
for cmd in aws jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' is required but not installed."
        exit 1
    fi
done

REGION="${AWS_DEFAULT_REGION:-ap-northeast-2}"

echo "Fetching secret: $SECRET_NAME (region: $REGION)"

# --- Fetch secret ---
SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$REGION" \
    --query SecretString \
    --output text 2>&1) || {
    echo "ERROR: Failed to fetch secret '$SECRET_NAME'"
    echo "$SECRET_JSON"
    exit 1
}

# --- Validate JSON ---
if ! echo "$SECRET_JSON" | jq empty 2>/dev/null; then
    echo "ERROR: Secret value is not valid JSON"
    exit 1
fi

# --- Create .env if not exists ---
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating new $ENV_FILE"
    touch "$ENV_FILE"
fi

# --- Merge secrets into .env ---
KEYS_UPDATED=0
KEYS_ADDED=0

while IFS='=' read -r key value; do
    # Skip empty keys
    [ -z "$key" ] && continue

    # Remove surrounding quotes from value
    value="${value%\"}"
    value="${value#\"}"

    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing key (use | as delimiter to avoid issues with / in values)
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        KEYS_UPDATED=$((KEYS_UPDATED + 1))
    else
        # Add new key
        echo "${key}=${value}" >> "$ENV_FILE"
        KEYS_ADDED=$((KEYS_ADDED + 1))
    fi
done < <(echo "$SECRET_JSON" | jq -r 'to_entries[] | "\(.key)=\(.value)"')

# --- Secure file permissions ---
chmod 600 "$ENV_FILE"

echo "Done: $KEYS_UPDATED updated, $KEYS_ADDED added in $ENV_FILE"
echo "File permissions set to 600 (owner read/write only)"
