# ─────────────────────────────────────────────────────────────
#  services/api/Dockerfile   (simple, single-stage build)
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── install Python packages ──────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── copy Flask application code ──────────────────────────────
COPY app.py .

# ── launch Gunicorn on Cloud Run’s default port (8080) ───────
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
