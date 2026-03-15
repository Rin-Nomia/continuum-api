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

# Keep deployment path consistent with Dockerfile.api:
# always sync core/pipeline/configs from z1-mvp.
ARG Z1_MVP_REPO=https://github.com/Rin-Nomia/z1_mvp.git
ARG Z1_MVP_REF=main
RUN git clone --depth 1 --branch "${Z1_MVP_REF}" "${Z1_MVP_REPO}" /tmp/z1_mvp \
    && cp -r /tmp/z1_mvp/core /app/core \
    && cp -r /tmp/z1_mvp/pipeline /app/pipeline \
    && cp -r /tmp/z1_mvp/configs /app/configs \
    && rm -rf /tmp/z1_mvp

COPY app.py /app/app.py
COPY logger.py /app/logger.py
COPY status.html /app/status.html
RUN mkdir -p /app/docs
COPY docs /app/docs
RUN mkdir -p /app/license
COPY license /app/license

EXPOSE 7860

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${API_PORT}"]
