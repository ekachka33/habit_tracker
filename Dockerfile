# Используем официальный образ Python
FROM python:3.11-slim-buster


WORKDIR /app


ENV PYTHONUNBUFFERED 1


RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8000


CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]