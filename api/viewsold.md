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
# --- ASEGÚRATE DE IMPORTAR ESTO ---
from rest_framework_simplejwt.views import TokenObtainPairView
# --- FIN IMPORTACIÓN ---

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
    # --- NUEVOS MODELOS (Asegúrate que existan y se importen) ---
    UserRole, UserProfile, UserRoleAssignment
)
# Importar constantes de roles (Asegúrate que este archivo exista)
try:
    from .roles import Roles
except ImportError:
    class Roles: # Placeholder si roles.py no existe
        DRAGON = 'dragon'; ADMIN = 'admin'; MARKETING = 'mktg'; FINANCE = 'fin';
        SALES = 'sales'; DEVELOPMENT = 'dev'; SUPPORT = 'support'; OPERATIONS = 'ops';
        DESIGN = 'design'; AUDIOVISUAL = 'av';
    print("ADVERTENCIA: api/roles.py no encontrado. Usando roles placeholder.")


# Importar TODOS los serializers necesarios
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
# ------------------------- PERMISOS PERSONALIZADOS --------------------------
# ==============================================================================
# (Asumiendo que tu implementación de HasRolePermission y subclases es correcta
# y que User tiene un método has_role(self, role_name))

class HasRolePermission(BasePermission):
    """Permiso base que verifica roles. Las subclases deben definir required_roles."""
    required_roles = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        # Verifica si es staff (acceso general) O tiene uno de los roles específicos
        # Asume que request.user tiene un método has_role
        user_has_role = False
        if hasattr(request.user, 'has_role'):
            user_has_role = any(request.user.has_role(role) for role in self.required_roles)
        return request.user.is_staff or user_has_role

class CanAccessDashboard(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.FINANCE, Roles.MARKETING, Roles.SALES, Roles.OPERATIONS]

# ... (Otras subclases de permiso) ...
class IsAdminOrDragon(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON]
class CanManageEmployees(IsAdminOrDragon): pass
class CanManageJobPositions(IsAdminOrDragon): pass
class CanManageCampaigns(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.MARKETING]
class CanManageServices(IsAdminOrDragon): pass
class CanManageFinances(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.FINANCE]
class CanViewAllOrders(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES, Roles.SUPPORT, Roles.OPERATIONS]
class CanCreateOrders(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES]
class CanViewAllDeliverables(IsAdminOrDragon): pass
class CanCreateDeliverables(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.DEVELOPMENT, Roles.DESIGN, Roles.AUDIOVISUAL, Roles.OPERATIONS]
class CanViewFormResponses(HasRolePermission): required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES, Roles.SUPPORT]
class CanViewAuditLogs(IsAdminOrDragon): pass


# ==============================================================================
# ------------------------- VISTAS DE LA API (CORREGIDAS) --------------------
# ==============================================================================

