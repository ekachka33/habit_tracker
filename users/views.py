from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
# from rest_framework_simplejwt.views import TokenObtainPairView # Не нужен, если токены генерируются в сериализаторе
from rest_framework_simplejwt.tokens import RefreshToken # Используется в serializers, здесь не обязательно


from users.serializers import UserRegisterSerializer # Используем UserRegisterSerializer

User = get_user_model()

class UserRegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save() # user здесь будет иметь access_token и refresh_token из сериализатора

        response_data = {
            'message': 'Пользователь успешно зарегистрирован.',
            'user': UserRegisterSerializer(user).data, # Сериализуем пользователя (без токенов здесь, т.к. они уже на верхнем уровне)
            'access': user.access_token, # Берем access_token из объекта user
            'refresh': user.refresh_token, # Берем refresh_token из объекта user
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

