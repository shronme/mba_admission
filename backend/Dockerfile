FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/static ./static

EXPOSE 8000

# Railway will typically override this with process-specific start commands.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

