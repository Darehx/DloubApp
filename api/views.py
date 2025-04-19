# api/views.py
from decimal import Decimal
from rest_framework import viewsets, generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.permissions import (
    IsAuthenticated, IsAdminUser, AllowAny, IsAuthenticatedOrReadOnly, BasePermission
)
from rest_framework.exceptions import AuthenticationFailed, ValidationError, PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView

# --- IMPORTACIÓN PARA TRADUCCIÓN ---
from django.utils.translation import gettext_lazy as _
# --- FIN IMPORTACIÓN ---

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import ( Sum, Count, Q, F, Avg, OuterRef, Subquery,
                               ExpressionWrapper, DurationField, DecimalField, Case, When, Value, CharField)
from django.db.models.functions import TruncMonth, Coalesce, Now
from django.utils import timezone
from datetime import timedelta, datetime
from collections import defaultdict
import logging

# Importar TODOS los modelos necesarios, incluyendo los nuevos
from .models import (
    Customer, Order, OrderService, Deliverable, Employee, Provider,
    Invoice, Payment, Service, JobPosition, Form, FormQuestion,
    FormResponse, Campaign, CampaignService, TransactionType, PaymentMethod,
    Notification, AuditLog, ServiceCategory, ServiceFeature, Price,
    # --- NUEVOS MODELOS ---
    UserRole, UserProfile, UserRoleAssignment
)
# Importar constantes de roles
try:
    from .roles import Roles
except ImportError:
    class Roles: # Placeholder
        DRAGON = 'dragon'
        ADMIN = 'admin'
        MARKETING = 'mktg'
        FINANCE = 'fin'
        SALES = 'sales'
        DEVELOPMENT = 'dev'
        SUPPORT = 'support'
    print("ADVERTENCIA: api/roles.py no encontrado.")


# Importar TODOS los serializers necesarios, incluyendo los nuevos/actualizados
from .serializers import (
    CustomTokenObtainPairSerializer, BasicUserSerializer,
    FormSerializer, FormQuestionSerializer, FormResponseSerializer, FormResponseBulkCreateSerializer,
    CustomerSerializer, CustomerCreateSerializer, JobPositionSerializer,
    EmployeeSerializer, EmployeeCreateSerializer, OrderReadSerializer, OrderCreateUpdateSerializer,
    DeliverableSerializer, ServiceCategorySerializer, ServiceSerializer, PriceSerializer, ServiceFeatureSerializer,
    CampaignSerializer, CampaignServiceSerializer, TransactionTypeSerializer, PaymentMethodSerializer,
    InvoiceSerializer, InvoiceBasicSerializer, PaymentReadSerializer, PaymentCreateSerializer,
    ProviderSerializer, NotificationSerializer, AuditLogSerializer
    # UserRoleSerializer, UserRoleAssignmentSerializer # Si los creaste
)

# --- Servicio de Aplicación ---
class FormResponseService:
    @staticmethod
    def bulk_create_responses(validated_data, customer):
        form = validated_data['form']; responses_to_create = [];
        for item in validated_data['responses']: question = item['question']; responses_to_create.append(FormResponse(customer=customer, form=form, question=question, text=item['text']));
        if responses_to_create: return FormResponse.objects.bulk_create(responses_to_create); return []

logger = logging.getLogger(__name__)
User = get_user_model()

# ==============================================================================
# ------------------------- VISTAS DE LA API (CORREGIDAS) --------------------
# ==============================================================================

