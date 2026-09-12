FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=main.settings.local \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      curl \
      tzdata \
      && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
      && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 共用 protocol package(2026-09-12 重構:改 root build context 直接 COPY,不再 rsync 到 _vendored/)
COPY ran-emulation-runtime/ran-emulation-runtime-interface-protocol /opt/ran-sim-protocol

COPY ran-emulation-runtime/RANsim-RU/requirements/ /app/requirements/
RUN pip install --upgrade pip && \
    pip install -r /app/requirements/base.txt

COPY ran-emulation-runtime/RANsim-RU /app

EXPOSE 8000

# entrypoint 會先跑 migrate 再 exec CMD
RUN chmod +x /app/shell/entrypoint.sh
ENTRYPOINT ["/app/shell/entrypoint.sh"]

CMD ["gunicorn", "main.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "2"]
