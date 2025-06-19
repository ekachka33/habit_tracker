# habits/models.py
from django.db import models
from django.conf import settings # Импортируем settings для доступа к AUTH_USER_MODEL

class Habit(models.Model):
    # Пользователь - создатель привычки.
    # CASCADE означает, что если пользователь будет удален, то все его привычки тоже удалятся.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             verbose_name="Пользователь", related_name='habits')

    # Место - место, в котором необходимо выполнять привычку.
    place = models.CharField(max_length=255, verbose_name="Место")

    # Время - время, когда необходимо выполнять привычку.
    # Предполагаем, что это будет поле времени, без даты.
    time = models.TimeField(verbose_name="Время выполнения")

    # Действие - действие, которое представляет собой привычка.
    action = models.CharField(max_length=255, verbose_name="Действие")

    # Признак приятной привычки - привычка, которую можно привязать к выполнению полезной привычки.
    # Если True, это приятная привычка, которую нельзя выполнять с вознаграждением или другой связанной привычкой.
    is_pleasant = models.BooleanField(default=False, verbose_name="Признак приятной привычки")

    # Связанная привычка - привычка, которая связана с другой привычкой.
    # Важно указывать для полезных привычек, но не для приятных.
    # Может быть null для привычек, у которых нет связанной привычки.
    # Связана сама с собой (self-referential FK).
    # У связанной привычки обязательно должен быть is_pleasant=True.
    related_habit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name="Связанная привычка",
                                      related_name='useful_habits')

    # Периодичность (по умолчанию ежедневная) - периодичность выполнения привычки для напоминания в днях.
    # 1 - ежедневно, 2 - раз в 2 дня, ..., 7 - раз в 7 дней.
    periodicity = models.PositiveSmallIntegerField(default=1, verbose_name="Периодичность (в днях)")

    # Вознаграждение - чем пользователь должен себя вознаградить после выполнения.
    # Может быть null, если есть связанная привычка.
    reward = models.CharField(max_length=255, blank=True, null=True, verbose_name="Вознаграждение")

    # Время на выполнение - время, которое предположительно потратит пользователь на выполнение привычки.
    # Должно быть не больше 120 секунд.
    duration = models.PositiveSmallIntegerField(
        verbose_name="Время на выполнение (секунды)",
        help_text="Время, которое предположительно потратит пользователь на выполнение привычки (не более 120 секунд)"
    )

    # Признак публичности - привычки можно публиковать в общий доступ, чтобы другие пользователи могли брать в пример чужие привычки.
    is_public = models.BooleanField(default=False, verbose_name="Признак публичности")

    class Meta:
        verbose_name = "Привычка"
        verbose_name_plural = "Привычки"
        # Указываем порядок сортировки по умолчанию (например, по времени)
        ordering = ['time']

    def __str__(self):
        return f"Я буду {self.action} в {self.time} в {self.place}"

    def clean(self):
        # Валидатор: Исключить одновременный выбор связанной привычки и указания вознаграждения.
        # В модели не должно быть заполнено одновременно и поле вознаграждения, и поле связанной привычки.
        if self.reward and self.related_habit:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Нельзя одновременно выбрать вознаграждение и связанную привычку.'
            )

        # Валидатор: У приятной привычки не может быть вознаграждения или связанной привычки.
        if self.is_pleasant:
            if self.reward or self.related_habit:
                from django.core.exceptions import ValidationError
                raise ValidationError(
                    'Приятная привычка не может иметь вознаграждения или связанной привычки.'
                )

        # Валидатор: Время выполнения должно быть не больше 120 секунд.
        if self.time_to_complete > 120:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Время на выполнение привычки не должно превышать 120 секунд.'
            )

        # Валидатор: В связанные привычки могут попадать только привычки с признаком приятной привычки.
        if self.related_habit and not self.related_habit.is_pleasant:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'В связанные привычки можно добавлять только приятные привычки.'
            )

        # Валидатор: Нельзя выполнять привычку реже, чем 1 раз в 7 дней.
        if self.periodicity > 7:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                'Нельзя выполнять привычку реже, чем 1 раз в 7 дней.'
            )