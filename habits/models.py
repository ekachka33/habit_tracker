from django.db import models
from django.conf import settings
# Удаляем импорт MaxValueValidator, так как он больше не будет использоваться для этих полей
# from django.core.validators import MaxValueValidator
from django.utils import timezone


class Habit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="Пользователь", related_name='habits')
    place = models.CharField(max_length=255, verbose_name="Место")
    time = models.TimeField(verbose_name="Время выполнения")
    action = models.CharField(max_length=255, verbose_name="Действие")
    is_pleasant = models.BooleanField(default=False, verbose_name="Признак приятной привычки")
    related_habit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name="Связанная привычка",
                                      related_name='useful_habits')
    periodicity = models.PositiveSmallIntegerField(
        default=1,
        # УДАЛЕНО: validators=[MaxValueValidator(7)], # Убрали, т.к. валидация в сериализаторе
        verbose_name="Периодичность (в днях)"
    )
    reward = models.CharField(max_length=255, blank=True, null=True, verbose_name="Вознаграждение")
    duration = models.PositiveSmallIntegerField(
        # УДАЛЕНО: validators=[MaxValueValidator(120)], # Убрали, т.к. валидация в сериализаторе
        verbose_name="Время на выполнение (секунды)",
        help_text="Время, которое предположительно потратит пользователь на выполнение привычки (не более 120 секунд)"
    )
    is_public = models.BooleanField(default=False, verbose_name="Признак публичности")
    telegram_chat_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID чата Telegram для уведомлений",
        help_text="ID чата Telegram для отправки напоминаний о привычке."
    )
    last_notification_sent = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Время последней отправки уведомления'
    )
    last_completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Время последнего выполнения'
    )

    class Meta:
        verbose_name = "Привычка"
        verbose_name_plural = "Привычки"
        ordering = ['time']

    def __str__(self):
        return f"Я буду {self.action} в {self.time} в {self.place}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.reward and self.related_habit:
            raise ValidationError(
                'Нельзя одновременно выбрать вознаграждение и связанную привычку.'
            )

        if self.is_pleasant:
            if self.reward or self.related_habit:
                raise ValidationError(
                    'Приятная привычка не может иметь вознаграждения или связанной привычки.'
                )

        if self.related_habit and not self.related_habit.is_pleasant:
            raise ValidationError(
                'В связанные привычки можно добавлять только приятные привычки.'
            )

        if self.duration is not None and self.duration > 120:
             raise ValidationError(
                 'Время на выполнение привычки не должно превышать 120 секунд.'
             )
        if self.periodicity is not None and self.periodicity > 7:
             raise ValidationError(
                 'Периодичность должна быть от 1 до 7 дней (нельзя выполнять привычку реже, чем 1 раз в 7 дней).'
             )
