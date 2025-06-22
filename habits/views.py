# habits/views.py
from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from habits.models import Habit
from habits.serializers import HabitSerializer
from rest_framework.pagination import PageNumberPagination
from habits.permissions import IsOwner # Импортируем IsOwner
from rest_framework.decorators import action
from django.utils import timezone
from rest_framework.response import Response
from django.http import Http404 # Для обработки Habit.DoesNotExist


class HabitPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated, IsOwner] # Добавляем IsAuthenticated
    pagination_class = HabitPagination

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        # Возвращаем только привычки текущего аутентифицированного пользователя
        return Habit.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None): # ИЗМЕНЕНО: Имя метода должно быть 'complete'
        """
        Отмечает привычку как выполненную.
        При выполнении полезной привычки, связанная приятная привычка также считается выполненной.
        """
        try:
            # get_object() уже проверяет права доступа благодаря permission_classes
            habit = self.get_object()
        except Http404:
            return Response({"detail": "Привычка не найдена."}, status=status.HTTP_404_NOT_FOUND)

        # Проверяем, что это полезная привычка (не приятная)
        if habit.is_pleasant:
            return Response(
                {"detail": "Невозможно отметить приятную привычку как выполненную напрямую."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1. Отмечаем полезную привычку как выполненную
        habit.last_completed_at = timezone.now()
        habit.save()

        # 2. Если есть связанная приятная привычка, отмечаем и её
        if habit.related_habit:
            related_habit = habit.related_habit
            # Валидация в сериализаторе уже должна гарантировать, что related_habit.is_pleasant=True
            # Но можно оставить проверку как дополнительную меру
            if not related_habit.is_pleasant:
                 # Это сообщение, по идее, не должно быть достигнуто, если валидация в сериализаторе работает корректно
                return Response(
                    {"detail": "Связанная привычка должна быть приятной.",
                     "habit_id": habit.pk
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            related_habit.last_completed_at = timezone.now() # Обновляем время выполнения связанной привычки
            related_habit.save() # Сохраняем связанную привычку

            return Response(
                {"message": "Полезная привычка и связанная приятная привычка отмечены как выполненные.",
                 "habit_id": habit.pk,
                 "related_habit_id": related_habit.pk
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"message": "Привычка успешно отмечена как выполненная.",
                 "habit_id": habit.pk
                },
                status=status.HTTP_200_OK
            )


class PublicHabitListAPIView(generics.ListAPIView):
    serializer_class = HabitSerializer
    # Public habits доступны для просмотра всем аутентифицированным пользователям.
    permission_classes = [IsAuthenticated]
    pagination_class = HabitPagination

    def get_queryset(self):
        # Возвращаем только публичные привычки
        return Habit.objects.filter(is_public=True)