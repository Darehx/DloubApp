# api/views/customers.py
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import Customer
from ..permissions import IsCustomerOwnerOrAdminOrSupport

# --- Importaciones de Serializers Corregidas ---
from ..serializers.customers import CustomerSerializer, CustomerCreateSerializer
# ----------------------------------------------

User = get_user_model()

class CustomerViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Clientes (Customers).
    """
    queryset = Customer.objects.select_related(
        'user',
        'user__profile__primary_role'
    ).all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user__email', 'preferred_contact_method', 'country', 'company_name']

    def get_serializer_class(self):
        """ Devuelve el serializer apropiado según la acción. """
        # Usa los serializers importados correctamente
        if self.action == 'create':
            return CustomerCreateSerializer
        return CustomerSerializer

    def get_permissions(self):
        """ Define los permisos según la acción. """
        if self.action == 'create':
            self.permission_classes = [permissions.AllowAny]
        elif self.action == 'list':
            self.permission_classes = [permissions.IsAuthenticated] # Ajusta si es necesario
        else:
            self.permission_classes = [IsCustomerOwnerOrAdminOrSupport]
        return super().get_permissions()

    # perform_create ahora puede devolver la instancia creada,
    # y DRF usará el serializer definido en get_serializer_class para la respuesta.
    def perform_create(self, serializer):
        # La lógica de creación está en CustomerCreateSerializer.create
        # Solo necesitamos guardar y DRF se encarga del resto.
        serializer.save() # Devuelve la instancia creada

