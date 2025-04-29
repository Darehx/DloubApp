# api/serializers/customers.py
"""
Serializers específicos para el modelo Customer.
"""
import logging
from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Importar modelos necesarios
from ..models import Customer, UserRole, UserProfile

# Importar serializers relacionados
from .base import BasicUserSerializer
from .users import UserCreateSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

class CustomerSerializer(serializers.ModelSerializer):
    """ Serializer para LEER información de un cliente. """
    user = BasicUserSerializer(read_only=True) # Muestra info completa del usuario asociado
    country_display = serializers.CharField(source='get_country_display', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'user', 'phone', 'address', 'date_of_birth', 'country',
            'country_display', 'company_name', 'created_at',
            'preferred_contact_method', 'brand_guidelines'
        ]
        read_only_fields = ['id', 'created_at', 'user', 'country_display']

class CustomerCreateSerializer(serializers.ModelSerializer):
    """ Serializer para CREAR un nuevo cliente y su usuario asociado. """
    user = UserCreateSerializer(write_only=True) # Serializer anidado para datos del usuario
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True,
        help_text=_("ID del rol principal obligatorio para este cliente.")
    )
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Customer
        fields = [
            'user', 'primary_role', 'phone', 'address', 'date_of_birth',
            'country', 'company_name', 'preferred_contact_method', 'brand_guidelines'
        ]

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        customer_specific_data = validated_data

        # Re-validar unicidad (doble chequeo)
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        # Crear usuario
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        # Asignar is_staff y rol primario
        user.is_staff = False # Clientes NO son staff
        user.save(update_fields=['is_staff'])

        try:
            # Asumiendo que la señal post_save crea UserProfile
            user_profile, profile_created = UserProfile.objects.get_or_create(user=user)
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean()
        except UserProfile.DoesNotExist:
             # Loggear y fallar si no se creó el perfil (muy raro si la señal funciona)
             logger.error(f"Error crítico: No se encontró/creó UserProfile para el usuario {user.username}")
             raise ValidationError(_("Error interno al inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a {user.username}: {e.message_dict}")
             user.delete() # Rollback manual
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', _('Error asignando rol primario.'))})

        # Crear perfil de Cliente
        customer = Customer.objects.create(user=user, **customer_specific_data)

        # Devolver la instancia de Customer creada
        return customer