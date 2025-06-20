import os

from celery import shared_task
from django.utils import timezone
import time
import asyncio
import telegram

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
    Отправляет сообщение в Telegram с использованием python-telegram-bot.
    Запускает асинхронную функцию внутри синхронной Celery-задачи.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN не найден в переменных окружения. Сообщение не отправлено.")
        return False

    # Асинхронная функция для отправки сообщения
    async def _send_message_async():
        try:
            bot = telegram.Bot(token=bot_token)
            await bot.send_message(chat_id=chat_id, text=message_text) # <-- Здесь используется await
            print(f"Сообщение успешно отправлено в Telegram. Chat ID: {chat_id}, Message: {message_text}")
            return True
        except telegram.error.TelegramError as e:
            print(f"Ошибка Telegram API при отправке сообщения: {e}")
            return False
        except Exception as e:
            print(f"Неизвестная ошибка при отправке сообщения в Telegram: {e}")
            return False

    # Запускаем асинхронную функцию
    return asyncio.run(_send_message_async())