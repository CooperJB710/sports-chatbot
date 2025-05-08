FROM python:3.11-slim
WORKDIR /job
COPY ../../requirements.txt .
RUN pip install -r requirements.txt
COPY run_etl.py .
ENTRYPOINT ["python","run_etl.py","2024"]
