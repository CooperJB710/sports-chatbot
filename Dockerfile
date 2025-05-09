FROM python:3.11-slim AS build
WORKDIR /app

# 1 – copy ONLY files that really exist inside services/api/
COPY requirements.txt .

RUN pip install --user -r requirements.txt

# 2 – copy the rest of the source (again, only local)
COPY . .

# --- runtime stage -------------------------------------------------
FROM python:3.11-slim
WORKDIR /app
COPY --from=build /root/.local /root/.local
COPY --from=build /app /app

ENV PATH="/root/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1

CMD ["gunicorn", "-b", "0.0.0.0:8080", "app.app:app"]