# --- VISTA USER ME ---
class UserMeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        # ***** ¡OPTIMIZACIÓN IMPORTANTE! *****
        try:
            user = User.objects.select_related(
                'profile__primary_role',
                'employee_profile__position' # <-- Añadir esto
            ).get(pk=request.user.pk)
        except User.DoesNotExist:
             # Esto no debería pasar si está autenticado, pero por seguridad
             return Response({"detail": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        # ***********************************
        serializer = BasicUserSerializer(user, context={'request': request})
        return Response(serializer.data)

# ---------------------- Autenticación y Verificación ----------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class CheckAuthView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        # ***** ¡OPTIMIZACIÓN IMPORTANTE! *****
        try:
            user = User.objects.select_related(
                'profile__primary_role',
                'employee_profile__position' # <-- Añadir esto
            ).get(pk=request.user.pk)
        except User.DoesNotExist:
             return Response({"isAuthenticated": False, "user": None}, status=status.HTTP_401_UNAUTHORIZED)
        # ***********************************
        serializer = BasicUserSerializer(user, context={'request': request})
        data = {"isAuthenticated": True, "user": serializer.data}
        return Response(data)

# ---------------------- Dashboard ------------------------------------------
class DashboardDataView(APIView):
    """Proporciona datos agregados para el dashboard."""
    permission_classes = [CanAccessDashboard] # <-- Usa la subclase

    def get(self, request, *args, **kwargs):
        # --- CORRECCIÓN LOG: Accede a la propiedad sin () ---
        user_roles_str = 'N/A'
        if hasattr(request.user, 'get_all_active_role_names'):
            try:
                # Accede directamente a la propiedad que devuelve una lista
                roles_list = request.user.get_all_active_role_names
                if isinstance(roles_list, (list, tuple, set)):
                    user_roles_str = ', '.join(map(str, roles_list)) # Convierte a string
                else: # Fallback por si devuelve otra cosa
                    user_roles_str = str(roles_list)
            except Exception as e:
                logger.warning(f"Error al obtener/formatear roles para log: {e}")
                user_roles_str = "[Error al obtener roles]"

        logger.info(f"[DashboardView] Iniciando GET para usuario {request.user.username} (Roles: {user_roles_str})")
        # --- Manejo de excepciones y errores ---

        try:
            # --- Manejo de Fechas ---
            # ... (código de fechas sin cambios)...
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

            # --- Queries Optimizadas (Asegúrate que los nombres de campo sean correctos) ---
            customer_demographics_qs = Customer.objects.filter(
                country__isnull=False
            ).exclude(
                country='' # Correcto
            ).values('country').annotate(count=Count('id')).order_by('-count')
            customer_demographics_data = list(customer_demographics_qs)

            recent_orders_query = Order.objects.select_related('customer__user', 'customer').order_by('-date_received')[:10]

            top_services_query = OrderService.objects.filter(
                order__date_received__date__range=(start_date, end_date), order__status='DELIVERED'
            ).values(
                'service__name', 'service__is_subscription'
            ).annotate(
                count=Count('id'),
                revenue=Coalesce(Sum(F('price') * F('quantity')), Decimal('0.00'), output_field=DecimalField())
            ).order_by('-count')[:10]
            top_services_data = list(top_services_query)

            payments_last_month = Payment.objects.filter(date__date__range=kpi_date_range, status='COMPLETED')
            kpi_revenue_last_month = payments_last_month.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00'), output_field=DecimalField()))['total']
            completed_orders_last_month_count = Order.objects.filter(status='DELIVERED', completed_at__date__range=kpi_date_range).count()
            kpi_aov = (kpi_revenue_last_month / completed_orders_last_month_count) if completed_orders_last_month_count > 0 else Decimal('0.00')
            kpi_subs_last_month_count = OrderService.objects.filter(order__date_received__date__range=kpi_date_range, service__is_subscription=True, order__status='DELIVERED').count()
            kpi_total_customers_count = Customer.objects.count()
            kpi_active_employees_count = Employee.objects.filter(user__is_active=True).count()
            active_users_count = User.objects.filter(last_login__gte=fifteen_minutes_ago, is_active=True).count()

            top_customers_query = Payment.objects.filter(
                status='COMPLETED', date__date__range=(one_year_ago, today)
            ).values('invoice__order__customer_id').annotate(
                customer_name=Subquery(Customer.objects.filter(pk=OuterRef('invoice__order__customer_id')).values(name=Coalesce(F('company_name'), F('user__first_name'), F('user__username'), output_field=CharField()))[:1]),
                total_revenue=Sum('amount')
            ).order_by('-total_revenue')[:5]
            top_customers_data = list(top_customers_query)

            task_summary = Deliverable.objects.aggregate(total_active=Count('id', filter=~Q(status__in=final_task_statuses)), unassigned=Count('id', filter=Q(assigned_employee__isnull=True) & Q(assigned_provider__isnull=True) & ~Q(status__in=final_task_statuses)), pending_approval=Count('id', filter=Q(status__in=['PENDING_APPROVAL', 'PENDING_INTERNAL_APPROVAL'])), requires_info=Count('id', filter=Q(status='REQUIRES_INFO')), assigned_to_provider=Count('id', filter=Q(assigned_provider__isnull=False) & ~Q(status__in=final_task_statuses)), overdue=Count('id', filter=Q(due_date__isnull=False, due_date__lt=today) & ~Q(status__in=final_task_statuses)))
            invoice_summary = Invoice.objects.filter(~Q(status='DRAFT')).aggregate(total_active=Count('id', filter=~Q(status__in=final_invoice_statuses)), pending=Count('id', filter=Q(status__in=['SENT', 'PARTIALLY_PAID', 'OVERDUE'])), paid_count=Count('id', filter=Q(status='PAID')), overdue_count=Count('id', filter=Q(status='OVERDUE')))

            avg_duration_data = Order.objects.filter(status='DELIVERED', completed_at__isnull=False, date_received__isnull=False, completed_at__gte=F('date_received'), completed_at__date__range=(one_year_ago, today)).aggregate(avg_duration=Avg(ExpressionWrapper(F('completed_at') - F('date_received'), output_field=DurationField())))
            avg_duration_days = avg_duration_data['avg_duration'].days if avg_duration_data['avg_duration'] else None

            employee_workload_query = Employee.objects.filter(user__is_active=True).annotate(active_tasks=Count('assigned_deliverables', filter=~Q(assigned_deliverables__status__in=final_task_statuses))).values('user__username', 'user__first_name', 'user__last_name', 'active_tasks').order_by('-active_tasks')
            employee_workload_data = list(employee_workload_query)

            # --- Formateo de respuesta ---
            def get_customer_display_name(order):
                 if order.customer:
                     user = order.customer.user
                     name_parts = [order.customer.company_name, user.get_full_name() if user else None, user.username if user else None]
                     display_name = next((name for name in name_parts if name), None)
                     return display_name or _("Cliente Desconocido")
                 return _("Cliente Desconocido")

            formatted_recent_orders = []
            for o in recent_orders_query:
                try:
                    formatted_recent_orders.append({
                        'id': o.id, 'customer_name': get_customer_display_name(o),
                        'status': o.get_status_display(),
                        'date_received': o.date_received.isoformat() if o.date_received else None,
                        'total_amount': o.total_amount
                    })
                except Exception as e:
                    logger.error(f"[DashboardView] Error formateando orden {o.id}: {e}", exc_info=True)

            dashboard_data = {
                'kpis': {'revenue_last_month': kpi_revenue_last_month,'subscriptions_last_month': kpi_subs_last_month_count,'completed_orders_last_month': completed_orders_last_month_count,'average_order_value_last_month': round(kpi_aov, 2) if kpi_aov else 0.00,'total_customers': kpi_total_customers_count,'active_employees': kpi_active_employees_count,'profit_loss_last_month': None,},
                'customer_demographics': customer_demographics_data,
                'recent_orders': formatted_recent_orders,
                'top_services': {'start_date': start_date.strftime('%Y-%m-%d'),'end_date': end_date.strftime('%Y-%m-%d'),'data': top_services_data },
                'active_users_now': active_users_count,
                'top_customers_last_year': top_customers_data,
                'task_summary': task_summary,
                'invoice_summary': invoice_summary,
                'average_order_duration_days': avg_duration_days,
                'employee_workload': employee_workload_data,
            }
            logger.info(f"[DashboardView] Datos generados exitosamente para {request.user.username}.")
            return Response(dashboard_data)

        except Exception as e:
             logger.error(f"[DashboardView] Error 500 inesperado para usuario {request.user.username}: {e}", exc_info=True)
             return Response({"detail": _("Ocurrió un error interno procesando los datos del dashboard.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ---------------------- ViewSets CRUD (Aplicando Permisos por Rol) ----------------------
# (Se mantienen como en la versión anterior, usando las subclases de permisos
#  o la lógica en get_permissions/check_permissions según corresponda)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('user__profile__primary_role').all()
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['user__email', 'preferred_contact_method', 'country']
    def get_serializer_class(self): return CustomerCreateSerializer if self.action == 'create' else CustomerSerializer
    def get_permissions(self):
        # ... (lógica de permisos con subclases como IsCustomerOwnerOrAdminOrSupport, etc.) ...
         if self.action == 'create': self.permission_classes = [AllowAny]
         # ... otros casos ...
         else: self.permission_classes = [IsAuthenticated]
         return super().get_permissions()

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('user__profile__primary_role', 'position').prefetch_related('user__secondary_role_assignments__role').filter(user__is_active=True)
    permission_classes = [CanManageEmployees] # Usa subclase
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['position__name', 'user__username', 'user__profile__primary_role__name']
    def get_serializer_class(self): return EmployeeCreateSerializer if self.action == 'create' else EmployeeSerializer

class JobPositionViewSet(viewsets.ModelViewSet):
    queryset = JobPosition.objects.all(); serializer_class = JobPositionSerializer; permission_classes = [CanManageJobPositions] # Usa subclase

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all(); permission_classes = [IsAuthenticated]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'customer__user__username', 'priority', 'employee__user__username', 'date_received', 'date_required']
    def get_serializer_class(self): return OrderReadSerializer if self.action in ['list', 'retrieve'] else OrderCreateUpdateSerializer
    def get_queryset(self):
        user = self.request.user; base_qs = Order.objects.select_related('customer__user', 'employee__user').prefetch_related('services__service', 'deliverables')
        if hasattr(user, 'customer_profile'): return base_qs.filter(customer=user.customer_profile)
        elif hasattr(user, 'employee_profile'):
            if CanViewAllOrders().has_permission(request=user, view=self): return base_qs.all()
            return base_qs.filter(employee=user.employee_profile)
        return Order.objects.none()
    def perform_create(self, serializer):
        user = self.request.user; customer = serializer.validated_data.get('customer')
        if hasattr(user, 'employee_profile'):
            if not CanCreateOrders().has_permission(request=user, view=self): raise PermissionDenied(_("No tienes permiso para crear pedidos."))
            employee_to_assign = serializer.validated_data.get('employee', user.employee_profile); serializer.save(employee=employee_to_assign)
        elif hasattr(user, 'customer_profile'):
            if customer == user.customer_profile: serializer.save(employee=None)
            else: raise PermissionDenied(_("No puedes crear pedidos para otros clientes."))
        else: raise PermissionDenied(_("Perfil de usuario no válido."))

class DeliverableViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverableSerializer; permission_classes = [IsAuthenticated]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'assigned_employee', 'assigned_provider', 'due_date']
    def get_queryset(self):
        # ... (lógica get_queryset como antes, usando has_permission si es necesario) ...
        user = self.request.user; order_pk = self.kwargs.get('order_pk'); base_qs = Deliverable.objects.select_related('assigned_employee__user', 'assigned_provider', 'order__customer__user', 'order__employee__user')
        if order_pk:
            base_qs = base_qs.filter(order__pk=order_pk);
            try:
                 order = Order.objects.select_related('customer').get(pk=order_pk)
                 # Simplificado: si puede ver la orden, puede ver los entregables (ajusta si es necesario)
                 perm_checker = CanViewAllOrders() # Reemplazado con una clase de permiso existente
                 if not perm_checker.has_object_permission(self.request, self, order): return Deliverable.objects.none()
            except Order.DoesNotExist: return Deliverable.objects.none()
        else:
            if not CanViewAllDeliverables().has_permission(request=user, view=self): return Deliverable.objects.none()
        return base_qs
    def perform_create(self, serializer):
        # ... (lógica perform_create como antes, usando has_permission) ...
        order_pk = self.kwargs.get('order_pk'); user = self.request.user
        if not order_pk: raise ValidationError(_("La creación debe hacerse bajo una orden."))
        try: order = Order.objects.get(id=order_pk)
        except Order.DoesNotExist: raise ValidationError({"order": _("El pedido especificado no existe.")})
        if not CanCreateDeliverables().has_permission(request=user, view=self): raise PermissionDenied(_("No tienes permiso para añadir entregables."))
        serializer.save(order=order)


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all(); serializer_class = ServiceCategorySerializer; permission_classes = [AllowAny]

class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.select_related('category', 'campaign').prefetch_related('features', 'price_history').all()
    serializer_class = ServiceSerializer; filter_backends = [DjangoFilterBackend]; filterset_fields = ['category', 'is_active', 'is_package', 'is_subscription', 'ventulab']
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']: self.permission_classes = [CanManageServices]
        else: self.permission_classes = [AllowAny]
        return super().get_permissions()

class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.prefetch_related('included_services__service').all(); serializer_class = CampaignSerializer
    permission_classes = [CanManageCampaigns]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['is_active', 'start_date', 'end_date']

class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('order__customer__user', 'order__employee__user').prefetch_related('payments__method')
    permission_classes = [IsAuthenticated]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'order__customer__user__username', 'date', 'due_date', 'invoice_number']
    def get_serializer_class(self): return InvoiceBasicSerializer if self.action == 'list' else InvoiceSerializer
    def get_queryset(self):
        user = self.request.user; base_qs = super().get_queryset()
        if hasattr(user, 'customer_profile'): return base_qs.filter(order__customer=user.customer_profile)
        elif hasattr(user, 'employee_profile'):
            if CanManageFinances().has_permission(request=user, view=self): return base_qs
        return Invoice.objects.none()
    def perform_create(self, serializer):
        if not CanManageFinances().has_permission(request=self.request, view=self): raise PermissionDenied(_("No tienes permiso para crear facturas."))
        serializer.save()

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('invoice__order__customer__user', 'method', 'transaction_type').all()
    permission_classes = [CanManageFinances] # Solo roles financieros
    filter_backends = [DjangoFilterBackend]; filterset_fields = ['status', 'method', 'transaction_type', 'currency', 'invoice__invoice_number', 'date']
    def get_serializer_class(self): return PaymentReadSerializer if self.action in ['list', 'retrieve'] else PaymentCreateSerializer

class FormResponseViewSet(viewsets.ModelViewSet):
    serializer_class = FormResponseSerializer; permission_classes = [IsAuthenticated]; filter_backends = [DjangoFilterBackend]; filterset_fields = ['form', 'question', 'customer__user__username']
    def get_queryset(self):
        user = self.request.user; base_qs = FormResponse.objects.select_related('customer__user', 'form', 'question')
        if hasattr(user, 'customer_profile'): return base_qs.filter(customer=user.customer_profile)
        elif hasattr(user, 'employee_profile'):
            if CanViewFormResponses().has_permission(request=user, view=self): return base_qs.all()
        return FormResponse.objects.none()
    def perform_create(self, serializer):
        if hasattr(self.request.user, 'customer_profile'): serializer.save(customer=self.request.user.customer_profile)
        else: raise PermissionDenied(_("Solo los clientes pueden enviar respuestas."))
    @action(detail=False, methods=['post'], serializer_class=FormResponseBulkCreateSerializer)
    def bulk_create(self, request):
        # ... (lógica bulk_create sin cambios) ...
         user = request.user
         if not hasattr(user, 'customer_profile'): return Response({"detail": _("Solo los clientes pueden usar la creación masiva.")}, status=status.HTTP_403_FORBIDDEN)
         serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True);
         try:
             FormResponseService.bulk_create_responses(serializer.validated_data, user.customer_profile)
             return Response({"message": _("Respuestas creadas exitosamente")}, status=status.HTTP_201_CREATED)
         except Exception as e:
             logger.error(f"Error en bulk_create FormResponse por {user.username}: {e}", exc_info=True)
             return Response({"detail": _("Ocurrió un error procesando las respuestas.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer; permission_classes = [IsAuthenticated];
    def get_queryset(self): return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_as_read(self, request, pk=None): notification = self.get_object(); notification.read = True; notification.save(update_fields=['read']); serializer = self.get_serializer(notification); return Response(serializer.data)
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_as_read(self, request): updated_count = self.get_queryset().filter(read=False).update(read=True); return Response({'status': f'{updated_count} notificaciones marcadas como leídas'})

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all().order_by('-timestamp')
    serializer_class = AuditLogSerializer; permission_classes = [CanViewAuditLogs] # Usa subclase
    filter_backends = [DjangoFilterBackend]; filterset_fields = { 'user__username': ['exact', 'icontains'], 'action': ['icontains'], 'timestamp': ['date', 'date__gte', 'date__lte', 'year', 'month'],}