FROM python:3.11-slim-bookworm
RUN pip install --no-cache-dir telnetlib3==2.0.4 httpx==0.27.2
COPY facade.py /app/facade.py
WORKDIR /app
CMD ["python3", "facade.py"]
