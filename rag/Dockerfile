# RAG Service Dockerfile
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system build tools + 한글 폰트 (PDF 생성용)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
