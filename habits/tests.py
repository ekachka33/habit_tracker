from datetime import datetime, time
from unittest.mock import MagicMock, patch

import pytz
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from habits.models import Habit, NotificationLog
# Импортируем Celery-таски для прямого вызова в тестах
from habits.tasks import (_send_telegram_message_async_wrapper,
                          check_and_send_habit_reminders,
                          send_telegram_notification)

User = get_user_model()


class HabitTest(APITestCase):

    def setUp(self):
        """Создание тестовых данных: пользователей и их привычек."""
        self.user1 = User.objects.create_user(
            username="testuser1", email="test1@example.com", password="password123"
        )
        self.user2 = User.objects.create_user(
            username="testuser2", email="test2@example.com", password="password123"
        )

        # Получаем токены для user1
        response_user1_token = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "testuser1", "password": "password123"},
            format="json",
        )
        self.user1_access_token = response_user1_token.data["access"]
        self.user1_refresh_token = response_user1_token.data["refresh"]

        # Получаем токены для user2
        response_user2_token = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "testuser2", "password": "password123"},
            format="json",
        )
        self.user2_access_token = response_user2_token.data["access"]
        self.user2_refresh_token = response_user2_token.data["refresh"]

        # Аутентифицируем клиента как user1
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user1_access_token)

        # Создаем тестовые привычки
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
            telegram_chat_id="test_chat_id_1",  # Для тестов уведомлений
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
            telegram_chat_id="test_chat_id_1",  # Для тестов уведомлений
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
            telegram_chat_id="test_chat_id_2",  # Для тестов уведомлений
        )

        # Данные для создания новой привычки
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

        # Данные для создания приятной привычки
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

    # --- Тесты CRUD для своих привычек ---
    def test_create_habit(self):
        """Тестирование создания привычки."""
        data = self.habit_data.copy()
        data["action"] = "Новая привычка"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Habit.objects.count(), 5)
        self.assertEqual(response.data["action"], "Новая привычка")
        self.assertEqual(response.data["user"], self.user1.id)

    def test_list_my_habits(self):
        """Тестирование получения списка своих привычек."""
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIn(
            self.habit1.action, [h["action"] for h in response.data["results"]]
        )
        self.assertIn(
            self.pleasant_habit.action, [h["action"] for h in response.data["results"]]
        )
        self.assertIn(
            self.habit_with_related.action,
            [h["action"] for h in response.data["results"]],
        )
        self.assertNotIn(
            self.public_habit.action, [h["action"] for h in response.data["results"]]
        )

    def test_retrieve_my_habit(self):
        """Тестирование получения деталей своей привычки."""
        response = self.client.get(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], self.habit1.action)

    def test_update_my_habit(self):
        """Тестирование обновления своей привычки."""
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
        """Тестирование удаления своей привычки."""
        response = self.client.delete(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Habit.objects.count(), 3)

    # --- Тесты прав доступа ---
    def test_list_other_users_habit_forbidden(self):
        """Пользователь не должен видеть чужие привычки (кроме публичных)."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user2_access_token)
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIn(
            self.public_habit.action, [h["action"] for h in response.data["results"]]
        )
        self.assertNotIn(
            self.habit1.action, [h["action"] for h in response.data["results"]]
        )

    def test_retrieve_other_users_habit_forbidden(self):
        """Пользователь не должен получать детали чужой привычки."""
        response = self.client.get(
            reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_other_users_habit_forbidden(self):
        """Пользователь не должен обновлять чужую привычку."""
        updated_data = {"action": "Действие чужой привычки"}
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk}),
            updated_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            Habit.objects.get(pk=self.public_habit.pk).action, self.public_habit.action
        )

    def test_delete_other_users_habit_forbidden(self):
        """Пользователь не должен удалять чужую привычку."""
        response = self.client.delete(
            reverse("habits:habit-detail", kwargs={"pk": self.public_habit.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_forbidden(self):
        """Неаутентифицированный пользователь не может получить доступ
        к своим привычкам."""
        self.client.credentials()
        response = self.client.get(reverse("habits:habit-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Тесты публичных привычек ---
    def test_list_public_habits(self):
        """Тестирование получения списка публичных привычек."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user1_access_token)
        response = self.client.get(reverse("habits:habit_public_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["action"], self.public_habit.action
        )

    def test_public_habit_create_forbidden(self):
        """Нельзя создать привычку через эндпоинт публичных привычек."""
        data = self.habit_data.copy()
        response = self.client.post(
            reverse("habits:habit_public_list"), data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_public_habit_update_forbidden_public_endpoint(self):
        """Нельзя обновить привычку через эндпоинт публичных привычек."""
        data = {"action": "Обновление публичной привычки"}
        response = self.client.patch(
            reverse("habits:habit_public_list"), data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- Тесты валидаторов (HabitSerializer.validate) ---
    def test_create_habit_with_reward_and_related_habit_fail(self):
        """Нельзя одновременно иметь вознаграждение и связанную привычку."""
        data = self.habit_data.copy()
        data["related_habit"] = self.pleasant_habit.pk
        data["reward"] = "Какая-то награда"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Нельзя одновременно выбрать вознаграждение и " "связанную привычку.",
            response.data["non_field_errors"][0],
        )

    def test_create_pleasant_habit_with_reward_fail(self):
        """Приятная привычка не может иметь вознаграждения."""
        data = self.pleasant_habit_data.copy()
        data["reward"] = "Награда для приятной привычки"
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Приятная привычка не может иметь вознаграждения "
            "или связанной привычки.",
            response.data["non_field_errors"][0],
        )

    def test_create_pleasant_habit_with_related_habit_fail(self):
        """Приятная привычка не может иметь связанную привычку."""
        data = self.pleasant_habit_data.copy()
        data["related_habit"] = self.habit1.pk
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "В связанные привычки можно добавлять только " "приятные привычки.",
            str(response.data["related_habit"][0]),
        )

    def test_create_habit_with_non_pleasant_related_habit_fail(self):
        """В связанные привычки можно добавлять только приятные привычки."""
        data = self.habit_data.copy()
        data.pop("reward")
        data["related_habit"] = self.habit1.pk
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "В связанные привычки можно добавлять только " "приятные привычки.",
            response.data["related_habit"][0],
        )

    def test_create_habit_duration_exceeds_120_seconds_fail(self):
        """Время выполнения не должно превышать 120 секунд."""
        data = self.habit_data.copy()
        data["duration"] = 121
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Время на выполнение привычки не должно превышать " "120 секунд.",
            response.data["duration"][0],
        )

    def test_create_habit_periodicity_more_than_7_days_fail(self):
        """Периодичность не должна быть более 7 дней."""
        data = self.habit_data.copy()
        data["periodicity"] = 8
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Периодичность должна быть от 1 до 7 дней.", response.data["periodicity"][0]
        )

    def test_create_useful_habit_no_reward_or_related_fail(self):
        """Полезная привычка без вознаграждения и связанной привычки
        должна выдать ошибку."""
        data = self.habit_data.copy()
        data["reward"] = None
        data["related_habit"] = None
        response = self.client.post(reverse("habits:habit-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Для полезной привычки необходимо указать либо "
            "вознаграждение, либо связанную привычку.",
            response.data["non_field_errors"][0],
        )

    # --- Тесты эндпоинта complete_habit ---
    def test_complete_useful_habit_success(self):
        """Тестирование успешного выполнения полезной привычки
        (без связанной)."""
        habit = self.habit1
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(
            reverse("habits:habit-complete", kwargs={"pk": habit.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIn(
            "Привычка успешно отмечена как выполненная.", response.data["message"]
        )
        self.assertEqual(response.data["habit_id"], habit.pk)

    def test_complete_habit_with_related_pleasant_habit_success(self):
        """Тестирование выполнения полезной привычки со связанной приятной."""
        habit = self.habit_with_related
        pleasant_habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)
        self.assertIsNone(pleasant_habit.last_completed_at)

        response = self.client.post(
            reverse("habits:habit-complete", kwargs={"pk": habit.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        pleasant_habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIsNotNone(pleasant_habit.last_completed_at)
        self.assertIn(
            "Полезная привычка и связанная приятная привычка "
            "отмечены как выполненные.",
            response.data["message"],
        )
        self.assertEqual(response.data["habit_id"], habit.pk)
        self.assertEqual(response.data["related_habit_id"], pleasant_habit.pk)

    def test_complete_pleasant_habit_directly_fail(self):
        """Нельзя напрямую отметить приятную привычку."""
        habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(
            reverse("habits:habit-complete", kwargs={"pk": habit.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Невозможно отметить приятную привычку как выполненную " "напрямую.",
            response.data["detail"],
        )
        habit.refresh_from_db()
        self.assertIsNone(habit.last_completed_at)

    def test_complete_other_users_habit_forbidden(self):
        """Нельзя отметить чужую привычку."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.user2_access_token)
        response = self.client.post(
            reverse("habits:habit-complete", kwargs={"pk": self.habit1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)

    # --- Тесты Model.clean() ---
    def test_model_clean_reward_and_related_habit_fail(self):
        """Тест clean(): Нельзя одновременно иметь вознаграждение
        и связанную привычку."""
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
                ValidationError,
                "Нельзя одновременно выбрать вознаграждение и " "связанную привычку.",
        ):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_reward_fail(self):
        """Тест clean(): Приятная привычка не может иметь вознаграждения."""
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
                ValidationError,
                "Приятная привычка не может иметь вознаграждения или "
                "связанной привычки.",
        ):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_related_habit_fail(self):
        """Тест clean(): Приятная привычка не может иметь
        связанную привычку."""
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
                ValidationError,
                "Приятная привычка не может иметь вознаграждения или "
                "связанной привычки.",
        ):
            habit.full_clean()

    def test_model_clean_non_pleasant_related_habit_fail(self):
        """Тест clean(): В связанные привычки можно добавлять
        только приятные привычки."""
        habit = Habit(
            user=self.user1,
            action="Test",
            place="Place",
            time=time(9, 0),
            is_pleasant=False,
            periodicity=1,
            duration=30,
            related_habit=self.habit1,
        )  # self.habit1 не приятная
        with self.assertRaisesMessage(
                ValidationError,
                "В связанные привычки можно добавлять только приятные привычки.",
        ):
            habit.full_clean()

    def test_model_clean_duration_exceeds_120_seconds_fail(self):
        """Тест clean(): Время на выполнение привычки не должно
        превышать 120 секунд."""
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
                ValidationError,
                "Время на выполнение привычки не должно превышать 120 секунд.",
        ):
            habit.full_clean()

    def test_model_clean_periodicity_more_than_7_days_fail(self):
        """Тест clean(): Периодичность не должна быть более 7 дней."""
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
                ValidationError,
                "Периодичность должна быть от 1 до 7 дней (нельзя выполнять "
                "привычку реже, чем 1 раз в 7 дней).",
        ):
            habit.full_clean()

    # --- Тесты Celery-тасок ---
    # Патчим асинхронную обертку
    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    @patch(
        "habits.tasks.timezone.now",
        side_effect=[
            # Теперь side_effect здесь корректен,
            # т.к. используется только для test_send_telegram_notification_success
            pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
            pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
        ],
    )
    def test_send_telegram_notification_success(
            self, mock_now, mock_send_message_delay
    ):
        """Тестирование успешной отправки уведомления для полезной привычки."""
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(9, 0)
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        # Проверяем, что _send_telegram_message_async_wrapper.delay был вызван
        mock_send_message_delay.assert_called_once()
        called_kwargs = mock_send_message_delay.call_args[1]  # Получаем kwargs
        self.assertIn(self.habit1.telegram_chat_id, called_kwargs["chat_id"])
        self.assertIn(self.habit1.action, called_kwargs["message_text"])

        # Проверяем, что создана запись в логе уведомлений со статусом QUEUED
        self.assertEqual(NotificationLog.objects.count(), 1)
        log_entry = NotificationLog.objects.first()
        self.assertEqual(log_entry.status, "QUEUED")
        self.assertEqual(log_entry.habit, self.habit1)
        self.assertIn("Напоминание о привычке", log_entry.message_content)

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    def test_send_telegram_notification_no_chat_id(self, mock_send_message_delay):
        """Тестирование, что уведомление не отправляется, если нет chat_id."""
        self.habit1.telegram_chat_id = ""
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_not_called()
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)
        self.assertIsNone(self.habit1.last_notification_sent)
        self.assertEqual(
            NotificationLog.objects.count(), 0
        )  # Не должно быть записей в логе

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    def test_send_telegram_notification_pleasant_habit_skipped(
            self, mock_send_message_delay
    ):
        """Тестирование, что уведомление не отправляется для приятной привычки."""
        self.pleasant_habit.telegram_chat_id = "123456789"
        self.pleasant_habit.save()

        send_telegram_notification(self.pleasant_habit.id)

        mock_send_message_delay.assert_not_called()
        self.pleasant_habit.refresh_from_db()
        self.assertIsNone(self.pleasant_habit.last_completed_at)
        self.assertIsNone(self.pleasant_habit.last_notification_sent)
        self.assertEqual(
            NotificationLog.objects.count(), 0
        )  # Не должно быть записей в логе

    @patch("habits.tasks._send_telegram_message_async_wrapper.delay")
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
    )
    def test_send_telegram_notification_not_due_yet(
            self, mock_now, mock_send_message_delay
    ):
        """Тестирование, что send_telegram_notification вызывается,
        даже если время еще не пришло, но check_and_send_habit_reminders
        должен предотвратить это."""
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(10, 0)  # Время уведомления в будущем
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_called_once()
        self.habit1.refresh_from_db()
        # last_notification_sent обновляется только после фактической успешной
        # отправки из _send_telegram_message_async_wrapper
        self.assertIsNone(self.habit1.last_notification_sent)

        # Проверяем, что создана запись в логе уведомлений со статусом QUEUED
        self.assertEqual(NotificationLog.objects.count(), 1)
        log_entry = NotificationLog.objects.first()
        self.assertEqual(log_entry.status, "QUEUED")

    # ИЗМЕНЕН: Теперь патчим Bot.send_message и вызываем .run() таска,
    # ожидая исключение
    @patch("habits.tasks.Bot")  # Патчим класс Bot
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
    )
    def test_send_telegram_notification_api_error(self, mock_now, MockBot):
        """Тестирование обработки ошибок при отправке в Telegram
        (имитация ошибки)."""
        # Настроим мок send_message, чтобы он поднимал исключение
        MockBot.return_value.send_message.side_effect = Exception(
            "Simulated Telegram API error"
        )

        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None
        self.habit1.save()

        # Создаем запись в логе, как это делает send_telegram_notification
        notification_log = NotificationLog.objects.create(
            habit=self.habit1,
            message_content=f"Напоминание о привычке: '{self.habit1.action}' "
                            f"в '{self.habit1.place}' в "
                            f"{self.habit1.time.strftime('%H:%M')}!",
            status="QUEUED",
        )

        # Вызываем _send_telegram_message_async_wrapper.run() напрямую,
        # чтобы проверить логику обработки ошибок внутри таска
        # Bind=True означает, что self должен быть передан как первый аргумент
        # (это сам таск).
        # Celery обычно делает это автоматически.
        # Здесь мы можем передать его как None или MagicMock
        with self.assertRaisesMessage(
                Exception, "Simulated Telegram API error"
        ):  # <-- ИЗМЕНЕНИЕ ЗДЕСЬ
            _send_telegram_message_async_wrapper.run(
                MagicMock(),  # Передаем mock self
                chat_id=self.habit1.telegram_chat_id,
                message_text="Test message",
                # Сообщение, которое будет пытаться отправить
                # _send_telegram_message_async_wrapper
                notification_log_id=notification_log.id,
            )

        # Проверяем, что last_notification_sent не изменилось
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_notification_sent)

        # Проверяем, что NotificationLog получил статус 'FAILED'
        log_entry = NotificationLog.objects.get(
            id=notification_log.id
        )  # Получаем обновленную запись
        self.assertEqual(log_entry.status, "FAILED")

    # ИЗМЕНЕН: Патчим send_telegram_notification.delay
    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now")
    def test_check_and_send_habit_reminders_daily(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders с ежедневной
        периодичностью."""
        test_now_initial = pytz.utc.localize(datetime(2025, 1, 5, 9, 0, 0))
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 1
        self.habit1.last_notification_sent = pytz.utc.localize(
            datetime(2025, 1, 4, 8, 30, 0)
        )  # Отправлено вчера
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        # Проверяем вызов с ID привычки
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

        # ИЗМЕНЕНИЕ ЗДЕСЬ: Эмулируем обновление last_notification_sent
        # после успешной отправки
        self.habit1.last_notification_sent = test_now_initial
        self.habit1.save()
        self.habit1.refresh_from_db()

        mock_send_notification_delay.reset_mock()

        # Проверяем, что при повторном запуске в тот же день,
        # не будет отправлено
        mock_now.return_value = pytz.utc.localize(
            datetime(2025, 1, 5, 10, 0, 0)
        )  # Время позже в тот же день
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        # Проверяем, что будет отправлено на следующий день
        mock_now.return_value = pytz.utc.localize(
            datetime(2025, 1, 6, 9, 0, 0)
        )  # Следующий день
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    # ИЗМЕНЕН: Патчим send_telegram_notification.delay
    @patch("habits.tasks.send_telegram_notification.delay")
    @patch("habits.tasks.timezone.now")
    def test_check_and_send_habit_reminders_multiple_days(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders с периодичностью
        > 1 дня."""
        test_now_initial = pytz.utc.localize(datetime(2025, 1, 7, 9, 0, 0))
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 3
        self.habit1.last_notification_sent = pytz.utc.localize(
            datetime(2025, 1, 4, 8, 30, 0)
        )
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        # Проверяем вызов с ID привычки
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

        # ИЗМЕНЕНИЕ ЗДЕСЬ: Эмулируем обновление last_notification_sent
        # после успешной отправки
        self.habit1.last_notification_sent = test_now_initial
        self.habit1.save()
        self.habit1.refresh_from_db()

        mock_send_notification_delay.reset_mock()

        # Проверяем, что не будет отправлено на следующий день
        # (периодичность 3)
        mock_now.return_value = pytz.utc.localize(
            datetime(2025, 1, 8, 9, 0, 0)
        )  # Через 1 день после last_notification_sent
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        # Проверяем, что не будет отправлено через 2 дня (периодичность 3)
        mock_now.return_value = pytz.utc.localize(
            datetime(2025, 1, 9, 9, 0, 0)
        )  # Через 2 дня
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

        mock_send_notification_delay.reset_mock()

        # Проверяем, что будет отправлено через 3 дня
        mock_now.return_value = pytz.utc.localize(
            datetime(2025, 1, 10, 9, 0, 0)
        )  # Через 3 дня
        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 7, 0, 0)),
    )
    def test_check_and_send_habit_reminders_not_due_time_today(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders: время уведомления
        еще не наступило сегодня."""
        mock_now.return_value = pytz.utc.localize(datetime(2025, 1, 1, 7, 0, 0))

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None
        self.habit1.is_pleasant = False
        self.habit1.periodicity = 1
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
    )
    def test_check_and_send_habit_reminders_no_chat_id_or_pleasant(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders:
        пропускаются привычки без chat_id или приятные."""
        # Приятная привычка
        self.pleasant_habit.telegram_chat_id = "chat_id_pleasant"
        self.pleasant_habit.is_pleasant = True
        self.pleasant_habit.time = time(8, 0)
        self.pleasant_habit.last_notification_sent = None
        self.pleasant_habit.save()

        # Полезная привычка без chat_id
        self.public_habit.telegram_chat_id = ""  # Пустой chat_id
        self.public_habit.is_pleasant = False
        self.public_habit.time = time(8, 0)
        self.public_habit.last_notification_sent = None
        self.public_habit.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch(
        "habits.tasks.timezone.now",
        return_value=pytz.utc.localize(datetime(2025, 1, 1, 9, 0, 0)),
    )
    def test_check_and_send_habit_reminders_first_notification(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders:
        первое уведомление для привычки."""
        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None  # Никогда не отправлялось
        self.habit1.is_pleasant = False
        self.habit1.periodicity = 1
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_called_once_with(self.habit1.id)

    @patch("habits.tasks.send_telegram_notification.delay")
    @patch(
        "habits.tasks.timezone.now",
        side_effect=[
            pytz.utc.localize(datetime(2025, 1, 10, 8, 0, 0)),  # Проверка
        ],
    )
    def test_check_and_send_habit_reminders_periodicity_not_met(
            self, mock_now, mock_send_notification_delay
    ):
        """Тестирование check_and_send_habit_reminders:
        периодичность еще не наступила."""
        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(7, 30)
        self.habit1.periodicity = 5
        self.habit1.last_notification_sent = pytz.utc.localize(
            datetime(2025, 1, 8, 7, 0, 0)
        )  # Отправлено 2 дня назад
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_notification_delay.assert_not_called()

    def test_habit_creation_with_valid_related_habit(self):
        """
        Тестирование создания привычки с корректной связанной
        (приятной) привычкой.
        """
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
        """
        Тестирование обновления привычки для добавления корректной
        связанной привычки.
        """
        # Изначально у habit1 нет связанной привычки или вознаграждения
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
        """
        Тестирование обновления привычки для добавления некорректной
        связанной привычки (неприятной).
        """
        # Убедимся, что habit1 сейчас без связанной привычки
        self.habit1.related_habit = None
        self.habit1.reward = None  # Чтобы не конфликтовало
        self.habit1.save()

        data = {
            "related_habit": self.habit_with_related.pk
        }  # habit_with_related не приятная
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "В связанные привычки можно добавлять только " "приятные привычки.",
            response.data["related_habit"][0],
        )
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.related_habit)  # Проверяем, что не изменилось

    def test_habit_update_from_reward_to_related_habit(self):
        """
        Тестирование обновления привычки:
        замена вознаграждения на связанную привычку.
        """
        self.habit1.reward = "Старое вознаграждение"
        self.habit1.related_habit = None
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
        """
        Тестирование обновления привычки:
        замена связанной привычки на вознаграждение.
        """
        self.habit_with_related.reward = None
        self.habit_with_related.related_habit = self.pleasant_habit
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
        """
        Тестирование обновления привычки на приятную:
        должны быть удалены связанная привычка и вознаграждение.
        """
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
        """
        Тестирование обновления привычки на приятную,
        но с оставленным вознаграждением.
        """
        self.habit1.reward = "Какая-то награда"
        self.habit1.is_pleasant = False
        self.habit1.save()

        data = {"is_pleasant": True}  # reward останется
        response = self.client.patch(
            reverse("habits:habit-detail", kwargs={"pk": self.habit1.pk}),
            data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Приятная привычка не может иметь вознаграждения "
            "или связанной привычки.",
            response.data["non_field_errors"][0],
        )
        self.habit1.refresh_from_db()
        self.assertFalse(self.habit1.is_pleasant)  # Не должно измениться
        self.assertIsNotNone(self.habit1.reward)
