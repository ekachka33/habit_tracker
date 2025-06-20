# users/urls.py (обновленный, только для регистрации)
from django.urls import path
from users.views import UserRegisterAPIView

app_name = 'users'

urlpatterns = [
    path('register/', UserRegisterAPIView.as_view(), name='user_register'),
]
