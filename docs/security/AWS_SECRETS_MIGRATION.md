# AWS Secrets Manager Migration Guide

## 1. Current State

All credentials are stored in `.env` files as plaintext:
- MySQL host, user, password
- JWT secret key
- OpenAI API key
- Google OAuth client secret
- RAG API key
- ChromaDB auth token

**Risk**: `.env` file on EC2 can be read by any process/user with file access.

## 2. Target Architecture

```
EC2 Instance (IAM Role)
    │
    ├── docker-compose.prod.yaml
    │     └── environment:
    │           └── (injected from Secrets Manager at deploy time)
    │
    └── scripts/load_secrets.sh
          └── aws secretsmanager get-secret-value
                └── Writes to .env (chmod 600)
```

- Secrets stored in **AWS Secrets Manager**
- EC2 retrieves secrets via **IAM Instance Role** (no access keys needed)
- `scripts/load_secrets.sh` runs at deploy time to inject secrets into `.env`

## 3. Migration Steps

### Step 1: Create Secret in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name "bizi/production" \
  --description "Bizi production credentials" \
  --secret-string '{
    "MYSQL_HOST": "bizi-db.xxxxx.ap-northeast-2.rds.amazonaws.com",
    "MYSQL_USER": "bizi_admin",
    "MYSQL_PASSWORD": "ACTUAL_PASSWORD",
    "JWT_SECRET_KEY": "ACTUAL_JWT_KEY",
    "OPENAI_API_KEY": "sk-xxx",
    "GOOGLE_CLIENT_ID": "xxx.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "GOCSPX-xxx",
    "RAG_API_KEY": "ACTUAL_RAG_KEY",
    "CHROMA_AUTH_TOKEN": "ACTUAL_CHROMA_TOKEN",
    "RUNPOD_API_KEY": "rpa_xxx",
    "RUNPOD_ENDPOINT_ID": "xxx"
  }' \
  --region ap-northeast-2
```

### Step 2: Create IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:bizi/production-*"
    }
  ]
}
```

```bash
aws iam create-policy \
  --policy-name BiziFetchSecrets \
  --policy-document file://bizi-secrets-policy.json

# Attach to EC2 instance role
aws iam attach-role-policy \
  --role-name Bizi-EC2-Role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/BiziFetchSecrets
```

### Step 3: Deploy with Secret Injection

```bash
# On EC2 instance
cd /opt/bizi

# Load secrets from AWS Secrets Manager into .env
./scripts/load_secrets.sh bizi/production

# Verify .env
python scripts/validate_env.py --production

# Deploy
docker compose -f docker-compose.prod.yaml up -d --build
```

## 4. Secret Rotation

```bash
# Update a specific key
aws secretsmanager put-secret-value \
  --secret-id "bizi/production" \
  --secret-string '{ ... updated values ... }' \
  --region ap-northeast-2

# Redeploy
./scripts/load_secrets.sh bizi/production
docker compose -f docker-compose.prod.yaml up -d
```

## 5. Interim Measures (Implemented in Phase 5)

Until full migration to Secrets Manager, these measures reduce risk:

| Measure | Description |
|---------|-------------|
| `hide_parameters=True` | SQLAlchemy error logs no longer expose DB password |
| Production validators | Backend + RAG refuse to start without required secrets |
| ChromaDB auth token | Vector DB protected by token authentication |
| Container security | `no-new-privileges`, `read_only`, `tmpfs` |
| `validate_env.py` | Pre-deploy check for missing/placeholder values |
| `load_secrets.sh` | Helper script for Secrets Manager integration |

## 6. Rollback

If Secrets Manager is unavailable, fall back to manual `.env`:
1. Ensure `.env` file exists with all required variables
2. Run `python scripts/validate_env.py --production`
3. Deploy normally with `docker compose up`
