#!/bin/sh
# RAGAS v4 evaluation runner
export EMBEDDING_PROVIDER=runpod
export RUNPOD_API_KEY=${RUNPOD_API_KEY:?"RUNPOD_API_KEY 환경변수를 설정하세요"}
export RUNPOD_ENDPOINT_ID=${RUNPOD_ENDPOINT_ID:?"RUNPOD_ENDPOINT_ID 환경변수를 설정하세요"}
export TOTAL_TIMEOUT=300
export LLM_TIMEOUT=120
export PYTHONUNBUFFERED=1

cd /app
python -u -m evaluation \
  --dataset /app/evaluation/ragas_dataset_v4.jsonl \
  --output /app/evaluation/results/ragas_v4_results_new.json \
  --timeout 300 \
  2>&1 | tee /app/evaluation/results/ragas_v4_run.log
