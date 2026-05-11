FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=main.settings.local \
    TZ=UTC

# 換成台灣 mirror 避免 archive.ubuntu.com / security.ubuntu.com 慢
RUN sed -i 's|http://archive.ubuntu.com|http://tw.archive.ubuntu.com|g; s|http://security.ubuntu.com|http://tw.archive.ubuntu.com|g' /etc/apt/sources.list \
    && apt-get -o Acquire::http::Timeout=15 -o Acquire::https::Timeout=15 update \
    && apt-get install -y --no-install-recommends \
      python3.10 \
      python3-pip \
      curl \
      libgl1 \
      libglib2.0-0 \
      libatomic1 \
      tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements/base.txt /app/requirements/
RUN pip install --upgrade pip --no-cache-dir && \
    pip install --no-cache-dir -r /app/requirements/base.txt && \
    pip install --no-cache-dir tzdata

COPY . /app

EXPOSE 8000

CMD ["daphne", "main.asgi:application", "-b", "0.0.0.0", "-p", "8000"]
