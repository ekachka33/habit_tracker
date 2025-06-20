# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework.routers import DefaultRouter
from habits.views import HabitViewSet, PublicHabitListAPIView
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
    path('api/habits/public/', PublicHabitListAPIView.as_view(), name='habit_public_list'),

    # Включение URL-ов для приложения users (если там не ViewSet и роутер)
    path('api/users/', include('users.urls')),

    # Если 'rest_framework.urls' нужен для браузерного API или других целей
    path('api-auth/', include('rest_framework.urls')),

    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]