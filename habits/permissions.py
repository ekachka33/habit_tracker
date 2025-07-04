from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет доступ только владельцам объекта.
    """
    def has_object_permission(self, request, view, obj):
        # Разрешение на чтение разрешено для любых запросов.
        # GET, HEAD или OPTIONS запросы разрешены всегда.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Разрешение на запись разрешено только владельцу объекта.
        return obj.user == request.user

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет:
    - Полный доступ владельцу объекта.
    - Только чтение для не-владельцев.
    """
    def has_object_permission(self, request, view, obj):
        # Разрешение на чтение разрешено для любых запросов.
        # GET, HEAD или OPTIONS запросы разрешены всегда.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Разрешение на запись (PUT, PATCH, DELETE) разрешено только владельцу объекта.
        return obj.user == request.user

class IsPublicHabit(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет только чтение для публичных привычек.
    """
    def has_permission(self, request, view):
        # Только POST-запросы (создание) не разрешены для этого ViewSet'а.
        # Разрешаем GET/HEAD/OPTIONS (безопасные методы) для всех аутентифицированных пользователей.
        return request.method in permissions.SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        # Для GET/HEAD/OPTIONS разрешаем, если привычка публичная.
        if request.method in permissions.SAFE_METHODS:
            return obj.is_public
        # Для других методов (PUT, PATCH, DELETE) не разрешаем.
        return False