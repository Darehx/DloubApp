# api/views.py

from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import (
    IsAuthenticated, IsAdminUser, AllowAny, IsAuthenticatedOrReadOnly, BasePermission
)
from rest_framework.exceptions import AuthenticationFailed, ValidationError, PermissionDenied # Importar PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import ( Sum, Count, Q, F, Avg, OuterRef, Subquery,
                               ExpressionWrapper, DurationField, DecimalField, Case, When, Value, CharField)
from django.db.models.functions import TruncMonth, Coalesce, Now
from django.utils import timezone
from datetime import timedelta, datetime
from collections import defaultdict
import logging


# Importar TODOS los modelos necesarios
from .models import (
    Customer, Order, OrderService, Deliverable, Employee, Provider,
    Invoice, Payment, Service, JobPosition, Form, FormQuestion,
    FormResponse, Campaign, CampaignService, TransactionType, PaymentMethod,
    Notification, AuditLog, ServiceCategory, ServiceFeature, Price
)

# Importar TODOS los serializers necesarios
from .serializers import (
    CustomTokenObtainPairSerializer,
    BasicUserSerializer,
    FormSerializer, FormQuestionSerializer, FormResponseSerializer, FormResponseBulkCreateSerializer,
    CustomerSerializer, CustomerCreateSerializer,
    JobPositionSerializer,
    EmployeeSerializer, EmployeeCreateSerializer,
    OrderReadSerializer, OrderCreateUpdateSerializer, # Usar Read/CreateUpdate
    DeliverableSerializer,
    ServiceCategorySerializer, ServiceSerializer, PriceSerializer, ServiceFeatureSerializer,
    CampaignSerializer, CampaignServiceSerializer,
    TransactionTypeSerializer, PaymentMethodSerializer,
    InvoiceSerializer, InvoiceBasicSerializer,
    PaymentReadSerializer, PaymentCreateSerializer, # Usar Read/Create
    ProviderSerializer,
    NotificationSerializer,
    AuditLogSerializer,
)

# --- Servicio de Aplicación (si lo usas para lógica extra) ---
# (Mantenido como lo tenías, asumiendo que funciona)
class FormResponseService:
    @staticmethod
    def bulk_create_responses(validated_data, customer):
        form = validated_data['form']
        responses_to_create = []
        for item in validated_data['responses']:
            question = item['question']
            responses_to_create.append(
                FormResponse(
                    customer=customer, form=form, question=question, text=item['text']
                )
            )
        if responses_to_create:
             return FormResponse.objects.bulk_create(responses_to_create)
        return []

logger = logging.getLogger(__name__)
User = get_user_model()

# ==============================================================================
# ------------------------- VISTAS DE LA API -----------------------------------
# ==============================================================================

# ---------------------- Permisos Personalizados (Opcional) -------------------
class IsOwnerOrAdmin(BasePermission):
    """Permiso para permitir acceso solo al dueño del objeto o a un admin."""
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura pueden ser más abiertos si se desea
        if request.method in permissions.SAFE_METHODS:
            # Podría permitir lectura a admins siempre, y al dueño
            return request.user.is_staff or obj == request.user

        # Permisos de escritura solo para el dueño o admin
        return request.user.is_staff or obj == request.user

# ---------------------- Autenticación y Verificación ----------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CheckAuthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = 'employee' if hasattr(user, 'employee_profile') else 'customer'
        user_data = BasicUserSerializer(user).data
        user_data['role'] = role
        data = {"isAuthenticated": True, "user": user_data}
        return Response(data)

