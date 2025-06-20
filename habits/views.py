# habits/views.py
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, AllowAny # AllowAny для публичных привычек
from habits.models import Habit
from habits.serializers import HabitSerializer
from rest_framework.pagination import PageNumberPagination

class HabitPagination(PageNumberPagination):
    """
    Пагинация для списка привычек.
    Выводит по 5 привычек на страницу.
    """
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100

class HabitViewSet(viewsets.ModelViewSet):
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HabitPagination # Применяем пагинацию к ViewSet

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        # ViewSet теперь отвечает только за "мои" привычки (CRUD)
        return Habit.objects.filter(user=self.request.user)

class HabitPublicListAPIView(generics.ListAPIView):
    """
    Список публичных привычек с пагинацией.
    Доступно всем (даже неавторизованным пользователям).
    """
    serializer_class = HabitSerializer
    permission_classes = [AllowAny] # Разрешаем доступ всем
    pagination_class = HabitPagination

    def get_queryset(self):
        return Habit.objects.filter(is_public=True)