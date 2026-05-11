FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /data \
    && chown -R app:app /app /data

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN pip install --upgrade pip && pip install .

USER app

CMD ["uvicorn", "line_alive_check_bot.main:app", "--host", "0.0.0.0", "--port", "8000"]
