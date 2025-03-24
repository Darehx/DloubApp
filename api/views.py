from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import *
from .serializers import *
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)




class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        logger.debug("Solicitud POST recibida en CustomTokenObtainPairView")
        return super().post(request, *args, **kwargs)
    
# ---------------------- Servicios de Aplicación ----------------------
class FormResponseService:
    @staticmethod
    def bulk_create_responses(validated_data, customer):
        form = validated_data['form']
        responses = [
            FormResponse(
                customer=customer,
                form=form,
                question=FormQuestion.objects.get(id=item['question']),
                text=item['text']
            ) for item in validated_data['responses']
        ]
        return FormResponse.objects.bulk_create(responses)

# ---------------------- Formularios ----------------------
class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FormResponse.objects.filter(customer=self.request.user.customer_profile)

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'customer_profile'):
            raise serializers.ValidationError("El usuario no tiene un perfil de cliente.")
        serializer.save(customer=self.request.user.customer_profile)

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        serializer = FormResponseBulkCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            customer = self.request.user.customer_profile
            FormResponseService.bulk_create_responses(serializer.validated_data, customer)
            return Response(
                {"message": "Respuestas creadas exitosamente"},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------- Usuarios y Perfiles ----------------------
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user__email', 'preferred_contact_method']

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerCreateSerializer
        return super().get_serializer_class()

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

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        return super().get_serializer_class()
    
class JobPositionViewSet(viewsets.ModelViewSet):
    queryset = JobPosition.objects.all()
    serializer_class = JobPositionSerializer
    permission_classes = [permissions.IsAuthenticated]

# ---------------------- Gestión de Pedidos ----------------------
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Manejo de servicios
        services_data = serializer.validated_data.pop('services', [])
        order = serializer.save()

        for service_data in services_data:
            if 'service' not in service_data or 'quantity' not in service_data or 'price' not in service_data:
                raise serializers.ValidationError("Datos de servicio incompletos.")
            OrderService.objects.create(order=order, **service_data)

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class DeliverableViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        order_id = self.kwargs.get('order_id')
        return Deliverable.objects.filter(order_id=order_id)

    def perform_create(self, serializer):
        order_id = self.kwargs.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError("El pedido especificado no existe.")
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
        if not hasattr(self.request.user, 'customer_profile'):
            raise serializers.ValidationError("El usuario no tiene un perfil de cliente.")
        return Invoice.objects.filter(order__customer=self.request.user.customer_profile)

class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'customer_profile'):
            raise serializers.ValidationError("El usuario no tiene un perfil de cliente.")
        return Payment.objects.filter(invoice__order__customer=self.request.user.customer_profile)
    
class CheckAuthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        data = {
            "isAuthenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.get_full_name(),
                "role": "customer" if hasattr(user, 'customer_profile') else "employee"
            }
        }
        return Response(data)