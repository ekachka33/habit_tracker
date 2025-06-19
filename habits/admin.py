# habits/admin.py
from django.contrib import admin
from .models import Habit

@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'place', 'time', 'action', 'is_pleasant',
        'related_habit', 'periodicity', 'reward', 'duration', 'is_public'
    )
    list_filter = ('is_pleasant', 'is_public', 'periodicity')
    search_fields = ('action', 'place', 'reward')