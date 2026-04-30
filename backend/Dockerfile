FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ ffmpeg curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY download_model.py /tmp/download_model.py
COPY models/large-v3 /app/.cache/huggingface/hub/models--Systran--faster-whisper-large-v3/snapshots/main

COPY . .
RUN mkdir -p /tmp/uploads

ENV HF_HUB_CACHE=/app/.cache/huggingface/hub
ENV HF_HUB_LOCAL_FILES_ONLY=1

RUN useradd -m appuser && chown -R appuser:appuser /app /tmp/uploads
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
