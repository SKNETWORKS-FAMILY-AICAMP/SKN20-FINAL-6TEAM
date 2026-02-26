# ChromaDB with pre-loaded vector data
FROM chromadb/chroma:1.5.0

# Copy backup archive and extract into ChromaDB data directory
COPY chromadb_backup.tar.gz /tmp/chromadb_backup.tar.gz
RUN mkdir -p /data && \
    tar -xzf /tmp/chromadb_backup.tar.gz -C /data && \
    rm /tmp/chromadb_backup.tar.gz
