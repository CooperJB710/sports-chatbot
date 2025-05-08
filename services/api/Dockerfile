# ────────────────────────────────────────────────────────────────
#  Build stage – install Python deps in a throw-away layer
# ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS build
WORKDIR /src

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy the real Flask application package from the repo root.
# The build-context is “services/api”, so two “..” go back to the repo root.
COPY ../../app /src/app

# ────────────────────────────────────────────────────────────────
#  Runtime stage – just the app + wheels, nothing else
# ────────────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# wheel cache from the first stage
COPY --from=build /root/.local /root/.local
# Flask code
COPY --from=build /src/app /app/app

ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Gunicorn entry-point
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app.app:app"]
