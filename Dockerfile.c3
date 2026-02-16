FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    C3_PORT=8501 \
    C3_BIND_HOST=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

ARG Z1_MVP_REPO=https://github.com/Rin-Nomia/z1_mvp.git
ARG Z1_MVP_REF=main
RUN git clone --depth 1 --branch "${Z1_MVP_REF}" "${Z1_MVP_REPO}" /tmp/z1_mvp \
    && cp -r /tmp/z1_mvp/core /app/core \
    && rm -rf /tmp/z1_mvp

COPY c3_dashboard.py /app/c3_dashboard.py
COPY manage.py /app/manage.py
COPY c3_entrypoint.sh /app/c3_entrypoint.sh
COPY docs /app/docs

RUN chmod +x /app/c3_entrypoint.sh

EXPOSE 8501

CMD ["/app/c3_entrypoint.sh"]
