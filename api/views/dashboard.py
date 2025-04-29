# api/views/dashboard.py
import logging
from decimal import Decimal
from datetime import timedelta, datetime
from collections import defaultdict

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import (
    Sum, Count, Q, F, Avg, OuterRef, Subquery, ExpressionWrapper,
    DurationField, DecimalField, Case, When, Value, CharField
)
from django.db.models.functions import TruncMonth, Coalesce, Now
from django.contrib.auth import get_user_model # <--- IMPORTACIÓN AÑADIDA

# Importaciones relativas
from ..models import (
    Customer, Order, OrderService, Deliverable, Employee, Invoice, Payment, Service
    # 'User' eliminado de esta lista
)
from ..permissions import CanAccessDashboard

logger = logging.getLogger(__name__)
User = get_user_model() # <--- OBTENER MODELO User

class DashboardDataView(APIView):
    """
    Proporciona datos agregados y KPIs para mostrar en el dashboard principal.
    """
    permission_classes = [IsAuthenticated, CanAccessDashboard]

    def get(self, request, *args, **kwargs):
        # --- Log de Acceso ---
        user_roles_str = 'N/A'
        if hasattr(request.user, 'get_all_active_role_names'):
            try:
                roles_list = request.user.get_all_active_role_names
                user_roles_str = ', '.join(map(str, roles_list)) if isinstance(roles_list, (list, tuple, set)) else str(roles_list)
            except Exception as e:
                logger.warning(f"Error al obtener/formatear roles para log en Dashboard: {e}")
                user_roles_str = "[Error roles]"
        logger.info(f"[DashboardView] GET solicitado por {request.user.username} (Roles: {user_roles_str})")

        try:
            # --- Manejo de Fechas ---
            end_date_str = request.query_params.get('end_date', timezone.now().strftime('%Y-%m-%d'))
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                end_date = timezone.now().date()

            start_date_str = request.query_params.get('start_date')
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else end_date - timedelta(days=180)
            except ValueError:
                 start_date = end_date - timedelta(days=180)

            today = timezone.now().date()
            first_day_current_month = today.replace(day=1)
            last_day_prev_month = first_day_current_month - timedelta(days=1)
            first_day_prev_month = last_day_prev_month.replace(day=1)
            kpi_date_range = (first_day_prev_month, last_day_prev_month)

            one_year_ago = today - timedelta(days=365)
            fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)

            final_task_statuses = getattr(Deliverable, 'FINAL_STATUSES', ['COMPLETED', 'CANCELLED', 'ARCHIVED'])
            final_invoice_statuses = getattr(Invoice, 'FINAL_STATUSES', ['PAID', 'CANCELLED', 'VOID'])

            # --- Queries Optimizadas ---
            customer_demographics_qs = Customer.objects.filter(
                country__isnull=False
            ).exclude(
                country=''
            ).values('country').annotate(count=Count('id')).order_by('-count')
            customer_demographics_data = list(customer_demographics_qs)

            recent_orders_query = Order.objects.select_related(
                'customer__user', # Usa la relación user del modelo Customer
                'customer'
            ).order_by('-date_received')[:10]

            top_services_query = OrderService.objects.filter(
                order__date_received__date__range=(start_date, end_date),
                order__status='DELIVERED'
            ).values(
                'service__name', 'service__is_subscription'
            ).annotate(
                count=Count('id'),
                revenue=Coalesce(Sum(F('price') * F('quantity')), Decimal('0.00'), output_field=DecimalField())
            ).order_by('-count')[:10]
            top_services_data = list(top_services_query)

            payments_last_month = Payment.objects.filter(
                date__date__range=kpi_date_range,
                status='COMPLETED'
            )
            kpi_revenue_last_month = payments_last_month.aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'), output_field=DecimalField())
            )['total']

            completed_orders_last_month_count = Order.objects.filter(
                status='DELIVERED',
                completed_at__date__range=kpi_date_range
            ).count()

            kpi_aov = (kpi_revenue_last_month / completed_orders_last_month_count) if completed_orders_last_month_count > 0 else Decimal('0.00')

            kpi_subs_last_month_count = OrderService.objects.filter(
                order__date_received__date__range=kpi_date_range,
                service__is_subscription=True,
                order__status='DELIVERED'
            ).count()

            kpi_total_customers_count = Customer.objects.count()
            kpi_active_employees_count = Employee.objects.filter(user__is_active=True).count() # Usa relación user de Employee

            # Usa 'User' obtenido con get_user_model()
            active_users_count = User.objects.filter(
                last_login__gte=fifteen_minutes_ago,
                is_active=True
            ).count()

            top_customers_query = Payment.objects.filter(
                status='COMPLETED',
                date__date__range=(one_year_ago, today)
            ).values(
                'invoice__order__customer_id'
            ).annotate(
                customer_name=Subquery(
                    Customer.objects.filter(
                        pk=OuterRef('invoice__order__customer_id')
                    ).values(
                        name=Coalesce(
                            F('company_name'),
                            F('user__first_name'), # Usa relación user de Customer
                            F('user__username'),   # Usa relación user de Customer
                            output_field=CharField()
                        )
                    )[:1]
                ),
                total_revenue=Sum('amount')
            ).order_by('-total_revenue')[:5]
            top_customers_data = list(top_customers_query)

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
                status='DELIVERED',
                completed_at__isnull=False,
                date_received__isnull=False,
                completed_at__gte=F('date_received'),
                completed_at__date__range=(one_year_ago, today)
            ).aggregate(
                avg_duration=Avg(
                    ExpressionWrapper(F('completed_at') - F('date_received'), output_field=DurationField())
                )
            )
            avg_duration_days = avg_duration_data['avg_duration'].days if avg_duration_data['avg_duration'] else None

            employee_workload_query = Employee.objects.filter(
                user__is_active=True # Usa relación user de Employee
            ).annotate(
                active_tasks=Count('assigned_deliverables', filter=~Q(assigned_deliverables__status__in=final_task_statuses))
            ).values(
                'user__username',     # Usa relación user de Employee
                'user__first_name',   # Usa relación user de Employee
                'user__last_name',    # Usa relación user de Employee
                'active_tasks'
            ).order_by('-active_tasks')
            employee_workload_data = list(employee_workload_query)


            # --- Formateo de respuesta ---
            def get_customer_display_name(order):
                 if order.customer:
                     # Usa la relación 'user' del modelo Customer
                     user_obj = order.customer.user # Renombrado para evitar conflicto con User=get_user_model()
                     name_parts = [
                         order.customer.company_name,
                         user_obj.get_full_name() if user_obj and user_obj.get_full_name() else None,
                         user_obj.username if user_obj else None
                     ]
                     display_name = next((name for name in name_parts if name and name.strip()), None)
                     return display_name or _("Cliente ID {}").format(order.customer.id)
                 return _("Cliente Desconocido")

            formatted_recent_orders = []
            for o in recent_orders_query:
                try:
                    formatted_recent_orders.append({
                        'id': o.id,
                        'customer_name': get_customer_display_name(o),
                        'status': o.get_status_display(),
                        'date_received': o.date_received.isoformat() if o.date_received else None,
                        'total_amount': o.total_amount
                    })
                except Exception as e:
                    logger.error(f"[DashboardView] Error formateando orden reciente {o.id}: {e}", exc_info=True)
                    formatted_recent_orders.append({
                         'id': o.id, 'customer_name': 'Error al procesar', 'status': 'Error',
                         'date_received': None, 'total_amount': None
                    })

            # --- Ensamblaje Final de Datos ---
            dashboard_data = {
                'kpis': {
                    'revenue_last_month': kpi_revenue_last_month,
                    'subscriptions_last_month': kpi_subs_last_month_count,
                    'completed_orders_last_month': completed_orders_last_month_count,
                    'average_order_value_last_month': round(kpi_aov, 2) if kpi_aov else Decimal('0.00'),
                    'total_customers': kpi_total_customers_count,
                    'active_employees': kpi_active_employees_count,
                },
                'customer_demographics': customer_demographics_data,
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

            logger.info(f"[DashboardView] Datos generados exitosamente para {request.user.username}.")
            return Response(dashboard_data)

        except Exception as e:
             logger.error(f"[DashboardView] Error 500 inesperado para usuario {request.user.username}: {e}", exc_info=True)
             return Response({"detail": _("Ocurrió un error interno procesando los datos del dashboard.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)