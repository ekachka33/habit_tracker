from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from habits.models import Habit
from django.utils import timezone
from datetime import time, timedelta, datetime
import pytz  # ИМПОРТИРОВАНО: pytz
from unittest.mock import patch, MagicMock, ANY

from django.core.exceptions import ValidationError

# Импортируем Celery-таски для прямого вызова в тестах
# Убедитесь, что habits/tasks.py существует и содержит эти таски
from habits.tasks import send_telegram_notification, check_and_send_habit_reminders

User = get_user_model()


class HabitTest(APITestCase):

    def setUp(self):
        """Создание тестовых данных: пользователей и их привычек."""
        self.user1 = User.objects.create_user(username='testuser1', email='test1@example.com', password='password123')
        self.user2 = User.objects.create_user(username='testuser2', email='test2@example.com', password='password123')

        # Получаем токены для user1
        response_user1_token = self.client.post(reverse('token_obtain_pair'),
                                                {'username': 'testuser1', 'password': 'password123'}, format='json')
        self.user1_access_token = response_user1_token.data['access']
        self.user1_refresh_token = response_user1_token.data['refresh']

        # Получаем токены для user2
        response_user2_token = self.client.post(reverse('token_obtain_pair'),
                                                {'username': 'testuser2', 'password': 'password123'}, format='json')
        self.user2_access_token = response_user2_token.data['access']
        self.user2_refresh_token = response_user2_token.data['refresh']

        # Аутентифицируем клиента как user1
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.user1_access_token)

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
            telegram_chat_id="test_chat_id_1"  # Для тестов уведомлений
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
            telegram_chat_id="test_chat_id_1"  # Для тестов уведомлений, но она приятная
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
            telegram_chat_id="test_chat_id_1"  # Для тестов уведомлений
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
            telegram_chat_id="test_chat_id_2"  # Для тестов уведомлений
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
            "telegram_chat_id": "new_chat_id"
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
            "telegram_chat_id": "new_pleasant_chat_id"
        }

    # --- Тесты CRUD для своих привычек ---
    def test_create_habit(self):
        """Тестирование создания привычки."""
        data = self.habit_data.copy()
        data['action'] = "Новая привычка"
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Habit.objects.count(), 5)
        self.assertEqual(response.data['action'], "Новая привычка")
        self.assertEqual(response.data['user'], self.user1.id)

    def test_list_my_habits(self):
        """Тестирование получения списка своих привычек."""
        response = self.client.get(reverse('habits:habit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        self.assertIn(self.habit1.action, [h['action'] for h in response.data['results']])
        self.assertIn(self.pleasant_habit.action, [h['action'] for h in response.data['results']])
        self.assertIn(self.habit_with_related.action, [h['action'] for h in response.data['results']])
        self.assertNotIn(self.public_habit.action, [h['action'] for h in response.data['results']])

    def test_retrieve_my_habit(self):
        """Тестирование получения деталей своей привычки."""
        response = self.client.get(reverse('habits:habit-detail', kwargs={'pk': self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['action'], self.habit1.action)

    def test_update_my_habit(self):
        """Тестирование обновления своей привычки."""
        updated_data = {"action": "Новое действие привычки", "reward": "Другая награда"}
        response = self.client.patch(reverse('habits:habit-detail', kwargs={'pk': self.habit1.pk}), updated_data,
                                     format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.action, "Новое действие привычки")

    def test_delete_my_habit(self):
        """Тестирование удаления своей привычки."""
        response = self.client.delete(reverse('habits:habit-detail', kwargs={'pk': self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Habit.objects.count(), 3)

    # --- Тесты прав доступа ---
    def test_list_other_users_habit_forbidden(self):
        """Пользователь не должен видеть чужие привычки (кроме публичных)."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.user2_access_token)
        response = self.client.get(reverse('habits:habit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn(self.public_habit.action, [h['action'] for h in response.data['results']])
        self.assertNotIn(self.habit1.action, [h['action'] for h in response.data['results']])

    def test_retrieve_other_users_habit_forbidden(self):
        """Пользователь не должен получать детали чужой привычки."""
        response = self.client.get(reverse('habits:habit-detail', kwargs={'pk': self.public_habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_other_users_habit_forbidden(self):
        """Пользователь не должен обновлять чужую привычку."""
        updated_data = {"action": "Действие чужой привычки"}
        response = self.client.patch(reverse('habits:habit-detail', kwargs={'pk': self.public_habit.pk}), updated_data,
                                     format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)  # 404, т.к. get_queryset фильтрует
        self.assertEqual(Habit.objects.get(pk=self.public_habit.pk).action, self.public_habit.action)

    def test_delete_other_users_habit_forbidden(self):
        """Пользователь не должен удалять чужую привычку."""
        response = self.client.delete(reverse('habits:habit-detail', kwargs={'pk': self.public_habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_forbidden(self):
        """Неаутентифицированный пользователь не может получить доступ к своим привычкам."""
        self.client.credentials()
        response = self.client.get(reverse('habits:habit-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Тесты публичных привычек ---
    def test_list_public_habits(self):
        """Тестирование получения списка публичных привычек."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.user1_access_token)
        response = self.client.get(reverse('habits:habit_public_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['action'], self.public_habit.action)

    def test_public_habit_create_forbidden(self):
        """Нельзя создать привычку через эндпоинт публичных привычек."""
        data = self.habit_data.copy()
        response = self.client.post(reverse('habits:habit_public_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_public_habit_update_forbidden_public_endpoint(self):
        """Нельзя обновить привычку через эндпоинт публичных привычек."""
        data = {"action": "Обновление публичной привычки"}
        response = self.client.patch(reverse('habits:habit_public_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # --- Тесты валидаторов (HabitSerializer.validate) ---
    def test_create_habit_with_reward_and_related_habit_fail(self):
        """Нельзя одновременно иметь вознаграждение и связанную привычку."""
        data = self.habit_data.copy()
        data['related_habit'] = self.pleasant_habit.pk
        data['reward'] = "Какая-то награда"
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Нельзя одновременно выбрать вознаграждение и связанную привычку.",
                      response.data['non_field_errors'][0])

    def test_create_pleasant_habit_with_reward_fail(self):
        """Приятная привычка не может иметь вознаграждения."""
        data = self.pleasant_habit_data.copy()
        data['reward'] = "Награда для приятной привычки"
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Приятная привычка не может иметь вознаграждения или связанной привычки.",
                      response.data['non_field_errors'][0])

    def test_create_pleasant_habit_with_related_habit_fail(self):
        """Приятная привычка не может иметь связанную привычку."""
        data = self.pleasant_habit_data.copy()
        data['related_habit'] = self.habit1.pk
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("В связанные привычки можно добавлять только приятные привычки.",
                      str(response.data['related_habit'][0]))

    def test_create_habit_with_non_pleasant_related_habit_fail(self):
        """В связанные привычки можно добавлять только приятные привычки."""
        data = self.habit_data.copy()
        data.pop('reward')
        data['related_habit'] = self.habit1.pk
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("В связанные привычки можно добавлять только приятные привычки.",
                      response.data['related_habit'][0])

    def test_create_habit_duration_exceeds_120_seconds_fail(self):
        """Время выполнения не должно превышать 120 секунд."""
        data = self.habit_data.copy()
        data['duration'] = 121
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Время на выполнение привычки не должно превышать 120 секунд.", response.data['duration'][0])

    def test_create_habit_periodicity_more_than_7_days_fail(self):
        """Периодичность не должна быть более 7 дней."""
        data = self.habit_data.copy()
        data['periodicity'] = 8
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Периодичность должна быть от 1 до 7 дней.", response.data['periodicity'][0])

    def test_create_useful_habit_no_reward_or_related_fail(self):
        """Полезная привычка без вознаграждения и связанной привычки должна выдать ошибку."""
        data = self.habit_data.copy()
        data['reward'] = None
        data['related_habit'] = None
        response = self.client.post(reverse('habits:habit-list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Для полезной привычки необходимо указать либо вознаграждение, либо связанную привычку.",
                      response.data['non_field_errors'][0])

    # --- Тесты эндпоинта complete_habit ---
    def test_complete_useful_habit_success(self):
        """Тестирование успешного выполнения полезной привычки (без связанной)."""
        habit = self.habit1
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(reverse('habits:habit-complete', kwargs={'pk': habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIn("Привычка успешно отмечена как выполненная.", response.data['message'])
        self.assertEqual(response.data['habit_id'], habit.pk)

    def test_complete_habit_with_related_pleasant_habit_success(self):
        """Тестирование выполнения полезной привычки со связанной приятной."""
        habit = self.habit_with_related
        pleasant_habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)
        self.assertIsNone(pleasant_habit.last_completed_at)

        response = self.client.post(reverse('habits:habit-complete', kwargs={'pk': habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        habit.refresh_from_db()
        pleasant_habit.refresh_from_db()
        self.assertIsNotNone(habit.last_completed_at)
        self.assertIsNotNone(pleasant_habit.last_completed_at)
        self.assertIn("Полезная привычка и связанная приятная привычка отмечены как выполненные.",
                      response.data['message'])
        self.assertEqual(response.data['habit_id'], habit.pk)
        self.assertEqual(response.data['related_habit_id'], pleasant_habit.pk)

    def test_complete_pleasant_habit_directly_fail(self):
        """Нельзя напрямую отметить приятную привычку."""
        habit = self.pleasant_habit
        self.assertIsNone(habit.last_completed_at)

        response = self.client.post(reverse('habits:habit-complete', kwargs={'pk': habit.pk}))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Невозможно отметить приятную привычку как выполненную напрямую.", response.data['detail'])
        habit.refresh_from_db()
        self.assertIsNone(habit.last_completed_at)

    def test_complete_other_users_habit_forbidden(self):
        """Нельзя отметить чужую привычку."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + self.user2_access_token)
        response = self.client.post(reverse('habits:habit-complete', kwargs={'pk': self.habit1.pk}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)

    # --- Тесты Model.clean() ---
    def test_model_clean_reward_and_related_habit_fail(self):
        """Тест clean(): Нельзя одновременно иметь вознаграждение и связанную привычку."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=False, periodicity=1, duration=30,
                      reward="Reward", related_habit=self.pleasant_habit)
        with self.assertRaisesMessage(ValidationError,
                                      "Нельзя одновременно выбрать вознаграждение и связанную привычку."):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_reward_fail(self):
        """Тест clean(): Приятная привычка не может иметь вознаграждения."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=True, periodicity=1, duration=30,
                      reward="Reward")
        with self.assertRaisesMessage(ValidationError,
                                      "Приятная привычка не может иметь вознаграждения или связанной привычки."):
            habit.full_clean()

    def test_model_clean_pleasant_habit_with_related_habit_fail(self):
        """Тест clean(): Приятная привычка не может иметь связанную привычку."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=True, periodicity=1, duration=30,
                      related_habit=self.pleasant_habit)
        with self.assertRaisesMessage(ValidationError,
                                      "Приятная привычка не может иметь вознаграждения или связанной привычки."):
            habit.full_clean()

    def test_model_clean_non_pleasant_related_habit_fail(self):
        """Тест clean(): В связанные привычки можно добавлять только приятные привычки."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=False, periodicity=1, duration=30,
                      related_habit=self.habit1)  # self.habit1 не приятная
        with self.assertRaisesMessage(ValidationError,
                                      "В связанные привычки можно добавлять только приятные привычки."):
            habit.full_clean()

    def test_model_clean_duration_exceeds_120_seconds_fail(self):
        """Тест clean(): Время на выполнение привычки не должно превышать 120 секунд."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=False, periodicity=1, duration=121, reward="R")
        with self.assertRaisesMessage(ValidationError, "Время на выполнение привычки не должно превышать 120 секунд."):
            habit.full_clean()

    def test_model_clean_periodicity_more_than_7_days_fail(self):
        """Тест clean(): Периодичность не должна быть более 7 дней."""
        habit = Habit(user=self.user1, action="Test", place="Place", time=time(9, 0),
                      is_pleasant=False, periodicity=8, duration=30, reward="R")
        with self.assertRaisesMessage(ValidationError,
                                      "Периодичность должна быть от 1 до 7 дней (нельзя выполнять привычку реже, чем 1 раз в 7 дней)."):
            habit.full_clean()

    # --- Тесты Celery-тасок ---
    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')  # Патчим асинхронную обертку
    @patch('django.utils.timezone.now', side_effect=[
        datetime(2025, 1, 1, 9, 0, 0, tzinfo=pytz.utc),
        datetime(2025, 1, 1, 9, 0, 0, tzinfo=pytz.utc)
    ])
    def test_send_telegram_notification_success(self, mock_now, mock_send_message_delay):
        """Тестирование успешной отправки уведомления для полезной привычки."""
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(9, 0)
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        # Проверяем, что _send_telegram_message_async_wrapper.delay был вызван
        mock_send_message_delay.assert_called_once()
        called_kwargs = mock_send_message_delay.call_args[1]  # Получаем kwargs
        self.assertIn(self.habit1.telegram_chat_id, called_kwargs['chat_id'])
        self.assertIn(self.habit1.action, called_kwargs['message_text'])

        self.habit1.refresh_from_db()
        self.assertIsNotNone(self.habit1.last_notification_sent)
        self.assertEqual(self.habit1.last_notification_sent.date(), mock_now().date())

    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')
    def test_send_telegram_notification_no_chat_id(self, mock_send_message_delay):
        """Тестирование, что уведомление не отправляется, если нет chat_id."""
        self.habit1.telegram_chat_id = ""
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_not_called()
        self.habit1.refresh_from_db()
        self.assertIsNone(self.habit1.last_completed_at)
        self.assertIsNone(self.habit1.last_notification_sent)

    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')
    def test_send_telegram_notification_pleasant_habit_skipped(self, mock_send_message_delay):
        """Тестирование, что уведомление не отправляется для приятной привычки."""
        self.pleasant_habit.telegram_chat_id = "123456789"
        self.pleasant_habit.save()

        send_telegram_notification(self.pleasant_habit.id)

        mock_send_message_delay.assert_not_called()
        self.pleasant_habit.refresh_from_db()
        self.assertIsNone(self.pleasant_habit.last_completed_at)
        self.assertIsNone(self.pleasant_habit.last_notification_sent)

    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')
    @patch('django.utils.timezone.now', return_value=datetime(2025, 1, 1, 9, 0, 0, tzinfo=pytz.utc))
    def test_send_telegram_notification_not_due_yet(self, mock_now, mock_send_message_delay):
        """Тестирование, что send_telegram_notification вызывается, даже если время еще не пришло,
        но check_and_send_habit_reminders должен предотвратить это."""
        self.habit1.telegram_chat_id = "123456789"
        self.habit1.time = time(10, 0)  # Время уведомления в будущем
        self.habit1.last_notification_sent = None
        self.habit1.save()

        send_telegram_notification(self.habit1.id)

        mock_send_message_delay.assert_called_once()
        self.habit1.refresh_from_db()
        self.assertIsNotNone(self.habit1.last_notification_sent)

    @patch('habits.tasks.send_telegram_notification')
    @patch('django.utils.timezone.now')
    def test_check_and_send_habit_reminders_daily(self, mock_now, mock_send_notification):
        """Тестирование check_and_send_habit_reminders с ежедневной периодичностью."""
        test_now_initial = datetime(2025, 1, 5, 9, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 1
        self.habit1.last_notification_sent = datetime(2025, 1, 4, 8, 30, 0, tzinfo=pytz.utc)
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        # Проверяем, что send_telegram_notification была вызвана для habit1
        mock_send_notification.delay.assert_called_once_with(self.habit1.id)

        # Симулируем обновление last_notification_sent самой задачей Celery
        Habit.objects.filter(pk=self.habit1.pk).update(last_notification_sent=test_now_initial)
        self.habit1.refresh_from_db()  # Обновляем локальный объект

        self.assertEqual(self.habit1.last_notification_sent.date(), test_now_initial.date())

        mock_send_notification.delay.reset_mock()  # Сбрасываем мок для следующего этапа

        # Устанавливаем время на более позднее в тот же день (10:00)
        test_now_later_today = datetime(2025, 1, 5, 10, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_later_today
        check_and_send_habit_reminders()

        # Проверяем, что send_telegram_notification НЕ была вызвана повторно сегодня
        mock_send_notification.delay.assert_not_called()

        mock_send_notification.delay.reset_mock()

        # Устанавливаем время на следующий день (6 января, 9:00)
        test_now_next_day = datetime(2025, 1, 6, 9, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_next_day
        check_and_send_habit_reminders()

        # Проверяем, что send_telegram_notification была вызвана на следующий день
        mock_send_notification.delay.assert_called_once_with(self.habit1.id)
        # Симулируем обновление last_notification_sent
        Habit.objects.filter(pk=self.habit1.pk).update(last_notification_sent=test_now_next_day)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.last_notification_sent.date(), test_now_next_day.date())

    @patch('habits.tasks.send_telegram_notification')
    @patch('django.utils.timezone.now')
    def test_check_and_send_habit_reminders_multiple_days(self, mock_now, mock_send_notification):
        """Тестирование check_and_send_habit_reminders с периодичностью > 1 дня."""
        test_now_initial = datetime(2025, 1, 7, 9, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_initial

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.periodicity = 3  # Периодичность 3 дня
        self.habit1.last_notification_sent = datetime(2025, 1, 4, 8, 30, 0, tzinfo=pytz.utc)  # Отправлено 4 января
        self.habit1.is_pleasant = False
        self.habit1.save()

        check_and_send_habit_reminders()

        # Проверяем, что send_telegram_notification была вызвана для habit1 (должно быть 7 января)
        mock_send_notification.delay.assert_called_once_with(self.habit1.id)

        # Симулируем обновление last_notification_sent
        Habit.objects.filter(pk=self.habit1.pk).update(last_notification_sent=test_now_initial)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.last_notification_sent.date(), test_now_initial.date())

        mock_send_notification.delay.reset_mock()

        # Устанавливаем время на следующий день (8 января, 9:00) - еще не должно быть отправлено (periodicity=3)
        test_now_next_day_not_due = datetime(2025, 1, 8, 9, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_next_day_not_due
        check_and_send_habit_reminders()
        mock_send_notification.delay.assert_not_called()

        mock_send_notification.delay.reset_mock()

        # Устанавливаем время на 10 января, 9:00 - должно быть отправлено (7 + 3 = 10)
        test_now_due_again = datetime(2025, 1, 10, 9, 0, 0, tzinfo=pytz.utc)
        mock_now.return_value = test_now_due_again
        check_and_send_habit_reminders()

        # Проверяем, что send_telegram_notification была вызвана
        mock_send_notification.delay.assert_called_once_with(self.habit1.id)
        # Симулируем обновление last_notification_sent
        Habit.objects.filter(pk=self.habit1.pk).update(last_notification_sent=test_now_due_again)
        self.habit1.refresh_from_db()
        self.assertEqual(self.habit1.last_notification_sent.date(), test_now_due_again.date())

    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')
    @patch('django.utils.timezone.now', return_value=datetime(2025, 1, 1, 7, 0, 0, tzinfo=pytz.utc))
    def test_check_and_send_habit_reminders_not_due_time_today(self, mock_now, mock_send_message_delay):
        """Тестирование check_and_send_habit_reminders: время уведомления еще не наступило сегодня."""
        mock_now.return_value = datetime(2025, 1, 1, 7, 0, 0, tzinfo=pytz.utc)

        self.habit1.telegram_chat_id = "chat_id_1"
        self.habit1.time = time(8, 0)
        self.habit1.last_notification_sent = None
        self.habit1.is_pleasant = False
        self.habit1.periodicity = 1
        self.habit1.save()

        check_and_send_habit_reminders()
        mock_send_message_delay.assert_not_called()

    @patch('habits.tasks._send_telegram_message_async_wrapper.delay')
    @patch('django.utils.timezone.now', return_value=datetime(2025, 1, 1, 9, 0, 0, tzinfo=pytz.utc))
    def test_check_and_send_habit_reminders_no_chat_id_or_pleasant(self, mock_now, mock_send_message_delay):
        """Тестирование check_and_send_habit_reminders: не отправляется для приятных или без chat_id."""
        # Приятная привычка
        self.pleasant_habit.telegram_chat_id = "chat_id_pleasant"
        self.pleasant_habit.is_pleasant = True
        self.pleasant_habit.time = time(8, 0)
        self.pleasant_habit.save()

        # Полезная привычка без chat_id
        self.public_habit.telegram_chat_id = ""  # Пустой chat_id
        self.public_habit.is_pleasant = False
        self.public_habit.time = time(8, 0)
        self.public_habit.save()

        check_and_send_habit_reminders()
        mock_send_message_delay.assert_not_called()
