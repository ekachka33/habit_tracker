# habits/urls.py
# habits/urls.py
from django.urls import path, include # <--- Обязательно добавьте 'include'
from rest_framework.routers import DefaultRouter # <--- Обязательно добавьте 'DefaultRouter'
from habits.views import HabitViewSet, HabitPublicListAPIView # <--- Импортируем ТОЛЬКО те классы, которые есть в views.py

app_name = 'habits'

# Создаем маршрутизатор (router)
router = DefaultRouter()
# Регистрируем HabitViewSet.
# 'habits' - это URL-префикс (т.е. /habits/ будет началом всех ваших URL для этого ViewSet)
# HabitViewSet - это класс ViewSet, который мы используем
# basename='habit' - это имя для набора URL-адресов, которое будет использоваться для reverse()
router.register(r'habits', HabitViewSet, basename='habit')

urlpatterns = [
    # Включаем все URL-адреса, автоматически сгенерированные маршрутизатором для HabitViewSet
    # Это покроет:
    # /habits/ (GET для списка, POST для создания)
    # /habits/<pk>/ (GET для детали, PUT/PATCH для обновления, DELETE для удаления)
    path('', include(router.urls)),

    # Отдельный путь для публичных привычек (т.к. это отдельный APIView)
    path('habits/public/', HabitPublicListAPIView.as_view(), name='habit_public_list'),
]