# ---------------------- Vista del Dashboard ----------------------
class DashboardDataView(APIView):
    """
    Proporciona datos agregados para el dashboard principal de la agencia.
    Acepta parámetros opcionales de query: start_date, end_date (YYYY-MM-DD).
    """
    permission_classes = [IsAuthenticated] # O [IsAdminUser]

    def get(self, request, *args, **kwargs):
        # --- Manejo de Fechas ---
        try:
            end_date_str = request.query_params.get('end_date', timezone.now().strftime('%Y-%m-%d'))
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError: end_date = timezone.now().date()
        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError: start_date = end_date - timedelta(days=180)
        else: start_date = end_date - timedelta(days=180)
        today = timezone.now().date()
        first_day_current_month = today.replace(day=1)
        last_day_prev_month = first_day_current_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        kpi_date_range = (first_day_prev_month, last_day_prev_month)
        one_year_ago = today - timedelta(days=365)
        twelve_months_ago = today - timedelta(days=365) # Usado para duración
        fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
        final_task_statuses = Deliverable.FINAL_STATUSES
        final_invoice_statuses = Invoice.FINAL_STATUSES


        # --- Queries Optimizadas ---
        customer_demographics = Customer.objects.filter(
            country__isnull=False, country__ne=''
        ).values('country').annotate(count=Count('id')).order_by('-count')

        recent_orders_query = Order.objects.select_related(
            'customer__user', 'customer'
        ).order_by('-date_received')[:10]

        top_services_query = OrderService.objects.filter(
            order__date_received__date__range=(start_date, end_date),
            order__status='DELIVERED'
        ).values(
            'service__name', 'service__is_subscription'
        ).annotate(
            count=Count('id'),
            revenue=Coalesce(Sum(F('price') * F('quantity')), 0, output_field=DecimalField())
        ).order_by('-count')[:10]

        payments_last_month = Payment.objects.filter(
            date__date__range=kpi_date_range, status='COMPLETED'
        )
        kpi_revenue_last_month = payments_last_month.aggregate(
            total=Coalesce(Sum('amount'), 0, output_field=DecimalField())
        )['total']

        completed_orders_last_month_count = Order.objects.filter(
            status='DELIVERED', completed_at__date__range=kpi_date_range
        ).count()

        kpi_aov = (kpi_revenue_last_month / completed_orders_last_month_count) if completed_orders_last_month_count > 0 else 0

        kpi_subs_last_month_count = OrderService.objects.filter(
            order__date_received__date__range=kpi_date_range,
            service__is_subscription=True, order__status='DELIVERED'
        ).count()

        kpi_total_customers_count = Customer.objects.count()
        kpi_active_employees_count = Employee.objects.filter(user__is_active=True).count()

        active_users_count = User.objects.filter(last_login__gte=fifteen_minutes_ago, is_active=True).count()

        top_customers_query = Payment.objects.filter(
            status='COMPLETED', date__date__range=(one_year_ago, today)
        ).values('invoice__order__customer_id').annotate(
            customer_name=Subquery(
                Customer.objects.filter(pk=OuterRef('invoice__order__customer_id')).values(
                    name=Case(
                        When(company_name__isnull=False, company_name__ne='', then=F('company_name')),
                        When(user__first_name__isnull=False, user__first_name__ne='', then=F('user__first_name')),
                        default=F('user__username')
                    )
                )[:1]
            ),
            total_revenue=Sum('amount')
        ).order_by('-total_revenue')[:5]

        task_summary = Deliverable.objects.aggregate(
            total_active=Count('id', filter=~Q(status__in=final_task_statuses)),
            unassigned=Count('id', filter=Q(assigned_employee__isnull=True) & Q(assigned_provider__isnull=True) & ~Q(status__in=final_task_statuses)),
            pending_approval=Count('id', filter=Q(status__in=['PENDING_APPROVAL', 'PENDING_INTERNAL_APPROVAL'])),
            requires_info=Count('id', filter=Q(status='REQUIRES_INFO')),
            assigned_to_provider=Count('id', filter=Q(assigned_provider__isnull=False) & ~Q(status__in=final_task_statuses)),
            overdue=Count('id', filter=Q(due_date__isnull=False, due_date__lt=today) & ~Q(status__in=final_task_statuses))
        )

        invoice_summary = Invoice.objects.filter(~Q(status='DRAFT')).aggregate(
           total_active=Count('id', filter=~Q(status__in=final_invoice_statuses)),
           pending=Count('id', filter=Q(status__in=['SENT', 'PARTIALLY_PAID', 'OVERDUE'])),
           paid_count=Count('id', filter=Q(status='PAID')),
           overdue_count=Count('id', filter=Q(status='OVERDUE'))
        )

        avg_duration_data = Order.objects.filter(
            status='DELIVERED', completed_at__isnull=False, date_received__isnull=False,
            completed_at__date__range=(twelve_months_ago, today)
        ).aggregate(
            avg_duration=Avg(ExpressionWrapper(F('completed_at') - F('date_received'), output_field=DurationField()))
        )
        avg_duration_days = avg_duration_data['avg_duration'].days if avg_duration_data['avg_duration'] else None

        employee_workload_query = Employee.objects.filter(
            user__is_active=True
        ).annotate(
            active_tasks=Count('assigned_deliverables', filter=~Q(assigned_deliverables__status__in=final_task_statuses))
        ).values(
            'user__username', 'user__first_name', 'user__last_name', 'active_tasks'
        ).order_by('-active_tasks')

        # --- Formateo y Construcción de Respuesta ---
        formatted_recent_orders = [
            {'id': o.id, 'customer_name': o.customer.company_name or o.customer.user.get_full_name() or o.customer.user.username, 'status': o.get_status_display(), 'date_received': o.date_received, 'total_amount': o.total_amount}
            for o in recent_orders_query
        ]
        top_services_data = list(top_services_query)
        top_customers_data = list(top_customers_query)
        employee_workload_data = list(employee_workload_query)

        dashboard_data = {
            'kpis': {
                'revenue_last_month': kpi_revenue_last_month,
                'subscriptions_last_month': kpi_subs_last_month_count,
                'completed_orders_last_month': completed_orders_last_month_count,
                'average_order_value_last_month': round(kpi_aov, 2),
                'total_customers': kpi_total_customers_count,
                'active_employees': kpi_active_employees_count,
                'profit_loss_last_month': None, # Placeholder
            },
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


# ---------------------- ViewSets CRUD ----------------------

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user__email', 'preferred_contact_method', 'country']

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomerCreateSerializer
        # Permitir actualización con el mismo serializer o uno específico si es necesario
        elif self.action in ['update', 'partial_update']:
             # Podrías necesitar un CustomerUpdateSerializer si los campos editables difieren mucho
             return CustomerSerializer # Ojo: User no será editable aquí
        return CustomerSerializer # Lectura

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [AllowAny]
        elif self.action in ['retrieve', 'update', 'partial_update']:
             # Permitir al usuario ver/editar su propio perfil, o admin ver/editar cualquiera
             # Necesitaríamos un permiso personalizado como IsOwnerOrAdmin aplicado al objeto user
             self.permission_classes = [IsAuthenticated] # Simplificado por ahora
        elif self.action == 'list' or self.action == 'destroy':
             self.permission_classes = [IsAdminUser]
        else:
             self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('user', 'position').filter(user__is_active=True)
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['position__name', 'user__username'] # Filtrar por nombre de puesto

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        return EmployeeSerializer

class JobPositionViewSet(viewsets.ModelViewSet):
    queryset = JobPosition.objects.all()
    serializer_class = JobPositionSerializer
    permission_classes = [IsAdminUser]

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('customer__user', 'employee__user').prefetch_related('services__service', 'deliverables').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'customer__user__username', 'priority', 'employee__user__username', 'date_received', 'date_required']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return OrderReadSerializer
        return OrderCreateUpdateSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = super().get_queryset() # Usa el queryset optimizado
        if hasattr(user, 'employee_profile'):
            return base_qs # Empleado ve todas
        elif hasattr(user, 'customer_profile'):
            return base_qs.filter(customer=user.customer_profile) # Cliente ve las suyas
        return Order.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        customer = serializer.validated_data.get('customer') # Cliente debe venir en los datos

        # Asignar empleado creador si no se especifica otro y es un empleado quien crea
        if hasattr(user, 'employee_profile') and not serializer.validated_data.get('employee'):
            serializer.save(employee=user.employee_profile)
        # Si es cliente, asegurarse que se asigna a sí mismo (ya filtrado en serializer si es necesario)
        elif hasattr(user, 'customer_profile'):
             if customer != user.customer_profile:
                  raise PermissionDenied("No puedes crear pedidos para otros clientes.")
             # El serializer ya asigna el customer si es write_only=False o se valida
             serializer.save() # Asumiendo que customer está en validated_data
        else: # Si no tiene perfil (raro si está autenticado)
            raise PermissionDenied("Perfil de usuario no válido para crear pedidos.")


class DeliverableViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverableSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'assigned_employee', 'assigned_provider', 'due_date']

    def get_queryset(self):
        """Obtiene entregables para una orden específica o todos si es admin."""
        user = self.request.user
        order_pk = self.kwargs.get('order_pk') # Desde URL anidada

        if order_pk:
            base_qs = Deliverable.objects.filter(order__pk=order_pk)
            # Verificar acceso a la orden
            try:
                order = Order.objects.get(pk=order_pk)
                can_access = False
                if hasattr(user, 'employee_profile'): can_access = True
                elif hasattr(user, 'customer_profile') and order.customer == user.customer_profile: can_access = True
                if not can_access: return Deliverable.objects.none()
            except Order.DoesNotExist: return Deliverable.objects.none()
        else: # Si se accede a /api/deliverables/ directamente (requiere permisos de admin?)
            if not user.is_staff: return Deliverable.objects.none() # Solo admin puede ver todos
            base_qs = Deliverable.objects.all()

        return base_qs.select_related('assigned_employee__user', 'assigned_provider', 'order')


    def perform_create(self, serializer):
        order_pk = self.kwargs.get('order_pk')
        if not order_pk:
            raise ValidationError("La creación de entregables debe hacerse bajo una orden específica (ej. /api/orders/X/deliverables/).")
        try:
            order = Order.objects.get(id=order_pk)
            user = self.request.user
            # Permitir crear solo a empleados (o admin)
            if not hasattr(user, 'employee_profile'):
                 raise PermissionDenied("Solo los empleados pueden añadir entregables.")
        except Order.DoesNotExist:
            raise ValidationError({"order": "El pedido especificado no existe."})
        serializer.save(order=order)


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [AllowAny] # Las categorías suelen ser públicas

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related('category', 'campaign').prefetch_related('features', 'price_history').all()
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly] # Lectura pública, escritura autenticada
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'is_active', 'is_package', 'is_subscription', 'ventulab']

    def get_permissions(self):
        # Solo admins pueden crear/editar/borrar servicios
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        return super().get_permissions()

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.prefetch_related('included_services__service').all() # Optimizar
    serializer_class = CampaignSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'start_date', 'end_date']

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('order__customer__user').prefetch_related('payments__method').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'order__customer__user__username', 'date', 'due_date', 'invoice_number']

    def get_serializer_class(self):
         if self.action == 'list':
             return InvoiceBasicSerializer
         return InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = super().get_queryset()
        if hasattr(user, 'employee_profile'):
            return base_qs
        elif hasattr(user, 'customer_profile'):
            return base_qs.filter(order__customer=user.customer_profile)
        return Invoice.objects.none()

    # perform_create: Normalmente lo hace un empleado. Necesita validar permiso sobre la orden.
    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'employee_profile'):
            raise PermissionDenied("Solo los empleados pueden crear facturas.")
        # Podrías añadir validación extra: ¿Tiene este empleado permiso sobre la orden asociada?
        serializer.save()

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('invoice__order__customer__user', 'method', 'transaction_type').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'method', 'transaction_type', 'currency', 'invoice__invoice_number', 'date']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return PaymentReadSerializer
        return PaymentCreateSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = super().get_queryset()
        if hasattr(user, 'employee_profile'):
            return base_qs
        elif hasattr(user, 'customer_profile'):
            # ¿Debería el cliente ver los pagos? Quizás solo los de sus facturas.
            return base_qs.filter(invoice__order__customer=user.customer_profile)
        return Payment.objects.none()

    # perform_create: Normalmente lo hace un empleado/admin.
    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'employee_profile'):
            raise PermissionDenied("Solo los empleados pueden registrar pagos.")
        # Validar si el empleado tiene permiso sobre la factura?
        serializer.save()


