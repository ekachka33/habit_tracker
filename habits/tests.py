from datetime import datetime, time
from unittest.mock import MagicMock, patch

import pytz
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings

from habits.models import Habit, NotificationLog
from habits.tasks import (
    _send_telegram_message_async_wrapper,
    check_and_send_habit_reminders,
    send_telegram_notification,
)

User = get_user_model()

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES_EXCEPTIONS=True)
class HabitTest(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="password123"
        )

        response_user1_token = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "testuser1", "password": "password123"},
            format="json",
        )
        self.user1_access_token = response_user1_token.data["access"]

        # ВОЗВРАЩЕНО: Создание access_token для user2
        response_user2_token = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "testuser2", "password": "password123"},
            format="json",
        )
        self.user2_access_token = response_user2_token.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user1_access_token)

        self.habit1 = Habit.objects.create(
            user=self.user1,
            action="Выпить стакан воды",
            place="Дома",
            time=time(8, 0),
            is_pleasant=False,
            periodicity=1,
            duration=30,
            is_public=False,
            reward="Награда за воду",
            telegram_chat_id="test_chat_id_1",
        )

        self.pleasant_habit = Habit.objects.create(
            user=self.user1,
            action="Послушать музыку",
            place="По дороге на работу",
            time=time(7, 30),
            is_pleasant=True,
            periodicity=1,
            duration=60,
            is_public=False,
            telegram_chat_id="test_chat_id_1",
        )

        self.habit_with_related = Habit.objects.create(
            user=self.user1,
            action="Сделать 10 отжиманий",
            place="В спортзале",
            time=time(18, 0),
            is_pleasant=False,
            related_habit=self.pleasant_habit,
            periodicity=1,
            duration=45,
            is_public=False,
            telegram_chat_id="test_chat_id_1",
        )

        self.public_habit = Habit.objects.create(
            user=self.user2,
            action="Прочитать 10 страниц книги",
            place="Библиотека",
            time=time(20, 0),
            is_pleasant=False,
            periodicity=1,
            duration=60,
            is_public=True,
            reward="Награда за чтение",
            telegram_chat_id="test_chat_id_2",
        )

        self.habit_data = {
            "action": "Пробежка",
            "place": "Парк",
            "time": "06:00:00",
            "is_pleasant": False,
            "periodicity": 1,
            "duration": 60,
            "is_public": True,
            "reward": "Купить себе кофе",
            "telegram_chat_id": "new_chat_id",
        }

        self.pleasant_habit_data = {
            "action": "Медитация",
            "place": "Тихое место",
            "time": "22:00:00",
            "is_pleasant": True,
            "periodicity": 1,
            "duration": 120,
            "is_public": True,
            "telegram_chat_id": "new_pleasant_chat_id",
        }

    def test_create_habit(self):
        data = self.habit_data.copy()
        data["action"] = "Новая привычка"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Habit.objects.count(), 5)
        self.assertEqual(response.data["action"], "Новая привычка")
        self.assertEqual(response.data["user"], self.user1.id)

    def test_list_my_habits(self):
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIn(self.habit1.action, [h["action"] for h in response.data["results"]])
        self.assertIn(self.pleasant_habit.action, [h["action"] for h in response.data["results"]])
        self.assertIn(self.habit_with_related.action, [h["action"] for h in response.data["results"]])
        self.assertNotIn(self.public_habit.action, [h["action"] for h in response.data["results"]])

    def test_retrieve_my_habit(self):
        response = self.client.get(reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], self.habit1.action)

    def test_update_my_habit(self):
        updated_data = {"action": "Новое действие привычки", "reward": "Другая награда"}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            updated_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.action, "Новое действие привычки")

    def test_delete_my_habit(self):
        response = self.client.delete(reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Habit.objects.count(), 3)

    def test_list_other_users_habit_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user2_access_token)
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn(self.public_habit.action, [h["action"] for h in response.data["results"]])
        self.assertNotIn(self.habit1.action, [h["action"] for h in response.data["results"]])

    def test_retrieve_other_users_habit_forbidden(self):
        # Пользователь user1 пытается получить привычку user2, которая является публичной.
        # Однако, поскольку это API для своих привычек, он не должен получить прямой доступ.
        # Это не должно быть 404, а 403, если Permissins правильно настроены.
        # Но ваш тест ожидает 404, если это не его привычка.
        # Если API PublicHabitListAPIView используется для публичных, то здесь 404 корректен.
        response = self.client.get(reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_other_users_habit_forbidden(self):
        updated_data = {"action": "Действие чужой привычки"}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk}),
            updated_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Habit.objects.get(pk=self.public_habit.pk).action, self.public_habit.action)

    def test_delete_other_users_habit_forbidden(self):
        response = self.client.delete(reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_forbidden(self):
        self.client.credentials()
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_public_habits(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user1_access_token)
        response = self.client.get(reverse("habits:habit_public_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["action"], self.public_habit.action)

    def test_public_habit_create_forbidden(self):
        data = self.habit_data.copy()
        response = self.client.post(reverse("habits:habit_public_list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_public_habit_update_forbidden_public_endpoint(self):
        data = {"action": "Обновление публичной привычки"}
        response = self.client.patch(reverse("habits:habit_public_list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_create_habit_with_reward_and_related_habit_fail(self):
        data = self.habit_data.copy()
        data["related_habit"] = self.pleasant_habit.pk
        data["reward"] = "Какая-то награда"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Нельзя одновременно выбрать вознаграждение и связанную привычку.", response.data["non_field_errors"][0])

    def test_create_pleasant_habit_with_reward_fail(self):
        data = self.pleasant_habit_data.copy()
        data["reward"] = "Награда для приятной привычки"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Приятная привычка не может иметь вознаграждения или связанной привычки.", response.data["non_field_errors"][0])

    def test_create_pleasant_habit_with_related_habit_fail(self):
        data = self.pleasant_habit_data.copy()
        data["related_habit"] = self.habit1.pk
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("В связанные привычки можно добавлять только приятные привычки.", str(response.data["related_habit"][0]))

    def test_create_habit_with_non_pleasant_related_habit_fail(self):
        data = self.habit_data.copy()
        data.pop("reward")
        data["related_habit"] = self.habit1.pk
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("В связанные привычки можно добавлять только приятные привычки.", response.data["related_habit"][0])

    def test_create_habit_duration_exceeds_120_seconds_fail(self):
        data = self.habit_data.copy()
        data["duration"] = 121
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Время на выполнение привычки не должно превышать 120 секунд.", response.data["duration"][0])

    def test_create_habit_periodicity_more_than_7_days_fail(self):
        data = self.habit_data.copy()
        data["periodicity"] = 8
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Периодичность должна быть от 1 до 7 дней.", response.data["periodicity"][0])

    def test_create_useful_habit_no_reward_or_related_fail(self):
        data = self.habit_data.copy()
        data["reward"] = None
        data["related_habit"] = None
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.",
            response.data["non_field_errors"][0],
        )

    def test_complete_useful_habit_success(self):
        habit = self.habit1
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(reverse("habits:habit-complete", kwargs={"pk": habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIn("Привычка успешно отмечена как выполненная.", response.data["message"])
        self.assertEqual(response.data["habit_id"], habit.pk)

    def test_complete_habit_with_related_pleasant_habit_success(self):
        habit = self.habit_with_related
        pleasant_habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)
        self.assertIsNone(pleasant_habit.last_completed_at)

        response = self.client.post(reverse("habits:habit-complete", kwargs={"pk": habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        pleasant_habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIsNotNone(pleasant_habit.last_completed_at)
        self.assertIn(
            "Полезная привычка и связанная приятная привычка отмечены как выполненные.",
            response.data["message"],
        )
        self.assertEqual(response.data["habit_id"], habit.pk)
        self.assertEqual(response.data["related_habit_id"], pleasant_habit.pk)

    def test_complete_pleasant_habit_directly_fail(self):
        habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(reverse("habits:habit-complete", kwargs={"pk": habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Невозможно отметить приятную привычку как выполненную напрямую.", response.data["detail"])
        habit.refresh_from_db()
        self.assertIsNone(habit.last_completed_at)

    def test_complete_other_users_habit_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user2_access_token)
        response = self.client.post(reverse("habits:habit-complete", kwargs={"pk": self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)

    def test_model_clean_reward_and_related_habit_fail(self):
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=False,
            periodicity=1,
            duration=30,
            reward="Reward",
            related_habit=self.pleasant_habit,
        )
        with self.assertRaisesMessage(
            ValidationError, "Нельзя одновременно выбрать вознаграждение и связанную привычку."
        ):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_reward_fail(self):
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=True,
            periodicity=1,
            duration=30,
            reward="Reward",
        )
        with self.assertRaisesMessage(
            ValidationError, "Приятная привычка не может иметь вознаграждения или связанной привычки."
        ):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_related_habit_fail(self):
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=True,
            periodicity=1,
            duration=30,
            related_habit=self.pleasant_habit,
        )
        with self.assertRaisesMessage(
            ValidationError, "Приятная привычка не может иметь вознаграждения или связанной привычки."
        ):
            habit.full_clean()

    def test_model_clean_non_pleasant_related_habit_fail(self):
        if self.habit1.is_pleasant:
            self.habit1.is_pleasant = False
            self.habit1.save()

        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=False,
            periodicity=1,
            duration=30,
            reward=None,
            related_habit=self.habit1,
        )
        with self.assertRaisesMessage(
            ValidationError, "В связанные привычки можно добавлять только приятные привычки."
        ):
            habit.full_clean()

    def test_model_clean_duration_exceeds_120_seconds_fail(self):
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=False,
            periodicity=1,
            duration=121,
            reward="R",
        )
        with self.assertRaisesMessage(
            ValidationError, "Время на выполнение привычки не должно превышать 120 секунд."
        ):
            habit.full_clean()

    def test_model_clean_periodicity_more_than_7_days_fail(self):
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=False,
            periodicity=8,
            duration=30,
            reward="R",
        )
        with self.assertRaisesMessage(
            ValidationError, "Периодичность должна быть от 1 до 7 дней (нельзя выполнять привычку реже, чем 1 раз в 7 дней)."
        ):
            habit.full_clean()

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    @patch(
        "habits.tasks.timezone.now",
        side_effect=[
            pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
            pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
        ],
    )
    def test_send_telegram_notification_success(self, mock_now, mock_send_message_delay):
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(9, 0)
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_called_once()
        called_kwargs = mock_send_message_delay.call_args[1]
        self.assertIn(self.habit1.telegram_chat_id, called_kwargs["chat_id"])
        self.assertIn(self.habit1.action, called_kwargs["message_text"])

        self.assertEqual(NotificationLog.objects.count(), 1)
        log_entry = NotificationLog.objects.first()
        self.assertEqual(log_entry.status, "QUEUED")
        self.assertEqual(log_entry.habit, self.habit1)
        self.assertIn("Напоминание о привычке", log_entry.message_content)

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    def test_send_telegram_notification_no_chat_id(self, mock_send_message_delay):
        self.habit1.telegram_chat_id = ""
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_not_called()
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)
        self.assertIsNone(self.habit1.last_notification_sent)
        self.assertEqual(NotificationLog.objects.count(), 0)

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    def test_send_telegram_notification_pleasant_habit_skipped(self, mock_send_message_delay):
        self.pleasant_habit.telegram_chat_id = "123456789"
        self.pleasant_habit.save()

        send_telegram_notification(self.pleasant_habit.id)

        mock_send_message_delay.assert_not_called()
        self.pleasant_habit.refresh_from_db()
        self.assertIsNone(self.pleasant_habit.last_completed_at)
        self.assertIsNone(self.pleasant_habit.last_notification_sent)
        self.assertEqual(NotificationLog.objects.count(), 0)

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
    )
    def test_send_telegram_notification_not_due_yet(self, mock_now, mock_send_message_delay):
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(10, 0)
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_called_once()
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_notification_sent)
        self.assertEqual(NotificationLog.objects.count(), 1)
        log_entry = NotificationLog.objects.first()
        self.assertEqual(log_entry.status, "QUEUED")


    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now")
    def test_check_and_send_habit_reminders_daily(self, mock_now, mock_send_notification_delay):
        test_now_initial = pytz.utc.localize(datetime(2025, 1, 5, 9, 0, 0))
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 1
        self.habit1.last_notification_sent = pytz.utc.localize(datetime(2025, 1, 4, 8, 30, 0))
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

        self.habit1.last_notification_sent = test_now_initial
        self.habit1.save()
        self.habit1.refresh_from_db()

        mock_send_notification_delay.reset_mock()

        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 5, 10, 0, 0))
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 6, 9, 0, 0))
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now")
    def test_check_and_send_habit_reminders_multiple_days(self, mock_now, mock_send_notification_delay):
        test_now_initial = pytz.utc.localize(datetime(2025, 1, 7, 9, 0, 0))
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 3
        self.habit1.last_notification_sent = pytz.utc.localize(datetime(2025, 1, 4, 8, 30, 0))
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

        self.habit1.last_notification_sent = test_now_initial
        self.habit1.save()
        self.habit1.refresh_from_db()

        mock_send_notification_delay.reset_mock()

        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 8, 9, 0, 0))
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 9, 9, 0, 0))
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 10, 9, 0, 0))
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now", return_value=pytz.utc.localize(datetime(2025, 1, 1, 7, 0, 0)))
    def test_check_and_send_habit_reminders_not_due_time_today(self, mock_now, mock_send_notification_delay):
        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None
        self.habit1.is_pleasant = False
        self.habit1.periodicity = 1
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now", return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)))
    def test_check_and_send_habit_reminders_no_chat_id_or_pleasant(self, mock_now, mock_send_notification_delay):
        Habit.objects.all().delete()

        pleasant_habit_for_test = Habit.objects.create(
            user=self.user1,
            action="Тестовая приятная привычка",
            place="Дома",
            time=time(8, 0),
            is_pleasant=True,
            periodicity=1,
            duration=60,
            is_public=False,
            telegram_chat_id="chat_id_pleasant",
            last_notification_sent=None,
        )

        no_chat_id_habit_for_test = Habit.objects.create(
            user=self.user1,
            action="Тестовая полезная привычка без чата",
            place="В офисе",
            time=time(8, 0),
            is_pleasant=False,
            periodicity=1,
            duration=60,
            is_public=False,
            telegram_chat_id="",
            reward="Тестовая награда",
            last_notification_sent=None,
        )

        check_and_send_habit_reminders()

        mock_send_notification_delay.assert_not_called()

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now", return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)))
    def test_check_and_send_habit_reminders_first_notification(self, mock_now, mock_send_notification_delay):
        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None
        self.habit1.is_pleasant = False
        self.habit1.periodicity = 1
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch(
        "habits.tasks.timezone.now",
        side_effect=[
            pytz.utc.localize(datetime(2025, 1, 10, 8, 0, 0)),
        ],
    )
    def test_check_and_send_habit_reminders_periodicity_not_met(self, mock_now, mock_send_notification_delay):
        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(7, 30)
        self.habit1.periodicity = 5
        self.habit1.last_notification_sent = pytz.utc.localize(datetime(2025, 1, 8, 7, 0, 0))
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

    def test_habit_creation_with_valid_related_habit(self):
        data = {
            "action": "Протереть пыль",
            "place": "Дома",
            "time": "10:00:00",
            "is_pleasant": False,
            "related_habit": self.pleasant_habit.pk,
            "periodicity": 2,
            "duration": 90,
            "is_public": False,
            "telegram_chat_id": "test_chat_id_related",
        }
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["related_habit"], self.pleasant_habit.pk)
        self.assertIsNone(response.data["reward"])
        new_habit = Habit.objects.get(pk=response.data["id"])
        self.assertEqual(new_habit.related_habit, self.pleasant_habit)
        self.assertIsNone(new_habit.reward)

    def test_habit_update_to_add_related_habit_valid(self):
        self.habit1.reward = None
        self.habit1.save()

        data = {"related_habit": self.pleasant_habit.pk}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.related_habit, self.pleasant_habit)
        self.assertIsNone(self.habit1.reward)

    def test_habit_update_to_add_related_habit_invalid(self):
        self.habit1.related_habit = None
        self.habit1.reward = None
        self.habit1.save()

        data = {"related_habit": self.habit_with_related.pk}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("В связанные привычки можно добавлять только приятные привычки.", response.data["related_habit"][0])
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.related_habit)

    def test_habit_update_from_reward_to_related_habit(self):
        self.habit1.reward = "Старое вознаграждение"
        self.habit1.related_habit = None
        self.habit1.is_pleasant = False
        self.habit1.save()

        data = {"reward": None, "related_habit": self.pleasant_habit.pk}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.reward)
        self.assertEqual(self.habit1.related_habit, self.pleasant_habit)

    def test_habit_update_from_related_habit_to_reward(self):
        self.habit_with_related.reward = None
        self.habit_with_related.related_habit = self.pleasant_habit
        self.habit_with_related.is_pleasant = False
        self.habit_with_related.save()

        data = {"related_habit": None, "reward": "Новое вознаграждение"}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit_with_related.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit_with_related.refresh_from_db()
        self.assertIsNone(self.habit_with_related.related_habit)
        self.assertEqual(self.habit_with_related.reward, "Новое вознаграждение")

    def test_habit_update_to_pleasant_and_remove_related_or_reward(self):
        self.habit1.reward = "Какая-то награда"
        self.habit1.related_habit = None
        self.habit1.is_pleasant = False
        self.habit1.save()

        data = {"is_pleasant": True, "reward": None, "related_habit": None}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit1.refresh_from_db()
        self.assertTrue(self.habit1.is_pleasant)
        self.assertIsNone(self.habit1.reward)
        self.assertIsNone(self.habit1.related_habit)

    def test_habit_update_to_pleasant_with_reward_fail(self):
        self.habit1.reward = "Какая-то награда"
        self.habit1.is_pleasant = False
        self.habit1.save()

        data = {"is_pleasant": True}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Приятная привычка не может иметь вознаграждения или связанной привычки.", response.data["non_field_errors"][0])
        self.habit1.refresh_from_db()
        self.assertFalse(self.habit1.is_pleasant)
        self.assertIsNotNone(self.habit1.reward)