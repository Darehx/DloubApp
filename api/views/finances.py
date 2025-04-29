# api/views/finances.py
import logging
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import Invoice, Payment, Order, Customer # Añadir Method/Type si hay ViewSet
from ..permissions import IsAuthenticated, CanManageFinances, IsCustomerOwnerOrAdminOrSupport

# --- Importaciones de Serializers Corregidas ---
from ..serializers.finances import (
    InvoiceSerializer, InvoiceBasicSerializer,
    PaymentReadSerializer, PaymentCreateSerializer
    # Añadir Method/Type si hay ViewSet para ellos
    # PaymentMethodSerializer, TransactionTypeSerializer
)
# ----------------------------------------------

logger = logging.getLogger(__name__)
User = get_user_model()

class InvoiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Facturas (Invoices).
    """
    queryset = Invoice.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'status': ['exact', 'in'],
        'order__customer__user__username': ['exact', 'icontains'],
        'order__customer__company_name': ['icontains'],
        'order__id': ['exact'],
        'date': ['date', 'date__gte', 'date__lte', 'year', 'month'],
        'due_date': ['date', 'date__gte', 'date__lte', 'isnull'],
        'invoice_number': ['exact', 'icontains'],
        'total_amount': ['exact', 'gte', 'lte'],
    }

    def get_serializer_class(self):
        """ Usa un serializer básico para la lista, completo para otros. """
        # Usa los serializers importados correctamente
        if self.action == 'list':
            return InvoiceBasicSerializer
        return InvoiceSerializer

    def get_queryset(self):
        # ... (lógica sin cambios) ...
        user = self.request.user
        base_qs = Invoice.objects.select_related(
            'order', 'order__customer', 'order__customer__user',
            'order__employee', 'order__employee__user'
        ).prefetch_related('payments__method')

        if hasattr(user, 'customer_profile') and user.customer_profile:
            return base_qs.filter(order__customer=user.customer_profile)
        elif hasattr(user, 'employee_profile'):
            checker = CanManageFinances()
            if checker.has_permission(request=self.request, view=self):
                return base_qs.all()
            else:
                return Invoice.objects.none()
        else:
            return Invoice.objects.none()

    def perform_create(self, serializer):
        # ... (lógica sin cambios) ...
        checker = CanManageFinances()
        if not checker.has_permission(request=self.request, view=self):
            raise PermissionDenied(checker.message)
        serializer.save() # InvoiceSerializer.create manejará la lógica

    def perform_update(self, serializer):
        # ... (lógica sin cambios) ...
        checker = CanManageFinances()
        if not checker.has_permission(request=self.request, view=self):
             raise PermissionDenied(checker.message)
        if hasattr(self.request.user, 'customer_profile'):
             raise PermissionDenied(_("Los clientes no pueden modificar facturas."))
        serializer.save() # InvoiceSerializer.update manejará la lógica

    def perform_destroy(self, instance):
        # ... (lógica sin cambios) ...
        checker = CanManageFinances()
        if not checker.has_permission(request=self.request, view=self):
             raise PermissionDenied(checker.message)
        if hasattr(self.request.user, 'customer_profile'):
             raise PermissionDenied(_("Los clientes no pueden eliminar facturas."))
        instance.delete()


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Pagos (Payments).
    """
    queryset = Payment.objects.select_related(
        'invoice', 'invoice__order', 'invoice__order__customer',
        'invoice__order__customer__user', 'method', 'transaction_type'
    ).all()
    permission_classes = [CanManageFinances]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'status': ['exact', 'in'],
        'method': ['exact'], 'method__name': ['exact', 'icontains'],
        'transaction_type': ['exact'], 'transaction_type__name': ['exact', 'icontains'],
        'currency': ['exact'],
        'invoice__invoice_number': ['exact', 'icontains'],
        'invoice__order__id': ['exact'],
        'invoice__order__customer__user__username': ['exact', 'icontains'],
        'date': ['date', 'date__gte', 'date__lte', 'year', 'month'],
        'amount': ['exact', 'gte', 'lte'],
    }

    def get_serializer_class(self):
        """ Serializer de lectura para list/retrieve, de creación/edición para otros. """
        # Usa los serializers importados correctamente
        if self.action in ['list', 'retrieve']:
            return PaymentReadSerializer
        return PaymentCreateSerializer

    # La lógica de actualizar estado de factura se movió a PaymentCreateSerializer.save()
    # o se puede manejar con señales post_save/post_delete en el modelo Payment.
    # Estos métodos perform_* solo necesitan llamar a serializer.save() o instance.delete().

    def perform_create(self, serializer):
        # La lógica de validación y posible actualización de factura está en el serializer
        serializer.save()

    def perform_update(self, serializer):
        # La lógica de validación y posible actualización de factura está en el serializer
        serializer.save()

    def perform_destroy(self, instance):
        # La lógica para actualizar factura post-delete debería estar en una señal
        invoice = instance.invoice # Guardar referencia si la señal la necesita
        payment_id = instance.id
        instance.delete()
        # Idealmente, una señal post_delete en Payment llamaría a invoice.update_status()
        # logger.info(f"Estado de factura {invoice.id} actualizado tras eliminación de pago {payment_id}")