# RAG Service Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system build tools (required for C extension compilation)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download bge-m3 embedding model into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# Copy source code
COPY . .

# Expose port
EXPOSE 8001

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
