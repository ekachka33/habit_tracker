# users/views.py
# users/views.py (обновленный, только для регистрации)
from rest_framework import generics
from rest_framework.permissions import AllowAny
from users.serializers import UserRegisterSerializer # Только этот сериализатор

class UserRegisterAPIView(generics.CreateAPIView):
    """
    Регистрация нового пользователя.
    Доступно без аутентификации.
    """
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]