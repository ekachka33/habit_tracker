from celery import shared_task
from habits.models import Habit, NotificationLog  # Импортируем новую модель
from django.utils import timezone
from datetime import timedelta, datetime
import logging
import os
from telegram import Bot  # Импортируем Bot здесь

logger = logging.getLogger(__name__)

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


@shared_task(bind=True)
def _send_telegram_message_async_wrapper(self, chat_id, message_text, notification_log_id=None):
    """
    Асинхронная обертка для отправки Telegram сообщения.
    Используется как Celery задача, чтобы не блокировать основной поток.
    Также обновляет статус лога уведомлений и last_notification_sent привычки.
    """
    notification_log = None
    if notification_log_id:
        try:
            notification_log = NotificationLog.objects.get(id=notification_log_id)
        except NotificationLog.DoesNotExist:
            logger.error(f"NotificationLog с ID {notification_log_id} не найден.")
            # Продолжаем без обновления лога, но с логгированием ошибки

    try:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен в переменных окружения.")

        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        bot.send_message(chat_id=chat_id, text=message_text)
        logger.info(f"Сообщение успешно отправлено в чат {chat_id}: {message_text}")
        if notification_log:
            notification_log.status = 'SENT'
            notification_log.save()
            logger.info(f"Статус NotificationLog {notification_log_id} обновлен на SENT.")

            # Обновляем last_notification_sent только после УСПЕШНОЙ отправки
            habit = notification_log.habit  # Получаем привычку через related_name
            habit.last_notification_sent = timezone.now()
            habit.save()
            logger.info(f"last_notification_sent для привычки {habit.id} обновлено после успешной отправки.")

    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram чат {chat_id}: {e}")
        if notification_log:
            notification_log.status = 'FAILED'
            notification_log.save()
            logger.error(f"Статус NotificationLog {notification_log_id} обновлен на FAILED.")
        # Можно добавить логику повторной попытки
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task
def send_telegram_notification(habit_id):
    """
    Отправляет уведомление о привычке в Telegram.
    Создает запись в NotificationLog.
    last_notification_sent будет обновлено в _send_telegram_message_async_wrapper после успешной отправки.
    """
    try:
        habit = Habit.objects.get(id=habit_id)
    except Habit.DoesNotExist:
        logger.warning(f"Привычка с ID {habit_id} не найдена для отправки уведомления.")
        return

    if not habit.telegram_chat_id:
        logger.info(f"У привычки ID {habit_id} нет связанного Telegram Chat ID. Уведомление не отправлено.")
        return

    if habit.is_pleasant:
        logger.info(
            f"Привычка {habit.action} (ID: {habit_id}) является приятной. Напоминания для приятных привычек не отправляются.")
        return

    message_text = f"Напоминание о привычке: '{habit.action}' в '{habit.place}' в {habit.time.strftime('%H:%M')}!"

    # Создаем запись в NotificationLog со статусом QUEUED
    notification_log = NotificationLog.objects.create(
        habit=habit,
        message_content=message_text,
        status='QUEUED'
    )
    logger.info(f"Запись NotificationLog {notification_log.id} создана со статусом QUEUED.")

    # Передаем ID лога в асинхронную обертку
    _send_telegram_message_async_wrapper.delay(
        chat_id=habit.telegram_chat_id,
        message_text=message_text,
        notification_log_id=notification_log.id
    )
    # last_notification_sent теперь обновляется в _send_telegram_message_async_wrapper после успешной отправки


@shared_task
def check_and_send_habit_reminders():
    """
    Проверяет все полезные привычки и ставит в очередь задачи по отправке напоминаний,
    если пришло время и привычка не была отправлена сегодня.
    """
    now = timezone.now()
    current_time = now.time()
    current_date = now.date()

    logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Запуск проверки привычек для напоминаний ({now.tzinfo}).")

    # Получаем только полезные привычки с указанным telegram_chat_id
    habits_to_check = Habit.objects.filter(is_pleasant=False).exclude(telegram_chat_id__exact='')

    for habit in habits_to_check:
        habit.refresh_from_db()  # Убедимся, что объект привычки содержит самые свежие данные из БД

        # Проверяем, пришло ли время для отправки сегодня
        if habit.time <= current_time:
            # Проверяем, когда было отправлено последнее уведомление
            if habit.last_notification_sent:
                days_since_last_notification = (current_date - habit.last_notification_sent.date()).days

                # Если привычка была отправлена сегодня, пропускаем
                if habit.last_notification_sent.date() == current_date:
                    logger.info(
                        f"[{current_time.strftime('%H:%M')}] Привычка {habit.id} ({habit.action}): Уже отправлено сегодня. Пропускаем.")
                    continue

                # Если периодичность позволяет, и прошло достаточно дней
                if days_since_last_notification >= habit.periodicity:
                    logger.info(
                        f"[{current_time.strftime('%H:%M')}] Привычка {habit.id} ({habit.action}): Пришло время и прошло {days_since_last_notification} дней. Отправляем.")
                    send_telegram_notification.delay(habit.id)
                else:
                    logger.info(
                        f"[{current_time.strftime('%H:%M')}] Привычка {habit.id} ({habit.action}): Время пришло, но не прошло достаточно дней с последнего уведомления ({days_since_last_notification}/{habit.periodicity}). Пропускаем.")
            else:
                # Если уведомления еще не было, отправляем (первое уведомление)
                logger.info(
                    f"[{current_time.strftime('%H:%M')}] Привычка {habit.id} ({habit.action}): Первое уведомление. Отправляем.")
                send_telegram_notification.delay(habit.id)
        else:
            logger.info(
                f"[{current_time.strftime('%H:%M')}] Привычка {habit.id} ({habit.action}): Время еще не пришло сегодня ({habit.time.strftime('%H:%M')}). Пропускаем.")
