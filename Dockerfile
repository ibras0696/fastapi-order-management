FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .

RUN chmod +x scripts/entrypoint_web.sh scripts/entrypoint_worker_noop.sh \
  && chmod +x scripts/test_api_curl.sh scripts/test_api_curl_full.sh scripts/test_event_flow.sh

RUN groupadd -g 1000 app && useradd -m -u 1000 -g 1000 app \
  && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
