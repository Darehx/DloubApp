# api/views/orders.py
import logging
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import Order, Deliverable, Customer, Employee
from ..permissions import (
    IsAuthenticated, CanViewAllOrders, CanCreateOrders,
    CanViewAllDeliverables, CanCreateDeliverables, IsOwnerOrReadOnly,
    IsCustomerOwnerOrAdminOrSupport
)

# --- Importaciones de Serializers Corregidas ---
from ..serializers.orders import (
    OrderReadSerializer, OrderCreateUpdateSerializer, DeliverableSerializer
)
# Nota: OrderService serializers son usados internamente por Order serializers,
# no necesitan importarse aquí a menos que los uses directamente en la vista.
# ----------------------------------------------

logger = logging.getLogger(__name__)
User = get_user_model()

class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Pedidos (Orders).
    """
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'status': ['exact', 'in'],
        'customer__user__username': ['exact', 'icontains'],
        'customer__company_name': ['icontains'],
        'priority': ['exact', 'in'],
        'employee__user__username': ['exact', 'icontains'],
        'date_received': ['date', 'date__gte', 'date__lte', 'year', 'month'],
        'date_required': ['date', 'date__gte', 'date__lte', 'isnull'],
        'id': ['exact']
    }

    def get_serializer_class(self):
        """ Usa serializer de lectura para list/retrieve, y de escritura para otros. """
        # Usa los serializers importados correctamente
        if self.action in ['list', 'retrieve']:
            return OrderReadSerializer
        return OrderCreateUpdateSerializer

    def get_queryset(self):
        # ... (lógica sin cambios) ...
        user = self.request.user
        base_qs = Order.objects.select_related(
            'customer', 'customer__user', 'employee', 'employee__user'
        ).prefetch_related('services__service', 'deliverables')

        if hasattr(user, 'customer_profile') and user.customer_profile:
            return base_qs.filter(customer=user.customer_profile)
        elif hasattr(user, 'employee_profile') and user.employee_profile:
            checker = CanViewAllOrders()
            if checker.has_permission(request=self.request, view=self):
                return base_qs.all()
            else:
                return base_qs.filter(employee=user.employee_profile)
        else:
            logger.warning(f"Usuario {user.username} sin perfil de cliente o empleado válido intentó listar pedidos.")
            return Order.objects.none()

    def perform_create(self, serializer):
        # ... (lógica sin cambios) ...
        user = self.request.user
        customer_data = serializer.validated_data.get('customer')

        if hasattr(user, 'employee_profile') and user.employee_profile:
            checker = CanCreateOrders()
            if not checker.has_permission(request=self.request, view=self):
                raise PermissionDenied(checker.message)
            employee_to_assign = serializer.validated_data.get('employee', user.employee_profile)
            # Guarda usando el OrderCreateUpdateSerializer.create
            serializer.save(employee=employee_to_assign)
        elif hasattr(user, 'customer_profile') and user.customer_profile:
            if customer_data and customer_data != user.customer_profile:
                raise PermissionDenied(_("No puedes crear pedidos para otros clientes."))
            # Guarda usando el OrderCreateUpdateSerializer.create
            serializer.save(customer=user.customer_profile, employee=None)
        else:
            raise PermissionDenied(_("Tu perfil de usuario no es válido para crear pedidos."))

    # perform_update usa OrderCreateUpdateSerializer.update por defecto


class DeliverableViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Entregables (Deliverables) asociados a un Pedido.
    """
    # Usa el serializer importado correctamente
    serializer_class = DeliverableSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'status': ['exact', 'in'],
        'assigned_employee': ['exact', 'isnull'],
        'assigned_provider': ['exact', 'isnull'],
        'due_date': ['date', 'date__gte', 'date__lte', 'isnull'],
        'order': ['exact'],
        'order__customer__user__username': ['exact', 'icontains'],
        'assigned_employee__user__username': ['exact', 'icontains'],
    }

    def get_queryset(self):
        # ... (lógica sin cambios) ...
        user = self.request.user
        order_pk = self.kwargs.get('order_pk')

        base_qs = Deliverable.objects.select_related(
            'order', 'order__customer', 'order__customer__user',
            'order__employee', 'order__employee__user',
            'assigned_employee', 'assigned_employee__user', 'assigned_provider'
        )

        if order_pk:
            order = get_object_or_404(Order.objects.select_related('customer', 'employee'), pk=order_pk)
            can_view_order = False
            if hasattr(user, 'customer_profile') and order.customer == user.customer_profile:
                can_view_order = True
            elif hasattr(user, 'employee_profile') and user.employee_profile:
                 order_viewer_checker = CanViewAllOrders()
                 if order_viewer_checker.has_permission(self.request, self) or order.employee == user.employee_profile:
                      can_view_order = True

            if not can_view_order:
                 return Deliverable.objects.none()
            return base_qs.filter(order=order)

        else:
            if hasattr(user, 'customer_profile') and user.customer_profile:
                return base_qs.filter(order__customer=user.customer_profile)
            elif hasattr(user, 'employee_profile') and user.employee_profile:
                viewer_checker = CanViewAllDeliverables()
                if viewer_checker.has_permission(request=self.request, view=self):
                    return base_qs.all()
                else:
                    return base_qs.filter(assigned_employee=user.employee_profile)
            else:
                return Deliverable.objects.none()


    def perform_create(self, serializer):
        # ... (lógica sin cambios) ...
        user = self.request.user
        order_pk = self.kwargs.get('order_pk')

        if not order_pk:
            raise ValidationError({"detail": _("La creación de entregables debe hacerse a través de la ruta de un pedido específico (e.g., /api/orders/ID/deliverables/).")})

        order = get_object_or_404(Order, pk=order_pk)
        creator_checker = CanCreateDeliverables()
        if not creator_checker.has_permission(request=self.request, view=self):
             raise PermissionDenied(creator_checker.message)

        # El serializer se encarga de guardar el archivo si se envió
        serializer.save(order=order)