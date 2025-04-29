# api/serializers/authentication.py
"""
Serializers relacionados con la autenticación y obtención de tokens.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

# Importar serializers base necesarios
from .base import BasicUserSerializer

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        try:
            # Optimización: Cargar datos necesarios para BasicUserSerializer
            user = User.objects.select_related(
                'profile__primary_role',
                'employee_profile__position'
            ).prefetch_related(
                'secondary_role_assignments__role'
            ).get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed(_("El usuario no existe."), code="user_not_found")

        if not user.check_password(password):
            raise AuthenticationFailed(_("Contraseña incorrecta."), code="invalid_credentials")

        if not user.is_active:
            raise AuthenticationFailed(_("Tu cuenta está inactiva."), code="user_inactive")

        data = super().validate(attrs) # Obtiene access y refresh

        # Añadir datos del usuario usando BasicUserSerializer
        user_data = BasicUserSerializer(user).data # 'user' ya tiene datos precargados
        data.update({'user': user_data})
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Añadir claims personalizados al token JWT
        token['roles'] = user.get_all_active_role_names
        token['primary_role'] = user.primary_role_name
        token['username'] = user.username
        token['is_dragon'] = user.is_dragon()
        return token