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
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status
logger = logging.getLogger(__name__)
from django.db.models import ( Sum, Count, Q, F, Avg, OuterRef, Subquery,
                               ExpressionWrapper, DurationField, DecimalField, Case, When, Value, CharField)
from django.db.models.functions import TruncMonth, Coalesce, Now
from django.utils import timezone
from datetime import timedelta, datetime
from collections import defaultdict

from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser # Elegir el adecuado
from django.contrib.auth.models import User

# Importa TODOS los modelos necesarios
from .models import (
    Customer, Order, OrderService, Deliverable, Employee, Provider,
    Invoice, Payment, Service # Asegúrate que todos estén importados
)

class DashboardDataView(APIView):
    """
    Proporciona datos agregados para el dashboard principal de la agencia.

    Acepta parámetros opcionales de query:
    - `start_date` (YYYY-MM-DD): Fecha de inicio para datos históricos (default: 6 meses atrás).
    - `end_date` (YYYY-MM-DD): Fecha de fin para datos históricos (default: hoy).
    """
    permission_classes = [IsAuthenticated] # O [IsAdminUser] si es solo para administradores

    def get(self, request, *args, **kwargs):
        # --- Manejo de Fechas ---
        try:
            end_date_str = request.query_params.get('end_date', timezone.now().strftime('%Y-%m-%d'))
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = timezone.now().date()

        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = end_date - timedelta(days=180) # Default histórico
        else:
            start_date = end_date - timedelta(days=180)

        today = timezone.now().date()
        # Fechas para KPIs del "mes anterior completo"
        first_day_current_month = today.replace(day=1)
        last_day_prev_month = first_day_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        kpi_date_range = (first_day_prev_month, last_day_prev_month)

        # --- 1. Customer Demographics (Map Data) ---
        customer_demographics = Customer.objects.filter(
            country__isnull=False, country__ne='' # Excluir nulos y vacíos
        ).values('country').annotate( # Django-countries guarda el código (ej. 'ES')
            count=Count('id')
        ).order_by('-count')
        # Formato: [{'country': 'ES', 'count': 150}, ...]

        # --- 2. Recent Orders ---
        recent_orders_query = Order.objects.select_related(
            'customer__user', 'customer' # Incluir customer completo
        ).order_by('-date_received')[:10] # Limitar a 10 más recientes
        formatted_recent_orders = [
            {
                'id': order.id,
                'customer_name': order.customer.company_name or order.customer.user.get_full_name() or order.customer.user.username,
                'status': order.get_status_display(),
                'date_received': order.date_received,
                'total_amount': order.total_amount, # Usar el campo precalculado
            } for order in recent_orders_query
        ]

        # --- 3. Top Services (Histórico según fechas de request) ---
        top_services_query = OrderService.objects.filter(
            order__date_received__date__range=(start_date, end_date),
            order__status='DELIVERED' # Solo de órdenes completadas
        ).values(
            'service__name',
            'service__is_subscription'
        ).annotate(
            count=Count('id'),
            # Usar el precio registrado en OrderService * cantidad
            revenue=Coalesce(Sum(F('price') * F('quantity')), 0, output_field=DecimalField())
        ).order_by('-count') # Ordenar por número de veces vendido

        top_services_data = list(top_services_query[:10]) # Top 10

        # --- 4. KPI Cards (Previous Complete Month) ---
        # Ingresos reales (pagos completados en el mes anterior)
        payments_last_month = Payment.objects.filter(
            date__date__range=kpi_date_range,
            status='COMPLETED'
        )
        kpi_revenue_last_month = payments_last_month.aggregate(
            total=Coalesce(Sum('amount'), 0, output_field=DecimalField())
        )['total']

        # Órdenes completadas en el mes anterior
        completed_orders_last_month = Order.objects.filter(
            status='DELIVERED',
            completed_at__date__range=kpi_date_range # Fecha de completado en el rango
        ).count()

        # AOV (Valor Medio de Orden) del mes anterior
        kpi_aov = (kpi_revenue_last_month / completed_orders_last_month) if completed_orders_last_month > 0 else 0

        # Suscripciones activas/vendidas en el mes anterior (contando líneas de pedido)
        kpi_subs_last_month = OrderService.objects.filter(
            order__date_received__date__range=kpi_date_range, # O usar completed_at si tiene más sentido
            service__is_subscription=True,
            order__status='DELIVERED' # O un estado 'activo' si aplica
        ).count()

        kpi_total_customers = Customer.objects.count() # Histórico total
        kpi_active_employees = Employee.objects.filter(user__is_active=True).count()

        # Pérdidas: Placeholder. Requiere modelo Expense.
        kpi_profit_loss_last_month = None

        kpis = {
            'revenue_last_month': kpi_revenue_last_month,
            'subscriptions_last_month': kpi_subs_last_month,
            'completed_orders_last_month': completed_orders_last_month,
            'average_order_value_last_month': round(kpi_aov, 2), # Redondear AOV
            'total_customers': kpi_total_customers,
            'active_employees': kpi_active_employees,
            'profit_loss_last_month': kpi_profit_loss_last_month,
        }

        # --- 5. Active Users (Last 15 Minutes) ---
        fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
        # Asegurarse que last_login no sea null
        active_users_count = User.objects.filter(last_login__gte=fifteen_minutes_ago, is_active=True).count()

        # --- 6. Top Customers (Revenue Last 365 days) ---
        one_year_ago = today - timedelta(days=365)
        top_customers_query = Payment.objects.filter(
            status='COMPLETED',
            date__date__range=(one_year_ago, today)
        ).values(
            # Agrupar por ID de cliente para evitar problemas con nombres duplicados
            'invoice__order__customer_id'
        ).annotate(
             # Obtener nombre (priorizar compañía) usando Subquery o Case/When
            customer_name=Subquery(
                Customer.objects.filter(pk=OuterRef('invoice__order__customer_id')).values(
                     name=Case(
                        When(company_name__isnull=False, company_name__ne='', then=F('company_name')),
                        When(user__first_name__isnull=False, user__first_name__ne='', then=F('user__first_name')), # Podría concatenar nombre y apellido
                        default=F('user__username')
                    )
                )[:1]
            ),
            total_revenue=Sum('amount')
        ).order_by('-total_revenue')

        top_customers_data = [
            {'id': item['invoice__order__customer_id'], 'name': item['customer_name'], 'revenue': item['total_revenue']}
            for item in top_customers_query[:5] # Top 5
        ]

        # --- 7. Task (Deliverable) Status Summary ---
        final_task_statuses = Deliverable.FINAL_STATUSES # Usar constante del modelo
        task_summary = Deliverable.objects.aggregate(
            total_active=Count('id', filter=~Q(status__in=final_task_statuses)),
            unassigned=Count('id', filter=Q(assigned_employee__isnull=True) & Q(assigned_provider__isnull=True) & ~Q(status__in=final_task_statuses)),
            pending_approval=Count('id', filter=Q(status__in=['PENDING_APPROVAL', 'PENDING_INTERNAL_APPROVAL'])),
            requires_info=Count('id', filter=Q(status='REQUIRES_INFO')),
            assigned_to_provider=Count('id', filter=Q(assigned_provider__isnull=False) & ~Q(status__in=final_task_statuses)),
            overdue=Count('id', filter=Q(due_date__isnull=False, due_date__lt=today) & ~Q(status__in=final_task_statuses))
        )

        # --- 8. Invoice Status Summary ---
        final_invoice_statuses = Invoice.FINAL_STATUSES # Usar constante
        invoice_summary = Invoice.objects.filter(
           ~Q(status='DRAFT') # Excluir solo borradores
        ).aggregate(
           total_active=Count('id', filter=~Q(status__in=final_invoice_statuses)),
           pending=Count('id', filter=Q(status__in=['SENT', 'PARTIALLY_PAID', 'OVERDUE'])), # Incluir vencidas como pendientes de pago
           paid_count=Count('id', filter=Q(status='PAID')), # Contar pagadas
           overdue_count=Count('id', filter=Q(status='OVERDUE')) # Contar vencidas específicamente
        )

        # --- 9. Average Order Duration (Histórico, últimos 12 meses) ---
        twelve_months_ago = today - timedelta(days=365)
        avg_duration_data = Order.objects.filter(
            status='DELIVERED',
            completed_at__isnull=False,
            date_received__isnull=False,
            completed_at__date__range=(twelve_months_ago, today) # Filtrar por completadas en el último año
        ).aggregate(
            avg_duration=Avg(ExpressionWrapper(F('completed_at') - F('date_received'), output_field=DurationField()))
        )
        # Convertir timedelta a días (o None si no hay datos)
        avg_duration_days = avg_duration_data['avg_duration'].days if avg_duration_data['avg_duration'] else None

        # --- 10. Employee Workload (Tareas activas por empleado activo) ---
        employee_workload_data = list(Employee.objects.filter(
            user__is_active=True
        ).annotate(
            active_tasks=Count('assigned_deliverables', filter=~Q(assigned_deliverables__status__in=final_task_statuses))
        ).values(
            'user__username',
            'user__first_name',
            'user__last_name',
            'active_tasks'
        ).order_by('-active_tasks')) # Lista ordenada por carga

        # --- Construir la Respuesta Final ---
        dashboard_data = {
            'kpis': kpis,
            'customer_demographics': list(customer_demographics),
            'recent_orders': formatted_recent_orders,
            'top_services': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'data': top_services_data
            },
            'active_users_now': active_users_count,
            'top_customers_last_year': top_customers_data,
            'task_summary': task_summary,
            'invoice_summary': invoice_summary,
            'average_order_duration_days': avg_duration_days,
            'employee_workload': employee_workload_data,
        }

        return Response(dashboard_data)





class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed as e:
            # Personalizar respuesta según el código de error
            if e.detail.get("code") == "user_not_found":
                return Response(
                    {"detail": "El usuario no existe"},
                    status=status.HTTP_404_NOT_FOUND
                )
            elif e.detail.get("code") == "invalid_credentials":
                return Response(
                    {"detail": "Contraseña incorrecta"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            elif e.detail.get("code") == "user_inactive":
                return Response(
                    {"detail": "Tu cuenta está inactiva"},
                    status=status.HTTP_403_FORBIDDEN
                )
            raise e  # Para otros errores no manejados
    
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