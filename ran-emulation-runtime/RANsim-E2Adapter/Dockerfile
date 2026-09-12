FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# pysctp needs libsctp + headers; build-essential needed for compiling C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsctp-dev \
        libsctp1 \
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

CMD ["bash", "/app/shell/entrypoint.sh"]