# --- VISTA USER ME ---
class UserMeView(APIView):
    """Devuelve la información del usuario autenticado con sus roles."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = BasicUserSerializer(user, context={'request': request}) # Ya incluye roles
        return Response(serializer.data)

# ---------------------- Permisos Personalizados -------------------
class IsOwnerOrAdmin(BasePermission):
    """Permiso para permitir acceso solo al dueño del objeto o a un admin/staff."""
    def has_object_permission(self, request, view, obj):
        # El objeto `obj` aquí generalmente es la instancia del modelo (ej. Customer, Order)
        # Necesitamos acceder al usuario relacionado con ese objeto si es posible
        owner = None
        if hasattr(obj, 'user'):
            owner = obj.user # Caso de Customer, Employee, Notification, etc.
        elif hasattr(obj, 'customer') and hasattr(obj.customer, 'user'):
            owner = obj.customer.user # Caso de Order, Invoice, FormResponse
        # Añadir más casos según sea necesario

        if request.method in permissions.SAFE_METHODS:
             # Permitir lectura a admins y al dueño
             return request.user.is_staff or (owner and owner == request.user)
        # Permitir escritura solo a admins y al dueño
        return request.user.is_staff or (owner and owner == request.user)


class HasRolePermission(BasePermission):
    """Permiso que verifica si el usuario tiene al menos uno de los roles requeridos."""
    def __init__(self, required_roles=None):
        if required_roles is None: self.required_roles = []
        elif isinstance(required_roles, str): self.required_roles = [required_roles]
        else: self.required_roles = list(required_roles)
        super().__init__()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        # Verifica si es staff (acceso general) O tiene uno de los roles específicos
        # AJUSTA ESTA LÓGICA: ¿Debería staff tener acceso implícito o basarse SOLO en roles?
        # Opción 1: Staff O rol específico
        # return request.user.is_staff or any(request.user.has_role(role) for role in self.required_roles)
        # Opción 2: SOLO rol específico (más granular)
        return any(request.user.has_role(role) for role in self.required_roles)


# ---------------------- Autenticación y Verificación ----------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CheckAuthView(APIView):
    """Verifica si el usuario está autenticado y devuelve sus datos (incluyendo roles)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = BasicUserSerializer(user, context={'request': request}) # Ya incluye roles
        data = {"isAuthenticated": True, "user": serializer.data}
        return Response(data)

