from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет доступ только владельцам объекта.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.user == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет:
    - Полный доступ владельцу объекта.
    - Только чтение для не-владельцев.
    """

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.user == request.user


class IsPublicHabit(permissions.BasePermission):
    """
    Кастомное разрешение, которое позволяет только чтение для публичных привычек.
    """

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return obj.is_public
        return False
