# habits/serializers.py
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from habits.models import Habit

class HabitSerializer(serializers.ModelSerializer):
    """
    Сериализатор для модели Habit.
    Используется для создания, обновления и отображения привычек.
    """
    class Meta:
        model = Habit
        fields = '__all__'
        # *** ДОБАВЬТЕ ЭТУ СТРОКУ ***
        read_only_fields = ('user',) # Пользователь устанавливается автоматически, поэтому он только для чтения

    def validate(self, data):
        # ... (ваш текущий код валидации) ...

        # Получаем данные из 'data' или используем существующие значения, если это обновление
        is_pleasant_habit = data.get('is_pleasant_habit', self.instance.is_pleasant_habit if self.instance else False)
        reward = data.get('reward', self.instance.reward if self.instance else None)
        related_habit = data.get('related_habit', self.instance.related_habit if self.instance else None)
        # Убедитесь, что здесь используется 'duration', а не 'time_to_complete'
        duration = data.get('duration', self.instance.duration if self.instance else None)
        periodicity = data.get('periodicity', self.instance.periodicity if self.instance else None)

        # Валидатор 1: Исключить одновременный выбор связанной привычки и указания вознаграждения.
        if reward and related_habit:
            raise ValidationError("Нельзя одновременно выбрать вознаграждение и связанную привычку.")

        # Валидатор 2: Время выполнения должно быть не больше 120 секунд.
        # Убедитесь, что здесь используется 'duration'
        if duration is not None and duration > 120:
            raise ValidationError("Время на выполнение привычки не должно превышать 120 секунд.")

        # Валидатор 3: В связанные привычки могут попадать только привычки с признаком приятной привычки.
        if related_habit:
            if not related_habit.is_pleasant_habit:
                raise ValidationError("В связанные привычки можно добавлять только приятные привычки.")

        # Валидатор 4: У приятной привычки не может быть вознаграждения или связанной привычки.
        if is_pleasant_habit:
            if reward or related_habit:
                raise ValidationError("Приятная привычка не может иметь вознаграждения или связанной привычки.")

        # Валидатор 5: Нельзя выполнять привычку реже, чем 1 раз в 7 дней.
        if periodicity is not None and periodicity > 7:
            raise ValidationError("Нельзя выполнять привычку реже, чем 1 раз в 7 дней.")

        # Валидатор 6: Для полезной привычки (неприятной) должно быть либо вознаграждение, либо связанная привычка.
        if not is_pleasant_habit and not reward and not related_habit:
            raise ValidationError("Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.")

        return data