# api/serializers/users.py
"""
Serializers para la gestión de usuarios, roles y asignaciones.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Importar modelos necesarios
from ..models import UserRole, UserRoleAssignment

# Importar serializers base/relacionados
from .base import BasicUserSerializer

User = get_user_model()

class UserCreateSerializer(serializers.ModelSerializer):
    """ Serializer para crear nuevos usuarios. """
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirmar Contraseña")

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email': {'required': True} # Email es obligatorio
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise ValidationError({"password": "Las contraseñas no coinciden."})
        # Validar email único
        email = attrs.get('email')
        if email and User.objects.filter(email=email).exists():
             raise ValidationError({'email': _('Ya existe un usuario con este email.')})
        # Validar username único
        username = attrs.get('username')
        if username and User.objects.filter(username=username).exists():
             raise ValidationError({'username': _('Ya existe un usuario con este nombre de usuario.')})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2', None)
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'], # create_user hashea
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        # is_staff se maneja en CustomerCreate/EmployeeCreate
        return user

class UserRoleSerializer(serializers.ModelSerializer):
    """ Serializer para el modelo UserRole. """
    class Meta:
        model = UserRole
        fields = ['id', 'name', 'display_name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    """ Serializer para gestionar asignaciones de roles secundarios. """
    # Mostrar info del usuario y rol (lectura)
    user_info = BasicUserSerializer(source='user', read_only=True)
    role_info = UserRoleSerializer(source='role', read_only=True)
    # Campos para crear/actualizar (escritura)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
    role = serializers.PrimaryKeyRelatedField(queryset=UserRole.objects.filter(is_active=True), write_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = ['id', 'user', 'user_info', 'role', 'role_info', 'is_active', 'assigned_at', 'updated_at']
        read_only_fields = ['id', 'user_info', 'role_info', 'assigned_at', 'updated_at']