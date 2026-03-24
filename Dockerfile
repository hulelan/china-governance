FROM python:3.12-slim

WORKDIR /app

# Cache-bust: 2026-03-24-v2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip show jinja2 | grep Version && \
    pip show starlette | grep Version

COPY . .

CMD uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000}
