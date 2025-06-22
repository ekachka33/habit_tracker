from celery import shared_task
from habits.models import Habit
from django.utils import timezone
from datetime import timedelta, datetime
import logging
from telegram import Bot  # Импортируем Bot здесь

logger = logging.getLogger(__name__)

# Замените 'YOUR_TELEGRAM_BOT_TOKEN' на ваш фактический токен бота
# Лучше получать его из переменных окружения или настроек Django
# Например, из settings.py: TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# Для простоты примера оставим так, но в реальном проекте используйте безопасное хранение.
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # ЗАМЕНИТЕ НА ВАШ ТОКЕН БОТА


@shared_task(bind=True)
def _send_telegram_message_async_wrapper(self, chat_id, message_text):
    """
    Асинхронная обертка для отправки Telegram сообщения.
    Используется как Celery задача, чтобы не блокировать основной поток.
    """
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)  # Инициализируем бота внутри задачи
        bot.send_message(chat_id=chat_id, text=message_text)
        logger.info(f"Сообщение успешно отправлено в чат {chat_id}: {message_text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram чат {chat_id}: {e}")
        # Можно добавить логику повторной попытки
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task
def send_telegram_notification(habit_id):
    """
    Отправляет уведомление о привычке в Telegram и обновляет last_notification_sent.
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
    _send_telegram_message_async_wrapper.delay(chat_id=habit.telegram_chat_id, message_text=message_text)

    # Обновляем last_notification_sent только после успешной постановки в очередь
    habit.last_notification_sent = timezone.now()
    habit.save()
    logger.info(f"Уведомление для привычки {habit.id} поставлено в очередь и время обновления записано.")


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
        # ОБНОВЛЕНИЕ: Убедимся, что объект привычки содержит самые свежие данные из БД
        habit.refresh_from_db()  # Это критически важно для тестов!

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
