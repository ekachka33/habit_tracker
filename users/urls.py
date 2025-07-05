from django.urls import path

from users.apps import UsersConfig
from users.views import UserRegisterAPIView

# If you have a ViewSet for User, but apparently not
# from rest_framework.routers import DefaultRouter


app_name = UsersConfig.name  # VERY IMPORTANT: defines the 'users' namespace

# router = DefaultRouter()
# router.register(r'users', UserViewSet, basename='user') # Example if UserViewSet existed

urlpatterns = [
    # Path for user registration
    path(
        "register/",
        UserRegisterAPIView.as_view(),
        name="user_register",
    ),
    # If there was a router, then like this:
    # path('', include(router.urls)),
]
