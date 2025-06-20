# config/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework.routers import DefaultRouter
from habits.views import HabitViewSet, HabitPublicListAPIView # Импортируем HabitPublicListAPIView
# from users.views import UserViewSet # Если у вас есть ViewSet для пользователей

router = DefaultRouter()
router.register(r'habits', HabitViewSet, basename='habit') # Регистрируем HabitViewSet для пути 'habits'
# router.register(r'users', UserViewSet) # Если есть ViewSet для пользователей


urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT аутентификация
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API для привычек (генерируется роутером)
    path('api/', include(router.urls)), # ЭТО ВКЛЮЧАЕТ /api/habits/ для всех методов

    # Отдельный эндпоинт для публичных привычек (если нужен отдельный путь)
    path('api/habits/public/', HabitPublicListAPIView.as_view(), name='habit_public_list'),

    # Включение URL-ов для приложения users (если там не ViewSet и роутер)
    path('api/users/', include('users.urls')),

    # Если 'rest_framework.urls' нужен для браузерного API или других целей
    path('api-auth/', include('rest_framework.urls')),
]