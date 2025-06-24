# backend/Dockerfile.prod - For GGUF model
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl wget git gcc g++ cmake \
    && rm -rf /var/lib/apt/lists/*

# Install requirements for GGUF model
COPY requirements-gguf.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-gguf.txt

# Copy your GGUF model file
COPY models/ /app/models/

# Copy application code
COPY . .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

ENV MODEL_PATH=/app/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
ENV MODEL_TYPE=gguf
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

HEALTHCHECK --interval=60s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]