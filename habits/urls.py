# habits/urls.py
from django.urls import path
from habits.views import (
    HabitCreateAPIView,
    HabitListAPIView,
    HabitPublicListAPIView,
    HabitRetrieveAPIView,
    HabitUpdateAPIView,
    HabitDestroyAPIView
)

app_name = 'habits'

urlpatterns = [
    path('habits/create/', HabitCreateAPIView.as_view(), name='habit_create'),
    path('habits/', HabitListAPIView.as_view(), name='habit_list'),
    path('habits/public/', HabitPublicListAPIView.as_view(), name='habit_public_list'),
    path('habits/<int:pk>/', HabitRetrieveAPIView.as_view(), name='habit_retrieve'),
    path('habits/update/<int:pk>/', HabitUpdateAPIView.as_view(), name='habit_update'),
    path('habits/delete/<int:pk>/', HabitDestroyAPIView.as_view(), name='habit_delete'),
]