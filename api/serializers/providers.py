# api/serializers/providers.py
"""
Serializers para Proveedores.
"""
from rest_framework import serializers

# Importar modelos necesarios
from ..models import Provider, Service

# Importar serializers relacionados
from .services_catalog import ServiceSerializer # Para mostrar detalles de servicios

class ProviderSerializer(serializers.ModelSerializer):
    """ Serializer para leer/escribir información de Proveedores. """
    # Mostrar detalles de servicios (lectura)
    services_provided_details = ServiceSerializer(source='services_provided', many=True, read_only=True)
    # Campo para escribir (asignar servicios por ID)
    services_provided = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), many=True, write_only=True, required=False
    )

    class Meta:
        model = Provider
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'rating',
            'is_active', 'notes',
            'services_provided',             # Para escribir
            'services_provided_details'      # Para leer
        ]
        read_only_fields = ['id', 'services_provided_details']
        # 'services_provided' es write_only por definición