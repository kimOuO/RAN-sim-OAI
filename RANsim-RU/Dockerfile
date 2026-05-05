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

# 共用 protocol package：build 前由 shell/init_project.sh 從 sibling 專案 rsync 到 _vendored/
COPY ./_vendored/ran-sim-protocol /opt/ran-sim-protocol

COPY requirements/ /app/requirements/
RUN pip install --upgrade pip && \
    pip install -r /app/requirements/base.txt

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "main.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "2"]
