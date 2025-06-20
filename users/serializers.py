# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    """
    Сериализатор для регистрации нового пользователя.
    Требует username, email и подтверждение пароля.
    """
    password = serializers.CharField(write_only=True, required=True, min_length=8, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, min_length=8, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2') # Оставил только обязательные для регистрации
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {'required': True}, # Явно указываем, что username требуется
            'email': {'required': True}    # Явно указываем, что email требуется
        }

    def validate(self, data):
        # Валидация совпадения паролей
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Пароли не совпадают."})

        # Валидация уникальности email
        if User.objects.filter(email=data.get('email')).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже существует."})

        return data

    def create(self, validated_data):
        # Удаляем поле подтверждения пароля, так как оно не является полем модели
        validated_data.pop('password2')
        # Создаем пользователя, используя create_user для правильного хеширования пароля
        user = User.objects.create_user(**validated_data)
        return user