FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FIELDSHIFT_SQLITE_PATH=/app/state/fieldshift_analyses.db

WORKDIR /app

# Install minimal runtime OS libs used by scientific/geospatial wheels & TLS certs
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libexpat1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project code, knowledge base, schemas, frontend, and geospatial datasets
COPY . .

# Create non-root user and persistent writable state directory for SQLite
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --shell /bin/false --create-home appuser \
    && mkdir -p /app/state \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5); sys.exit(0 if r.status == 200 else 1)"

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
