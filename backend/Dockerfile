FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

# OS-level packages required by weasyprint (PDF rendering engine) and related
# font/graphics libraries. Must come before pip install.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-noto \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/static ./static

COPY backend/docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

EXPOSE 8000

# One image: role chosen by APP_ROLE (web | worker). See docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
