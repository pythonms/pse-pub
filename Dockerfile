FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir "fastapi>=0.110.0" "uvicorn[standard]>=0.28.0" \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY main.py __version__.py ./

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
