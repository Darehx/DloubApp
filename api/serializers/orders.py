# api/serializers/orders.py
"""
Serializers para Pedidos, Servicios de Pedido y Entregables.
"""
import logging
from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Importar modelos necesarios
from ..models import Order, OrderService, Deliverable, Service, Employee, Provider, Customer

# Importar serializers relacionados/base
from .base import EmployeeBasicSerializer, ProviderBasicSerializer
from .customers import CustomerSerializer # Para OrderReadSerializer
from .services_catalog import ServiceSerializer # Para OrderServiceReadSerializer

logger = logging.getLogger(__name__)


class OrderServiceCreateSerializer(serializers.ModelSerializer):
    """ Serializer para AÑADIR/ACTUALIZAR servicios en una orden. """
    # Usar PrimaryKeyRelatedField para escribir el ID del servicio
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True),
        required=True
    )
    # Precio opcional, se puede calcular o tomar del servicio
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = OrderService
        # Excluir 'order' ya que se asignará al anidar o en la vista
        fields = ['id', 'service', 'quantity', 'price', 'note']
        read_only_fields = ['id']

    def validate_price(self, value):
        if value is not None and value < Decimal('0.00'):
            raise ValidationError(_("El precio no puede ser negativo."))
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise ValidationError(_("La cantidad debe ser mayor que cero."))
        return value


class OrderServiceReadSerializer(serializers.ModelSerializer):
    """ Serializer para MOSTRAR servicios dentro de una orden. """
    # Mostrar info completa del servicio usando su serializer
    service = ServiceSerializer(read_only=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'quantity', 'price', 'note']
        read_only_fields = fields


class DeliverableSerializer(serializers.ModelSerializer):
    """ Serializer para LEER/ESCRIBIR información de Entregables. """
    # Campos legibles
    assigned_employee_info = EmployeeBasicSerializer(source='assigned_employee', read_only=True)
    assigned_provider_info = ProviderBasicSerializer(source='assigned_provider', read_only=True)
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_url = serializers.SerializerMethodField(read_only=True) # URL del archivo

    # Campos para escribir (asignar por ID)
    assigned_employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(user__is_active=True),
        write_only=True, required=False, allow_null=True
    )
    assigned_provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.filter(is_active=True),
        write_only=True, required=False, allow_null=True
    )
    # Permitir carga de archivo (usar multipart/form-data)
    file = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Deliverable
        fields = [
            'id', 'order_id', 'description', 'version',
            'file', # Para escribir (subir)
            'file_url', # Para leer (URL)
            'status', 'status_display', 'due_date',
            'assigned_employee', 'assigned_employee_info', # write / read
            'assigned_provider', 'assigned_provider_info', # write / read
            'feedback_notes', 'created_at'
        ]
        read_only_fields = [
            'id', 'order_id', 'version', 'created_at', 'status_display', 'file_url',
            'assigned_employee_info', 'assigned_provider_info'
        ]
        # 'file' es write_only por definición de FileField aquí

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        elif obj.file:
            return obj.file.url # Fallback si no hay request
        return None

class OrderReadSerializer(serializers.ModelSerializer):
    """ Serializer para LEER detalles completos de una orden. """
    customer = CustomerSerializer(read_only=True)
    employee = EmployeeBasicSerializer(read_only=True)
    services = OrderServiceReadSerializer(many=True, read_only=True)
    deliverables = DeliverableSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Calculado en modelo/señal

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'status_display',
            'date_received', 'date_required', 'payment_due_date', 'note',
            'priority', 'completed_at', 'total_amount', 'services', 'deliverables'
        ]
        read_only_fields = fields # Solo lectura


class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    """ Serializer para CREAR o ACTUALIZAR una orden. """
    # Campos para escribir (FKs por ID)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=True)
    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(user__is_active=True),
        required=False, allow_null=True
    )
    # Anidar el serializer de creación/actualización de servicios
    services = OrderServiceCreateSerializer(many=True, required=False) # Lista de servicios

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'date_required',
            'payment_due_date', 'note', 'priority', 'services'
        ]
        read_only_fields = ['id']

    def _create_or_update_services(self, order, services_data):
        """ Helper para crear/actualizar servicios anidados. """
        # Mapear IDs existentes vs nuevos
        current_service_mapping = {s.id: s for s in order.services.all()}
        incoming_service_mapping = {item.get('id'): item for item in services_data if item.get('id')}
        ids_to_update = set(current_service_mapping.keys()) & set(incoming_service_mapping.keys())
        ids_to_delete = set(current_service_mapping.keys()) - ids_to_update
        data_to_create = [item for item in services_data if not item.get('id')]

        # Eliminar los que ya no están
        if ids_to_delete:
            OrderService.objects.filter(order=order, id__in=ids_to_delete).delete()

        # Actualizar los existentes
        for service_id in ids_to_update:
            instance = current_service_mapping[service_id]
            service_data = incoming_service_mapping[service_id]
            service_obj = service_data.get('service') # PKRelatedField ya validó

            # Obtener precio si no se especificó
            price = service_data.get('price')
            if price is None and service_obj:
                current_price_obj = service_obj.get_current_price(currency='EUR') # Asume EUR o ajusta
                price = current_price_obj.amount if current_price_obj else Decimal('0.00')

            # Actualizar instancia
            instance.service = service_obj
            instance.quantity = service_data.get('quantity', instance.quantity)
            instance.price = price
            instance.note = service_data.get('note', instance.note)
            # No guardar aquí, hacerlo en bulk_update si es posible
            # instance.save() # Alternativa si no hay bulk_update

        # Crear los nuevos
        services_to_create_bulk = []
        for service_data in data_to_create:
            service_obj = service_data.get('service')
            price = service_data.get('price')
            if price is None and service_obj:
                 current_price_obj = service_obj.get_current_price(currency='EUR')
                 price = current_price_obj.amount if current_price_obj else Decimal('0.00')

            services_to_create_bulk.append(OrderService(
                order=order,
                service=service_obj,
                quantity=service_data.get('quantity', 1),
                price=price,
                note=service_data.get('note', '')
            ))

        if services_to_create_bulk:
            OrderService.objects.bulk_create(services_to_create_bulk)

        # Actualizar (si hay cambios y Django >= 4)
        # services_to_update = [current_service_mapping[sid] for sid in ids_to_update]
        # if services_to_update:
        #     OrderService.objects.bulk_update(services_to_update, ['service', 'quantity', 'price', 'note'])


    @transaction.atomic
    def create(self, validated_data):
        services_data = validated_data.pop('services', [])
        order = Order.objects.create(**validated_data)
        self._create_or_update_services(order, services_data)
        # La señal post_save/delete de OrderService debería recalcular total_amount
        order.refresh_from_db()
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        services_data = validated_data.pop('services', None) # None si no se envía el campo
        # Actualizar campos de Order
        instance = super().update(instance, validated_data)

        if services_data is not None: # Si se envió el campo 'services' (incluso vacío)
            self._create_or_update_services(instance, services_data)

        # Señal debería recalcular total_amount
        instance.refresh_from_db()
        return instance