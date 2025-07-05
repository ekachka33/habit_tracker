from rest_framework.pagination import PageNumberPagination


class HabitPagination(PageNumberPagination):
    """
    Кастомный класс пагинации для привычек.
    Выводит по 5 привычек на страницу.
    """

    page_size = 5  # Количество элементов на странице
    # Параметр запроса для установки page_size (опционально)
    page_size_query_param = "page_size"
    max_page_size = 100  # Максимальное количество элементов на странице