class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['form', 'question', 'customer__user__username']

    def get_queryset(self):
        user = self.request.user
        base_qs = FormResponse.objects.select_related('customer__user', 'form', 'question')
        if hasattr(user, 'employee_profile'):
             return base_qs.all() # Empleado ve todas?
        elif hasattr(user, 'customer_profile'):
             return base_qs.filter(customer=user.customer_profile)
        return FormResponse.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'customer_profile'):
             serializer.save(customer=user.customer_profile)
        else:
             # Permitir a empleado crear si pasa 'customer' ID? Necesitaría cambiar serializer
             raise PermissionDenied("Solo los clientes pueden crear respuestas directamente.")


    @action(detail=False, methods=['post'], serializer_class=FormResponseBulkCreateSerializer)
    def bulk_create(self, request):
        user = request.user
        if not hasattr(user, 'customer_profile'):
            return Response({"detail": "Solo los clientes pueden usar la creación masiva."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            # Llamar al servicio de aplicación
            FormResponseService.bulk_create_responses(serializer.validated_data, user.customer_profile)
            return Response({"message": "Respuestas creadas exitosamente"}, status=status.HTTP_201_CREATED)
        except Exception as e:
             logger.error(f"Error en bulk_create FormResponse por {user.username}: {e}", exc_info=True)
             return Response({"detail": "Ocurrió un error procesando las respuestas."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    # Marcar como leída individualmente
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_as_read(self, request, pk=None):
        notification = self.get_object() # get_object ya filtra por usuario via get_queryset
        if not notification.read:
            notification.read = True
            notification.save(update_fields=['read'])
        serializer = self.get_serializer(notification) # Devolver la notificación actualizada
        return Response(serializer.data)

    # Marcar todas como leídas
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_as_read(self, request):
        updated_count = self.get_queryset().filter(read=False).update(read=True)
        return Response({'status': f'{updated_count} notificaciones marcadas como leídas'})

    # Permitir borrar notificaciones?
    def perform_destroy(self, instance):
        # get_object ya asegura que es del usuario actual
        instance.delete()


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser] # Solo Admins
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'user__username': ['exact', 'icontains'],
        'action': ['icontains'],
        'timestamp': ['date', 'date__gte', 'date__lte', 'year', 'month'],
        # Podrías añadir filtro por tipo de objeto si guardas ContentType
    }