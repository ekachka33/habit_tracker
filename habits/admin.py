from django.contrib import admin

from .models import Habit, NotificationLog


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "place",
        "time",
        "action",
        "is_pleasant",
        "related_habit",
        "periodicity",
        "reward",
        "duration",
        "is_public",
        "telegram_chat_id",
        "last_notification_sent",
        "last_completed_at",
    )
    list_filter = ("is_pleasant", "is_public", "periodicity")
    search_fields = ("action", "place", "reward", "user__email")
    ordering = ("time",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("habit", "timestamp", "status", "message_content")
    list_filter = ("status", "timestamp")
    search_fields = ("habit__action", "message_content")
    readonly_fields = ("timestamp",)
