import os

import requests
from celery import shared_task
from django.utils import timezone
import time

@shared_task
def debug_task(message):
    """
    Простая тестовая Celery-задача, которая выводит сообщение.
    """
    print(f"[{timezone.now()}] Debug Task Received: {message}")
    time.sleep(5) # Имитация длительной операции
    print(f"[{timezone.now()}] Debug Task Finished for: {message}")
    return f"Task '{message}' completed successfully!"


@shared_task
def send_telegram_message(chat_id, message_text):
    """
    Отправляет сообщение в Telegram.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message_text
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status() # Вызывает исключение для ошибок HTTP (4xx или 5xx)
        print(f"Telegram message sent successfully! Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")