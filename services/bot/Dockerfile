FROM python:3.11-slim
WORKDIR /bot
COPY ../../requirements.txt .
RUN pip install -r requirements.txt
COPY discord_bot.py .
ENV PYTHONUNBUFFERED=1
CMD ["python","discord_bot.py"]
