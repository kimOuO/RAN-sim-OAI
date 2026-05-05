FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=main.settings.local \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.10 \
      python3-pip \
      curl \
      libgl1 \
      libxrender1 \
      libatomic1 \
      libglib2.0-0 \
      libssl3 \
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
