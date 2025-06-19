# users/views.py
from rest_framework import generics
from rest_framework.permissions import AllowAny # Разрешаем доступ без аутентификации
from users.serializers import UserRegisterSerializer

class UserRegisterAPIView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    Доступно без аутентификации.
    """
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny] # Разрешаем любому пользователю (даже неавторизованному) регистрироваться