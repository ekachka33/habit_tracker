# habits/serializers.py
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from habits.models import Habit
from habits.tasks import send_telegram_message # Убедитесь, что путь к вашей задаче корректен
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json
from django.utils import timezone
import datetime # Для создания объекта time

class HabitSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Habit.
    Используется для создания, обновления и отображения привычек.
    """
    class Meta:
        model = Habit
        fields = '__all__'
        read_only_fields = ('user',) # Пользователь устанавливается автоматически, поэтому он только для чтения

    def validate(self, data):
        # Получаем данные из 'data' или используем существующие значения для обновления
        # Используем .get() с дефолтом для новых объектов, и instance для существующих
        is_pleasant = data.get('is_pleasant', getattr(self.instance, 'is_pleasant', False))
        reward = data.get('reward', getattr(self.instance, 'reward', None))
        related_habit = data.get('related_habit', getattr(self.instance, 'related_habit', None))
        duration = data.get('duration', getattr(self.instance, 'duration', None))
        periodicity = data.get('periodicity', getattr(self.instance, 'periodicity', None))

        # --- Валидаторы ---
        # 1. Исключить одновременный выбор связанной привычки и указания вознаграждения.
        if reward and related_habit:
            raise ValidationError("Нельзя одновременно выбрать вознаграждение и связанную привычку.")

        # 2. Время выполнения должно быть не больше 120 секунд.
        if duration is not None and duration > 120:
            raise ValidationError("Время на выполнение привычки не должно превышать 120 секунд.")

        # 3. В связанные привычки могут попадать только привычки с признаком приятной привычки.
        if related_habit:
            # Если related_habit - это ID, нужно получить объект
            if isinstance(related_habit, int): # Если передан ID связанной привычки
                try:
                    related_habit_obj = Habit.objects.get(pk=related_habit)
                except Habit.DoesNotExist:
                    raise ValidationError("Связанная привычка не найдена.")
                if not related_habit_obj.is_pleasant: # Используем .is_pleasant
                    raise ValidationError("В связанные привычки можно добавлять только приятные привычки.")
            elif isinstance(related_habit, Habit): # Если уже объект
                if not related_habit.is_pleasant: # Используем .is_pleasant
                    raise ValidationError("В связанные привычки можно добавлять только приятные привычки.")


        # 4. У приятной привычки не может быть вознаграждения или связанной привычки.
        if is_pleasant: # Используем is_pleasant
            if reward or related_habit:
                raise ValidationError("Приятная привычка не может иметь вознаграждения или связанной привычки.")

        # 5. Нельзя выполнять привычку реже, чем 1 раз в 7 дней (и не чаще чем 1 раз в день).
        if periodicity is not None and not (1 <= periodicity <= 7):
            raise ValidationError("Периодичность должна быть от 1 до 7 дней (нельзя выполнять привычку реже, чем 1 раз в 7 дней).")

        # 6. Для полезной привычки (неприятной) должно быть либо вознаграждение, либо связанная привычка.
        if not is_pleasant and not reward and not related_habit:
            raise ValidationError("Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.")

        return data

    def create(self, validated_data):
        # Пользователь берется из контекста запроса
        validated_data['user'] = self.context['request'].user
        habit = super().create(validated_data)
        self.schedule_habit_notification(habit)
        return habit

    def update(self, instance, validated_data):
        habit = super().update(instance, validated_data)
        # Если изменились поля, влияющие на расписание, перепланируем задачу
        # Это включает time, periodicity, telegram_chat_id, is_pleasant
        if any(field in validated_data for field in ['time', 'periodicity', 'telegram_chat_id', 'is_pleasant']):
            self.reschedule_habit_notification(habit)
        return habit

    def schedule_habit_notification(self, habit: Habit):
        """
        Планирует периодическую задачу в Celery Beat для напоминания о привычке.
        """
        # Прежде чем планировать, убедимся, что это не приятная привычка
        # и что у пользователя есть chat_id для Telegram.
        if habit.is_pleasant or not habit.telegram_chat_id:
            # Удаляем любые старые задачи, если привычка стала приятной или потеряла chat_id
            PeriodicTask.objects.filter(name=f'habit-notification-{habit.id}').delete()
            return

        # Удаляем любые старые задачи для этой привычки перед созданием новой
        PeriodicTask.objects.filter(name=f'habit-notification-{habit.id}').delete()

        # Определяем расписание в зависимости от периодичности
        if habit.periodicity == 1: # Ежедневная привычка
            schedule, created = CrontabSchedule.objects.get_or_create(
                minute=habit.time.minute,
                hour=habit.time.hour,
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
            )

            # --- ДОБАВЛЯЕМ ЛОГИКУ ДЛЯ start_time В CRONTABSCHEDULE ---
            now = timezone.now()  # Получаем текущее UTC время
            # Комбинируем текущую дату с временем привычки
            start_time_today = now.replace(
                hour=habit.time.hour,
                minute=habit.time.minute,
                second=0,
                microsecond=0
            )

            # Если время привычки сегодня уже прошло, планируем на завтра
            if start_time_today < now:
                start_time_today += datetime.timedelta(days=1)

            periodic_task_kwargs = {
                'crontab': schedule,
                'start_time': start_time_today,
            }# Устанавливаем start_time

        else:  # Привычка с периодичностью > 1 (IntervalSchedule)
            interval, created = IntervalSchedule.objects.get_or_create(
                every=habit.periodicity,
                period=IntervalSchedule.DAYS,

            )

            # Указываем start_time, чтобы первое напоминание было в нужное время
            # Например, если привычка должна быть в 10:00, то задача начнется сегодня в 10:00
            now = timezone.now()
            start_time_today = now.replace(
                hour=habit.time.hour,
                minute=habit.time.minute,
                second=0,
                microsecond=0
            )

            # Если время сегодня уже прошло, планируем на завтра
            if start_time_today < now:
                start_time_today += datetime.timedelta(days=1)

            periodic_task_kwargs = {
                'interval': interval,
                'start_time': start_time_today,
            }

        # Создаем или обновляем периодическую задачу
        PeriodicTask.objects.create(
            **periodic_task_kwargs,
            name=f'habit-notification-{habit.id}', # Уникальное имя для каждой привычки
            task='habits.tasks.send_telegram_message',
            args=json.dumps([
                habit.telegram_chat_id,
                f'Привет! Напоминание: пора выполнить "{habit.action}" в {habit.place}!',
            ]),
            enabled=True, # Включаем задачу
            one_off=False, # Задача будет повторяющейся
        )
        print(f"Задача для привычки {habit.id} ('{habit.action}') запланирована.")

    def reschedule_habit_notification(self, habit: Habit):
        """
        Перепланирует задачу для привычки, удаляя старую и создавая новую.
        """
        self.schedule_habit_notification(habit)