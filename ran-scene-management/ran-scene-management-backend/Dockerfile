FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements/ /app/requirements/
RUN pip install --upgrade pip && pip install -r /app/requirements/local.txt
COPY . /app/
RUN mkdir -p /app/logs /app/assets && chmod +x /app/shell/*.sh /app/manage.py
EXPOSE 8000
ENTRYPOINT ["/app/shell/entrypoint.sh"]
CMD ["gunicorn", "main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
