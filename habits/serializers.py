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
        read_only_fields = ('user',)  # Пользователь устанавливается автоматически, не должен быть доступен для записи

    def validate(self, data):
        # Получаем текущие значения или значения из instance для полей,
        # которые могли не быть переданы при частичном обновлении.
        is_pleasant = data.get('is_pleasant', getattr(self.instance, 'is_pleasant', False))
        reward = data.get('reward', getattr(self.instance, 'reward', None))
        related_habit = data.get('related_habit', getattr(self.instance, 'related_habit', None))
        duration = data.get('duration', getattr(self.instance, 'duration', None))
        periodicity = data.get('periodicity', getattr(self.instance, 'periodicity', None))

        # Валидация 1: Нельзя одновременно выбрать вознаграждение и связанную привычку.
        if reward and related_habit:
            raise ValidationError("Нельзя одновременно выбрать вознаграждение и связанную привычку.")

        # Валидация 2: Время на выполнение привычки не должно превышать 120 секунд.
        if duration is not None and duration > 120:
            raise ValidationError({"duration": "Время на выполнение привычки не должно превышать 120 секунд."})

        # Валидация 3: Обработка связанной привычки
        if related_habit:
            # Если related_habit передана как PK, нужно получить объект
            # Это происходит при создании или обновлении, когда related_habit - это int
            if isinstance(related_habit, int):
                try:
                    related_habit_obj = Habit.objects.get(pk=related_habit)
                except Habit.DoesNotExist:
                    raise ValidationError({"related_habit": "Связанная привычка не найдена."})
                # После получения объекта, используем его для дальнейшей проверки
                related_habit = related_habit_obj

            # Проверяем, является ли связанная привычка приятной
            if not related_habit.is_pleasant:
                raise ValidationError(
                    {"related_habit": "В связанные привычки можно добавлять только приятные привычки."})

        # Валидация 4: Приятная привычка не может иметь вознаграждения или связанной привычки.
        if is_pleasant:
            if reward or related_habit:
                raise ValidationError("Приятная привычка не может иметь вознаграждения или связанной привычки.")

        # Валидация 5: Периодичность должна быть от 1 до 7 дней.
        if periodicity is not None and not (1 <= periodicity <= 7):
            raise ValidationError({"periodicity": "Периодичность должна быть от 1 до 7 дней."})

        # Валидация 6: Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.
        if not is_pleasant and not reward and not related_habit:
            raise ValidationError(
                "Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.")

        return data

    def create(self, validated_data):
        # Пользователь устанавливается автоматически через perform_create в HabitViewSet
        # validated_data['user'] = self.context['request'].user # Закомментировано как избыточное
        habit = super().create(validated_data)
        return habit

    def update(self, instance, validated_data):
        habit = super().update(instance, validated_data)
        return habit
