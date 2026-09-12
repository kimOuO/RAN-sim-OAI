FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/ /app/requirements/
RUN pip install --upgrade pip && \
    pip install -r /app/requirements/local.txt

COPY . /app/

RUN mkdir -p /app/logs && chmod +x /app/shell/*.sh /app/manage.py

EXPOSE 8000

# ran-sim-protocol is mounted at /tmp/ran-sim-protocol by docker-compose;
# install it on container start so its venv has the latest source.
ENTRYPOINT ["/app/shell/entrypoint.sh"]
# daphne 跑 ASGI（HTTP + WebSocket 都支援，runserver 不支援 WebSocket）
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "main.asgi:application"]
