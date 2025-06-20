# habits/views.py
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated # Убрали AllowAny, если хотим только для аутентифицированных
from habits.models import Habit
from habits.serializers import HabitSerializer
from rest_framework.pagination import PageNumberPagination
from habits.permissions import IsOwner # Импортируем IsOwner из habits/permissions.py

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
    # Применяем IsOwner, чтобы гарантировать, что только владелец может выполнять CRUD
    # IsAuthenticated уже включен в общие настройки DEFAULT_PERMISSION_CLASSES
    # или его можно явно указать, если DEFAULT_PERMISSION_CLASSES отсутствует.
    # Если DEFAULT_PERMISSION_CLASSES = [IsAuthenticated], то здесь достаточно [IsOwner]
    permission_classes = [IsOwner]
    pagination_class = HabitPagination

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_queryset(self):
        # ViewSet теперь отвечает только за "мои" привычки (CRUD)
        # Этот queryset сам по себе уже фильтрует по владельцу.
        return Habit.objects.filter(user=self.request.user)

class PublicHabitListAPIView(generics.ListAPIView):
    """
    Список публичных привычек с пагинацией.
    Доступно только аутентифицированным пользователям для просмотра.
    """
    serializer_class = HabitSerializer
    # Только аутентифицированные пользователи могут видеть публичные привычки.
    # Права на просмотр самих объектов будут определяться их is_public=True
    permission_classes = [IsAuthenticated]
    pagination_class = HabitPagination

    def get_queryset(self):
        return Habit.objects.filter(is_public=True)