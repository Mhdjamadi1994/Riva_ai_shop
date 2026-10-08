FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN groupadd --system app && useradd --system --gid app --home-dir /app app \
    && mkdir -p /app/data /app/beat /app/backups /app/staticfiles \
    && chown -R app:app /app/data /app/beat /app/backups /app/staticfiles

RUN DEBUG=True SECRET_KEY=build-only-staticfiles-key python manage.py collectstatic --noinput

USER app

EXPOSE 10000
