from django.conf import settings
from django.db import models


class Habit(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="habits",
    )
    place = models.CharField(max_length=255, verbose_name="Место")
    time = models.TimeField(verbose_name="Время выполнения")
    action = models.CharField(max_length=255, verbose_name="Действие")
    is_pleasant = models.BooleanField(
        default=False, verbose_name="Признак приятной привычки"
    )
    related_habit = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Связанная привычка",
        related_name="useful_habits",
    )
    periodicity = models.PositiveSmallIntegerField(
        default=1, verbose_name="Периодичность (в днях)"
    )
    reward = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Вознаграждение"
    )
    duration = models.PositiveSmallIntegerField(
        verbose_name="Время на выполнение (секунды)",
        help_text=(
            "Время, которое предположительно потратит пользователь на выполнение "
            "привычки (не более 120 секунд)"
        ),
    )
    is_public = models.BooleanField(default=False, verbose_name="Признак публичности")
    telegram_chat_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID чата Telegram для уведомлений",
        help_text="ID чаta Telegram для отправки напоминаний о привычке.",
    )
    last_notification_sent = models.DateTimeField(
        null=True, blank=True, verbose_name="Время последней отправки уведомления"
    )
    last_completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Время последнего выполнения"
    )

    class Meta:
        verbose_name = "Привычка"
        verbose_name_plural = "Привычки"
        ordering = ["time"]

    def __str__(self):
        return f"Я буду {self.action} в {self.time} в {self.place}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.reward and self.related_habit:
            raise ValidationError(
                "Нельзя одновременно выбрать вознаграждение и связанную привычку."
            )

        if self.is_pleasant:
            if self.reward or self.related_habit:
                raise ValidationError(
                    "Приятная привычка не может иметь вознаграждения или "
                    "связанной привычки."
                )

        if self.related_habit and not self.related_habit.is_pleasant:
            raise ValidationError(
                "В связанные привычки можно добавлять только приятные привычки."
            )

        if self.duration is not None and self.duration > 120:
            raise ValidationError(
                "Время на выполнение привычки не должно превышать 120 секунд."
            )
        if self.periodicity is not None and self.periodicity > 7:
            raise ValidationError(
                "Периодичность должна быть от 1 до 7 дней "
                "(нельзя выполнять привычку реже, "
                "чем 1 раз в 7 дней)."  # <-- Final fix for E501
            )


class NotificationLog(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, verbose_name="Привычка")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время отправки")
    message_content = models.TextField(verbose_name="Содержание сообщения")
    status = models.CharField(
        max_length=50, default="QUEUED", verbose_name="Статус отправки"
    )

    class Meta:
        verbose_name = "Лог уведомления"
        verbose_name_plural = "Логи уведомлений"
        ordering = ["-timestamp"]  # Сортировка по убыванию времени

    def __str__(self):
        return f"Уведомление для '{self.habit.action}' отправлено в {self.timestamp.strftime('%Y-%m-%d %H:%M')}"