# ---------------------- Dashboard ------------------------------------------
class DashboardDataView(APIView):
    """Proporciona datos agregados para el dashboard."""
    # Definir qué roles pueden acceder al dashboard
    permission_classes = [HasRolePermission([
        Roles.ADMIN, Roles.DRAGON, Roles.FINANCE, Roles.MARKETING, Roles.SALES, Roles.OPERATIONS # Ejemplo
    ])]

    def get(self, request, *args, **kwargs):
        logger.info(f"[DashboardView] Iniciando GET para usuario {request.user.username} (Roles: {request.user.get_all_active_role_names})")
        try:
            # --- Lógica de cálculo de fechas y KPIs (Mantenida) ---
            end_date_str = request.query_params.get('end_date', timezone.now().strftime('%Y-%m-%d'))
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            start_date_str = request.query_params.get('start_date')
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else end_date - timedelta(days=180)
            today = timezone.now().date()
            first_day_current_month = today.replace(day=1)
            last_day_prev_month = first_day_current_month - timedelta(days=1)
            first_day_prev_month = last_day_prev_month.replace(day=1)
            kpi_date_range = (first_day_prev_month, last_day_prev_month)
            one_year_ago = today - timedelta(days=365)
            fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
            final_task_statuses = Deliverable.FINAL_STATUSES
            final_invoice_statuses = Invoice.FINAL_STATUSES

            # --- Queries Optimizadas (Mantenidas) ---
            customer_demographics_data = list(Customer.objects.filter(country__isnull=False).exclude(country='').values('country').annotate(count=Count('id')).order_by('-count'))
            recent_orders_query = Order.objects.select_related('customer__user', 'customer').order_by('-date_received')[:10]
            top_services_data = list(OrderService.objects.filter(order__date_received__date__range=(start_date, end_date),order__status='DELIVERED').values('service__name', 'service__is_subscription').annotate(count=Count('id'),revenue=Coalesce(Sum(F('price') * F('quantity')), Decimal('0.00'), output_field=DecimalField())).order_by('-count')[:10])
            payments_last_month = Payment.objects.filter(date__date__range=kpi_date_range, status='COMPLETED')
            kpi_revenue_last_month = payments_last_month.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00'), output_field=DecimalField()))['total']
            completed_orders_last_month_count = Order.objects.filter(status='DELIVERED', completed_at__date__range=kpi_date_range).count()
            kpi_aov = (kpi_revenue_last_month / completed_orders_last_month_count) if completed_orders_last_month_count > 0 else Decimal('0.00')
            kpi_subs_last_month_count = OrderService.objects.filter(order__date_received__date__range=kpi_date_range, service__is_subscription=True, order__status='DELIVERED').count() # Revisar lógica de status para subs
            kpi_total_customers_count = Customer.objects.count()
            kpi_active_employees_count = Employee.objects.filter(user__is_active=True).count()
            active_users_count = User.objects.filter(last_login__gte=fifteen_minutes_ago, is_active=True).count()
            top_customers_data = list(Payment.objects.filter(status='COMPLETED', date__date__range=(one_year_ago, today)).values('invoice__order__customer_id').annotate(customer_name=Subquery(Customer.objects.filter(pk=OuterRef('invoice__order__customer_id')).values(name=Coalesce(F('company_name'),F('user__first_name'),F('user__username'),output_field=CharField()))[:1]),total_revenue=Sum('amount')).order_by('-total_revenue')[:5])
            task_summary = Deliverable.objects.aggregate(total_active=Count('id', filter=~Q(status__in=final_task_statuses)),unassigned=Count('id', filter=Q(assigned_employee__isnull=True) & Q(assigned_provider__isnull=True) & ~Q(status__in=final_task_statuses)),pending_approval=Count('id', filter=Q(status__in=['PENDING_APPROVAL', 'PENDING_INTERNAL_APPROVAL'])),requires_info=Count('id', filter=Q(status='REQUIRES_INFO')),assigned_to_provider=Count('id', filter=Q(assigned_provider__isnull=False) & ~Q(status__in=final_task_statuses)),overdue=Count('id', filter=Q(due_date__isnull=False, due_date__lt=today) & ~Q(status__in=final_task_statuses)))
            invoice_summary = Invoice.objects.filter(~Q(status='DRAFT')).aggregate(total_active=Count('id', filter=~Q(status__in=final_invoice_statuses)),pending=Count('id', filter=Q(status__in=['SENT', 'PARTIALLY_PAID', 'OVERDUE'])),paid_count=Count('id', filter=Q(status='PAID')),overdue_count=Count('id', filter=Q(status='OVERDUE')))
            avg_duration_data = Order.objects.filter(status='DELIVERED',completed_at__isnull=False,date_received__isnull=False, completed_at__gte=F('date_received'),completed_at__date__range=(one_year_ago, today)).aggregate(avg_duration=Avg(ExpressionWrapper(F('completed_at') - F('date_received'), output_field=DurationField())))
            avg_duration_days = avg_duration_data['avg_duration'].days if avg_duration_data['avg_duration'] else None
            employee_workload_data = list(Employee.objects.filter(user__is_active=True).annotate(active_tasks=Count('assigned_deliverables', filter=~Q(assigned_deliverables__status__in=final_task_statuses))).values('user__username', 'user__first_name', 'user__last_name', 'active_tasks').order_by('-active_tasks'))

            # --- Formateo de respuesta (Mantenido) ---
            def get_customer_display_name(order): name_parts = [order.customer.company_name if order.customer else None, order.customer.user.get_full_name() if order.customer and order.customer.user else None, order.customer.user.username if order.customer and order.customer.user else None]; return next((name for name in name_parts if name), _("Cliente Desconocido")) if order.customer else _("Cliente Desconocido")
            formatted_recent_orders = [{'id': o.id,'customer_name': get_customer_display_name(o),'status': o.get_status_display(),'date_received': o.date_received.isoformat() if o.date_received else None,'total_amount': o.total_amount} for o in recent_orders_query]
            dashboard_data = {'kpis': {'revenue_last_month': kpi_revenue_last_month,'subscriptions_last_month': kpi_subs_last_month_count,'completed_orders_last_month': completed_orders_last_month_count,'average_order_value_last_month': round(kpi_aov, 2) if kpi_aov else 0.00,'total_customers': kpi_total_customers_count,'active_employees': kpi_active_employees_count,'profit_loss_last_month': None,},'customer_demographics': customer_demographics_data,'recent_orders': formatted_recent_orders,'top_services': {'start_date': start_date.strftime('%Y-%m-%d'),'end_date': end_date.strftime('%Y-%m-%d'),'data': top_services_data },'active_users_now': active_users_count,'top_customers_last_year': top_customers_data,'task_summary': task_summary,'invoice_summary': invoice_summary,'average_order_duration_days': avg_duration_days,'employee_workload': employee_workload_data,}
            logger.info(f"[DashboardView] Datos generados exitosamente para {request.user.username}.")
            return Response(dashboard_data)
        except Exception as e:
             logger.error(f"[DashboardView] Error 500 inesperado para usuario {request.user.username}: {e}", exc_info=True)
             return Response({"detail": _("Ocurrió un error interno procesando los datos del dashboard.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------- ViewSets CRUD (PERMISOS ACTUALIZADOS) ----------------------

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('user__profile__primary_role').all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user__email', 'preferred_contact_method', 'country']

    def get_serializer_class(self):
        if self.action == 'create': return CustomerCreateSerializer
        return CustomerSerializer

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = [AllowAny] # Crear cliente es público
        elif self.action == 'retrieve':
             # Ver detalle: Autenticado Y (es dueño O tiene rol de soporte/admin)
             self.permission_classes = [IsAuthenticated] # Pendiente: IsOwnerOrAdminOrRole([Roles.SUPPORT, Roles.ADMIN])
        elif self.action in ['update', 'partial_update']:
             # Editar: Autenticado Y (es dueño O tiene rol admin)
             self.permission_classes = [IsAuthenticated] # Pendiente: IsOwnerOrAdminOrRole([Roles.ADMIN])
        elif self.action == 'list':
             # Listar: Solo roles específicos
             self.permission_classes = [HasRolePermission([Roles.ADMIN, Roles.SALES, Roles.SUPPORT, Roles.DRAGON])]
        elif self.action == 'destroy':
             # Borrar: Solo roles muy altos
             self.permission_classes = [HasRolePermission([Roles.ADMIN, Roles.DRAGON])]
        else:
             self.permission_classes = [IsAuthenticated] # Default seguro
        return super().get_permissions()


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('user__profile__primary_role', 'position').prefetch_related('user__secondary_role_assignments__role').filter(user__is_active=True)
    permission_classes = [HasRolePermission([Roles.ADMIN, Roles.DRAGON])] # Solo Admin/Dragon gestionan empleados
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['position__name', 'user__username', 'user__profile__primary_role__name'] # Filtrar por rol primario

    def get_serializer_class(self):
        if self.action == 'create': return EmployeeCreateSerializer
        return EmployeeSerializer


class JobPositionViewSet(viewsets.ModelViewSet):
    queryset = JobPosition.objects.all()
    serializer_class = JobPositionSerializer
    permission_classes = [HasRolePermission([Roles.ADMIN, Roles.DRAGON])] # Solo Admin/Dragon gestionan puestos


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('customer__user', 'employee__user').prefetch_related('services__service', 'deliverables') # Quitar roles aquí, filtrar en get_queryset
    permission_classes = [IsAuthenticated] # Base: debe estar autenticado
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'customer__user__username', 'priority', 'employee__user__username', 'date_received', 'date_required']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']: return OrderReadSerializer
        return OrderCreateUpdateSerializer

    def get_queryset(self):
        user = self.request.user
        # Optimizar consulta base incluyendo roles necesarios para filtrar
        base_qs = Order.objects.select_related(
            'customer__user__profile__primary_role',
            'employee__user__profile__primary_role'
        ).prefetch_related('services__service', 'deliverables')

        if hasattr(user, 'customer_profile'):
            return base_qs.filter(customer=user.customer_profile) # Cliente ve las suyas
        elif hasattr(user, 'employee_profile'):
             # Empleados: Admin/Dragon/Sales ven todo? Otros solo asignados?
            if user.has_role(Roles.ADMIN) or user.has_role(Roles.DRAGON) or user.has_role(Roles.SALES):
                 return base_qs.all()
            # Ejemplo: Resto de empleados solo ven las que gestionan
            return base_qs.filter(employee=user.employee_profile)
        return Order.objects.none() # Caso no esperado

    def perform_create(self, serializer):
        user = self.request.user
        customer = serializer.validated_data.get('customer')

        # Permitir crear a empleados (con ciertos roles?) o clientes para sí mismos
        if hasattr(user, 'employee_profile'):
             # ¿Qué roles de empleado pueden crear? Sales, Admin, Dragon?
             if not user.has_role(Roles.SALES) and not user.has_role(Roles.ADMIN) and not user.has_role(Roles.DRAGON):
                  raise PermissionDenied(_("No tienes permiso para crear pedidos para clientes."))
             if not serializer.validated_data.get('employee'):
                 serializer.save(employee=user.employee_profile) # Asignar creador por defecto
             else:
                 serializer.save()
        elif hasattr(user, 'customer_profile'):
            if customer == user.customer_profile:
                 serializer.save(employee=None) # Cliente crea para sí mismo
            else:
                  raise PermissionDenied(_("No puedes crear pedidos para otros clientes."))
        else:
            raise PermissionDenied(_("Perfil de usuario no válido para crear pedidos."))


class DeliverableViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverableSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'assigned_employee', 'assigned_provider', 'due_date']

    def get_queryset(self):
        user = self.request.user
        order_pk = self.kwargs.get('order_pk')
        base_qs = Deliverable.objects.all()

        if order_pk:
            base_qs = base_qs.filter(order__pk=order_pk)
            try:
                order = Order.objects.select_related('customer').get(pk=order_pk)
                can_access = False
                # Empleados (con roles?) y el cliente dueño pueden ver
                if hasattr(user, 'employee_profile'): # ¿Todos los empleados o roles específicos?
                    if user.has_role(Roles.ADMIN) or user.has_role(Roles.DEVELOPMENT) or user.has_role(Roles.SUPPORT) or user.has_role(Roles.DRAGON): # Ejemplo
                        can_access = True
                    elif order.employee == user.employee_profile: # Si es el gestor del pedido
                         can_access = True
                    # Podría añadirse: O si está asignado a alguna tarea de la orden
                elif hasattr(user, 'customer_profile') and order.customer == user.customer_profile:
                    can_access = True
                if not can_access: return Deliverable.objects.none()
            except Order.DoesNotExist: return Deliverable.objects.none()
        else: # Acceso directo a /deliverables/
             # Solo roles altos pueden ver todos los entregables
            if not user.has_role(Roles.ADMIN) and not user.has_role(Roles.DRAGON):
                return Deliverable.objects.none()

        return base_qs.select_related('assigned_employee__user', 'assigned_provider', 'order')

    def perform_create(self, serializer):
        order_pk = self.kwargs.get('order_pk')
        if not order_pk: raise ValidationError(_("La creación debe hacerse bajo una orden."))
        try:
            order = Order.objects.get(id=order_pk)
            user = self.request.user
            # ¿Qué roles pueden añadir entregables? DEV, ADMIN, DESIGN, AUDIOVISUAL?
            allowed_roles = [Roles.ADMIN, Roles.DRAGON, Roles.DEVELOPMENT, Roles.DESIGN, Roles.AUDIOVISUAL]
            if not any(user.has_role(role) for role in allowed_roles):
                 raise PermissionDenied(_("No tienes permiso para añadir entregables a este pedido."))
        except Order.DoesNotExist:
            raise ValidationError({"order": _("El pedido especificado no existe.")})
        serializer.save(order=order)


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all(); serializer_class = ServiceCategorySerializer; permission_classes = [AllowAny]


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related('category', 'campaign').prefetch_related('features', 'price_history').all()
    serializer_class = ServiceSerializer; filter_backends = [DjangoFilterBackend]; filterset_fields = ['category', 'is_active', 'is_package', 'is_subscription', 'ventulab']

    def get_permissions(self):
        # Solo Admin/Dragon modifican servicios
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [HasRolePermission([Roles.ADMIN, Roles.DRAGON])]
        else: # Lectura pública
             self.permission_classes = [AllowAny]
        return super().get_permissions()


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.prefetch_related('included_services__service').all()
    serializer_class = CampaignSerializer
    # Marketing, Admin, Dragon gestionan campañas
    permission_classes = [HasRolePermission([Roles.ADMIN, Roles.MARKETING, Roles.DRAGON])]
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['is_active', 'start_date', 'end_date']


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('order__customer__user').prefetch_related('payments__method').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'order__customer__user__username', 'date', 'due_date', 'invoice_number']

    def get_serializer_class(self):
         if self.action == 'list': return InvoiceBasicSerializer
         return InvoiceSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = super().get_queryset()
        if hasattr(user, 'customer_profile'):
            return base_qs.filter(order__customer=user.customer_profile) # Cliente ve las suyas
        elif hasattr(user, 'employee_profile'):
            # Finanzas, Admin, Dragon ven todas? Sales ve solo las de sus clientes?
            if user.has_role(Roles.FINANCE) or user.has_role(Roles.ADMIN) or user.has_role(Roles.DRAGON):
                 return base_qs
            # elif user.has_role(Roles.SALES): # Ejemplo: Sales ve las de órdenes que gestiona
            #      return base_qs.filter(order__employee=user.employee_profile)
            return Invoice.objects.none() # Otros roles no ven nada por defecto
        return Invoice.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Finanzas, Admin, Dragon crean facturas
        allowed_roles = [Roles.FINANCE, Roles.ADMIN, Roles.DRAGON]
        if not any(user.has_role(role) for role in allowed_roles):
            raise PermissionDenied(_("No tienes permiso para crear facturas."))
        # Validar si tiene permiso sobre la orden específica? Podría ser necesario
        serializer.save()


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('invoice__order__customer__user', 'method', 'transaction_type').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'method', 'transaction_type', 'currency', 'invoice__invoice_number', 'date']

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']: return PaymentReadSerializer
        return PaymentCreateSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = super().get_queryset()
        if hasattr(user, 'customer_profile'):
            return Payment.objects.none() # Clientes no ven pagos directamente
        elif hasattr(user, 'employee_profile'):
             # Finanzas, Admin, Dragon ven pagos
             allowed_roles = [Roles.FINANCE, Roles.ADMIN, Roles.DRAGON]
             if any(user.has_role(role) for role in allowed_roles):
                  return base_qs
        return Payment.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Finanzas, Admin, Dragon crean pagos
        allowed_roles = [Roles.FINANCE, Roles.ADMIN, Roles.DRAGON]
        if not any(user.has_role(role) for role in allowed_roles):
            raise PermissionDenied(_("No tienes permiso para registrar pagos."))
        # Validar si tiene permiso sobre la factura asociada?
        serializer.save()


