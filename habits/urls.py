from django.urls import path, include
from rest_framework.routers import DefaultRouter
from habits.views import HabitViewSet, PublicHabitListAPIView

app_name = 'habits'

router = DefaultRouter()
router.register(r'habits', HabitViewSet, basename='habit') # Эндпоинты для CRUD ваших привычек

urlpatterns = [
    path('', include(router.urls)), # Включаем URL-адреса из DefaultRouter

    # Отдельный эндпоинт для публичных привычек
    path('habits/public/', PublicHabitListAPIView.as_view(), name='habit_public_list'),
]