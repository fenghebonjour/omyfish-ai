FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as root by default otherwise — a container breakout or dependency RCE would have full
# root inside the container for no benefit, since uvicorn doesn't need it to bind :8000
# (BACKLOG.md item G, WEAKNESS_AUDIT.md §1.4). The CLIP fish-gate downloads its weights to
# $HF_HOME at first startup (predictors/fish_gate.py), so the new user needs a writable
# cache dir, not just a writable home.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app \
    && mkdir -p /app/.cache && chown -R app:app /app
USER app
ENV HF_HOME=/app/.cache/huggingface

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