class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer; permission_classes = [IsAuthenticated]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['form', 'question', 'customer__user__username']

    def get_queryset(self):
        user = self.request.user
        base_qs = FormResponse.objects.select_related('customer__user', 'form', 'question')
        if hasattr(user, 'customer_profile'):
             return base_qs.filter(customer=user.customer_profile) # Cliente ve las suyas
        elif hasattr(user, 'employee_profile'):
            # ¿Qué roles ven respuestas? Soporte, Ventas, Admin?
            allowed_roles = [Roles.SUPPORT, Roles.SALES, Roles.ADMIN, Roles.DRAGON]
            if any(user.has_role(role) for role in allowed_roles):
                return base_qs.all()
        return FormResponse.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if hasattr(user, 'customer_profile'):
            serializer.save(customer=user.customer_profile)
        else:
             raise PermissionDenied(_("Solo los clientes pueden enviar respuestas de formulario directamente."))

    @action(detail=False, methods=['post'], serializer_class=FormResponseBulkCreateSerializer)
    def bulk_create(self, request):
        user = request.user
        if not hasattr(user, 'customer_profile'):
            return Response({"detail": _("Solo los clientes pueden usar la creación masiva.")}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True);
        try:
            FormResponseService.bulk_create_responses(serializer.validated_data, user.customer_profile)
            return Response({"message": _("Respuestas creadas exitosamente")}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error en bulk_create FormResponse por {user.username}: {e}", exc_info=True)
            return Response({"detail": _("Ocurrió un error procesando las respuestas.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer; permission_classes = [IsAuthenticated];
    def get_queryset(self): return Notification.objects.filter(user=self.request.user)
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_as_read(self, request, pk=None): notification = self.get_object(); notification.read = True; notification.save(update_fields=['read']); serializer = self.get_serializer(notification); return Response(serializer.data)
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_as_read(self, request): updated_count = self.get_queryset().filter(read=False).update(read=True); return Response({'status': f'{updated_count} notificaciones marcadas como leídas'})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all()
    serializer_class = AuditLogSerializer
    # Solo Admin/Dragon ven logs
    permission_classes = [HasRolePermission([Roles.ADMIN, Roles.DRAGON])]
    filter_backends = [DjangoFilterBackend]; filterset_fields = { 'user__username': ['exact', 'icontains'], 'action': ['icontains'], 'timestamp': ['date', 'date__gte', 'date__lte', 'year', 'month'],}

# --- Opcional: ViewSets para gestionar Roles y Asignaciones ---
# class UserRoleViewSet(viewsets.ModelViewSet): ...
# class UserRoleAssignmentViewSet(viewsets.ModelViewSet): ...