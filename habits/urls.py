from django.urls import path
from rest_framework.routers import DefaultRouter

from habits.views import HabitViewSet, PublicHabitListAPIView

app_name = "habits"

router = DefaultRouter()
# Регистрируем HabitViewSet с ПУСТЫМ префиксом.
# Это значит, что его URL-адреса будут непосредственно
# после пути, по которому habits.urls будет включен в config/urls.py
router.register(r"", HabitViewSet, basename="habit")

urlpatterns = [
    # Этот путь будет доступен как /api/habits/public/ (благодаря config/urls.py)
    path(
        "public/",
        PublicHabitListAPIView.as_view(),
        name="habit_public_list",
    ),
]

# Добавляем все URL-адреса, сгенерированные роутером.
# Они будут доступны как /api/habits/, /api/habits/<pk>/, /api/habits/<pk>/complete/
urlpatterns += router.urls