# api/serializers/employees.py
"""
Serializers para Empleados y Puestos de Trabajo.
"""
import logging
from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Importar modelos necesarios
from ..models import Employee, JobPosition, UserRole, UserProfile

# Importar serializers relacionados
from .base import BasicUserSerializer
from .users import UserCreateSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

class JobPositionSerializer(serializers.ModelSerializer):
    """ Serializer para el modelo JobPosition. """
    class Meta:
        model = JobPosition
        fields = '__all__'

class EmployeeSerializer(serializers.ModelSerializer):
    """ Serializer para LEER/ACTUALIZAR información de un empleado existente. """
    user = BasicUserSerializer(read_only=True) # Info detallada del usuario (lectura)
    position = JobPositionSerializer(read_only=True) # Info del puesto (lectura)

    # Campo para ACTUALIZAR la posición enviando solo el ID
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(),
        source='position', # Mapea al campo 'position' del modelo Employee
        write_only=True,   # Solo para escritura
        required=False,    # No obligatorio al actualizar otros campos
        allow_null=True    # Permitir desasignar puesto
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'hire_date', 'address', 'salary',
            'position',     # Para lectura
            'position_id'   # Para escritura (actualización)
        ]
        read_only_fields = ['id', 'hire_date', 'user', 'position']

class EmployeeCreateSerializer(serializers.ModelSerializer):
    """ Serializer para CREAR un nuevo empleado y su usuario asociado. """
    user = UserCreateSerializer(write_only=True) # Datos para crear el usuario
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True,
        help_text=_("ID del rol principal obligatorio para este empleado.")
    )
    # Campo para ASIGNAR la posición al crear (ID)
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(),
        source='position', # Mapea al campo 'position' del modelo
        required=False,    # Puesto opcional al crear
        allow_null=True,
        write_only=True    # No se devuelve en la respuesta de creación
    )

    class Meta:
        model = Employee
        fields = [
            'user', 'primary_role', 'position_id',
            'address', 'salary', 'hire_date'
        ]
        extra_kwargs = {
            'hire_date': {'required': False, 'allow_null': True} # Fecha de contratación opcional
        }

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        # 'position' ya está manejado por source='position' en position_id
        employee_specific_data = validated_data

        # Validar unicidad
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        # Crear usuario
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        # Asignar is_staff y rol primario
        user.is_staff = True # Empleados SI son staff
        user.save(update_fields=['is_staff'])

        try:
            # Asignar rol primario al perfil (asume señal o crea)
            user_profile, profile_created = UserProfile.objects.get_or_create(user=user)
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean()
        except UserProfile.DoesNotExist:
             logger.error(f"Error crítico: No se encontró/creó UserProfile para empleado {user.username}")
             raise ValidationError(_("Error interno al inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a empleado {user.username}: {e.message_dict}")
             user.delete() # Rollback
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', _('Error asignando rol primario.'))})

        # Crear perfil de Empleado
        # validated_data contiene 'position' gracias a source='position'
        employee = Employee.objects.create(user=user, **employee_specific_data)
        return employee