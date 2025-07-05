from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from users.serializers import UserRegisterSerializer

# Not needed if tokens are generated in the serializer
# from rest_framework_simplejwt.views import TokenObtainPairView
# Used in serializers, not necessarily here
# from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class UserRegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # user will have access_token and refresh_token from the serializer
        user = serializer.save()

        response_data = {
            "message": "Пользователь успешно зарегистрирован.",
            # Serialize the user (without tokens here, as they are already top-level)
            "user": UserRegisterSerializer(user).data,
            "access": user.access_token,  # Get access_token from user object
            "refresh": user.refresh_token,  # Get refresh_token from user object
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
