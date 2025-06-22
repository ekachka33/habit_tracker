# users/urls.py (обновленный, только для регистрации)
from django.urls import path
from users.views import UserRegisterAPIView
# from rest_framework.routers import DefaultRouter # Если у вас есть ViewSet для User, но судя по всему, нет

app_name = 'users' # ОЧЕНЬ ВАЖНО: определяет пространство имен 'users'

# router = DefaultRouter()
# router.register(r'users', UserViewSet, basename='user') # Пример, если бы был UserViewSet

urlpatterns = [
    # Путь для регистрации пользователя
    path('register/', UserRegisterAPIView.as_view(), name='user_register'),
    # Если был бы роутер, то так:
    # path('', include(router.urls)),
]
