# api/serializers/base.py
"""
Contiene serializers base o comunes usados en múltiples módulos.
"""
import logging
from rest_framework import serializers
from django.contrib.auth import get_user_model

# Importar modelos necesarios para estos serializers base
from ..models import Employee, Provider, UserProfile, JobPosition

logger = logging.getLogger(__name__)
User = get_user_model()

class BasicUserSerializer(serializers.ModelSerializer):
    """
    Serializer básico para mostrar información del usuario, incluyendo roles
    y el nombre del puesto de trabajo si es un empleado.
    Optimizado para funcionar con datos precargados (select_related/prefetch_related).
    """
    full_name = serializers.SerializerMethodField(read_only=True)
    primary_role = serializers.CharField(source='primary_role_name', read_only=True, allow_null=True)
    primary_role_display_name = serializers.SerializerMethodField(read_only=True, allow_null=True)
    secondary_roles = serializers.ListField(source='get_secondary_active_role_names', read_only=True, child=serializers.CharField())
    all_roles = serializers.ListField(source='get_all_active_role_names', read_only=True, child=serializers.CharField())
    is_dragon_user = serializers.BooleanField(source='is_dragon', read_only=True)
    job_position_name = serializers.SerializerMethodField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff',
            'primary_role', 'primary_role_display_name', 'secondary_roles',
            'all_roles', 'is_dragon_user', 'job_position_name',
        ]
        # No es necesario read_only_fields aquí para SerializerMethodFields o campos con read_only=True

    def get_full_name(self, obj):
        name = obj.get_full_name()
        return name if name else obj.username

    def get_primary_role_display_name(self, obj):
        primary_role_instance = getattr(obj, 'primary_role', None)
        if primary_role_instance and hasattr(primary_role_instance, 'display_name'):
            return primary_role_instance.display_name
        try:
            # Fallback (menos eficiente)
            profile = getattr(obj, 'profile', None)
            if profile and profile.primary_role:
                return profile.primary_role.display_name
        except UserProfile.DoesNotExist:
             logger.warning(f"Perfil no encontrado para usuario {obj.username} en get_primary_role_display_name.")
        except Exception as e:
            logger.error(f"Error obteniendo display_name de ROL para usuario {obj.username}: {e}")
        return None

    def get_job_position_name(self, obj):
        try:
            employee_profile = getattr(obj, 'employee_profile', None)
            position = getattr(employee_profile, 'position', None)
            if position and hasattr(position, 'name'):
                return position.name
        except Employee.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error inesperado obteniendo job_position_name para {obj.username}: {e}", exc_info=True)
        return None

class EmployeeBasicSerializer(serializers.ModelSerializer):
    """ Serializer muy básico para info mínima de empleado, usando BasicUserSerializer. """
    user = BasicUserSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'user']
        read_only_fields = fields

class ProviderBasicSerializer(serializers.ModelSerializer):
     """ Serializer muy básico para info mínima de proveedor. """
     class Meta:
        model = Provider
        fields = ['id', 'name']
        read_only_fields = fields