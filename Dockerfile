# Используем официальный образ Python
FROM python:3.11-slim-buster

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл requirements.txt в рабочую диреторию
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта в рабочую диреторию
COPY . .

# Открываем порт, на котором будет работать Django-приложение
EXPOSE 8000

# Команда по умолчанию для запуска приложения (может быть переопределена в docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]