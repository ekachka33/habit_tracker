# habits/views.py
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated # Для ограничения доступа
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


class HabitCreateAPIView(generics.CreateAPIView):
    """
    Создание новой привычки.
    Доступно только авторизованным пользователям.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """
        Автоматически устанавливает текущего пользователя как создателя привычки.
        """
        serializer.save(user=self.request.user)


class HabitListAPIView(generics.ListAPIView):
    """
    Список привычек текущего пользователя с пагинацией.
    Доступно только авторизованным пользователям.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HabitPagination # Применяем нашу пагинацию

    def get_queryset(self):
        """
        Возвращает только привычки текущего авторизованного пользователя.
        """
        return Habit.objects.filter(user=self.request.user)


class HabitPublicListAPIView(generics.ListAPIView):
    """
    Список публичных привычек с пагинацией.
    Доступно всем (даже неавторизованным пользователям).
    """
    serializer_class = HabitSerializer
    # permission_classes не указан, значит, по умолчанию Public
    pagination_class = HabitPagination # Применяем нашу пагинацию

    def get_queryset(self):
        """
        Возвращает только публичные привычки.
        """
        return Habit.objects.filter(is_public=True)


class HabitRetrieveAPIView(generics.RetrieveAPIView):
    """
    Просмотр одной привычки.
    Доступно только владельцу привычки.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    queryset = Habit.objects.all() # queryset должен быть определен для Retrieve
    lookup_field = 'pk' # Использование первичного ключа для поиска

    def get_queryset(self):
        """
        Разрешает просмотр только собственных привычек.
        """
        return Habit.objects.filter(user=self.request.user)


class HabitUpdateAPIView(generics.UpdateAPIView):
    """
    Редактирование привычки.
    Доступно только владельцу привычки.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    queryset = Habit.objects.all()
    lookup_field = 'pk'

    def get_queryset(self):
        """
        Разрешает редактирование только собственных привычек.
        """
        return Habit.objects.filter(user=self.request.user)


class HabitDestroyAPIView(generics.DestroyAPIView):
    """
    Удаление привычки.
    Доступно только владельцу привычки.
    """
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    queryset = Habit.objects.all()
    lookup_field = 'pk'

    def get_queryset(self):
        """
        Разрешает удаление только собственных привычек.
        """
        return Habit.objects.filter(user=self.request.user)

