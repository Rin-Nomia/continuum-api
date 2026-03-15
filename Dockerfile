FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    API_PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY logger.py /app/logger.py
COPY status.html /app/status.html
COPY core /app/core
COPY pipeline /app/pipeline
COPY configs /app/configs

RUN mkdir -p /app/docs
RUN mkdir -p /app/license

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${API_PORT}"]
