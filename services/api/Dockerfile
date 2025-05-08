# Build image for Flask API
FROM python:3.11-slim AS build
WORKDIR /src
COPY ../../requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn","-b","0.0.0.0:8080","app.app:app"]
