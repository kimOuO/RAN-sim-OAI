FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 把 ran-sim-protocol 一起拷進來(以便 -e 安裝)
# build context 預期是 /home/mitlab/XAPP_DT/(雙 repo 一起)
COPY Physics_sim/ran-sim-protocol /opt/ran-sim-protocol
COPY RANsim-DU /app

RUN sed -i 's|-e /home/mitlab/XAPP_DT/Physics_sim/ran-sim-protocol|-e /opt/ran-sim-protocol|' \
        /app/requirements/base.txt && \
    pip install --no-cache-dir -r /app/requirements/production.txt

EXPOSE 8000

CMD ["gunicorn", "main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
