# config/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('habits.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('api/users/', include('users.urls')),
    # JWT аутентификация
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # Получение access и refresh токенов
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Обновление access токена
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]

