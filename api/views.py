from rest_framework import viewsets, generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import *
from .serializers import *
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models

# ---------------------- Servicios de Aplicación ----------------------

class FormResponseService:
    @staticmethod
    def bulk_create_responses(validated_data, customer):
        respuestas = [
            FormResponse(**item, customer=customer) for item in validated_data
        ]
        return FormResponse.objects.bulk_create(respuestas)


# ---------------------- Formularios ----------------------

class FormResponseBulkCreateSerializer(serializers.ListSerializer):
    child = FormResponseSerializer()  # Serializador base para cada ítem

    def create(self, validated_data):
        customer = self.context['customer']
        return FormResponseService.bulk_create_responses(validated_data, customer)


class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FormResponse.objects.filter(customer=self.request.user.customer_profile)

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user.customer_profile)

@action(detail=False, methods=['post'])
def bulk_create(self, request):
    """
    Creación masiva de respuestas:
    """
    serializer = FormResponseBulkCreateSerializer(
        data=request.data,
        context={'customer': request.user.customer_profile}
    )
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": f"{len(serializer.validated_data)} respuestas creadas exitosamente."},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------- Autenticación ----------------------

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ---------------------- Usuarios y Perfiles ----------------------

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user__email', 'preferred_contact_method']

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerCreateSerializer
        return CustomerSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['position', 'active']


# ---------------------- Gestión de Pedidos ----------------------

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()  # Añade esta línea
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'customer', 'priority']

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'employee_profile'):
            return Order.objects.all().select_related('customer')
        return Order.objects.filter(customer=user.customer_profile).select_related('customer')

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'employee_profile'):
            serializer.save(employee=self.request.user.employee_profile)
        else:
            serializer.save(customer=self.request.user.customer_profile)


class DeliverableViewSet(viewsets.ModelViewSet):
    queryset = Deliverable.objects.all()  # Asegúrate de que haya un queryset
    serializer_class = DeliverableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return Deliverable.objects.filter(order_id=order_id)

    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        order = Order.objects.get(id=order_id)
        serializer.save(order=order)


# ---------------------- Servicios y Catálogo ----------------------

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['code', 'ventulab', 'campaign']


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['start_date', 'end_date']


# ---------------------- Gestión de Pagos ----------------------

class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Invoice.objects.filter(order__customer=self.request.user.customer_profile)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(invoice__order__customer=self.request.user.customer_profile)
