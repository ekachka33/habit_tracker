from rest_framework.pagination import PageNumberPagination

class HabitPagination(PageNumberPagination):
    """
    Кастомный класс пагинации для привычек.
    Выводит по 5 привычек на страницу.
    """
    page_size = 5 # Количество элементов на странице
    page_size_query_param = 'page_size' # Параметр запроса для установки page_size (опционально)
    max_page_size = 100 # Максимальное количество элементов на странице