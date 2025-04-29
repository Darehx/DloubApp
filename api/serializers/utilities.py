# api/serializers/utilities.py
"""
Serializers para utilidades como Notificaciones y Logs de Auditoría.
"""
from rest_framework import serializers

# Importar modelos necesarios
from ..models import Notification, AuditLog

# Importar serializers base/relacionados
from .base import BasicUserSerializer # Para mostrar info de usuario

class NotificationSerializer(serializers.ModelSerializer):
    """ Serializer para MOSTRAR notificaciones. """
    # Mostrar info básica del usuario receptor
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'read', 'created_at', 'link']
        # Este serializer es principalmente para lectura desde la vista
        read_only_fields = fields

class AuditLogSerializer(serializers.ModelSerializer):
    """ Serializer para MOSTRAR logs de auditoría. """
    # Mostrar info básica del usuario que realizó la acción
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'action', 'timestamp', 'target_model', 'target_id', # Añadido target
            'ip_address', 'details' # Añadido IP
            ]
        read_only_fields = fields # Solo lectura