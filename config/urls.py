from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# Настройка схемы для drf-yasg
schema_view = get_schema_view(
   openapi.Info(
      title="Habit Tracker API", # Название вашего API
      default_version='v1',      # Версия API
      description="API для приложения трекера привычек", # Описание
      terms_of_service="https://www.google.com/policies/terms/", # Опционально
      contact=openapi.Contact(email="contact@yourdomain.com"), # Опционально
      license=openapi.License(name="BSD License"), # Опционально
   ),
   public=True,
   permission_classes=[permissions.AllowAny], # Разрешить доступ к документации всем
)


urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT аутентификация
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API для привычек
    # Включаем URL-адреса из приложения 'habits' под префиксом 'api/habits/'.
    # Это позволяет роутеру в habits/urls.py (с пустым префиксом r'')
    # создать URL-адреса типа /api/habits/, /api/habits/<pk>/, /api/habits/<pk>/complete/
    # и путь для публичных привычек /api/habits/public/.
    path('api/habits/', include('habits.urls', namespace='habits')),

    # Включение URL-адресов для приложения users (предполагается, что там также есть app_name = 'users')
    path('api/users/', include('users.urls', namespace='users')),

    # Если 'rest_framework.urls' нужен для браузерного API или других целей
    path('api-auth/', include('rest_framework.urls')),

    # DRF-YASG URLs
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
