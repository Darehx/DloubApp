# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
# drf-nested-routers es genial para esto, mantenlo si lo tienes instalado
from rest_framework_nested import routers
from rest_framework_simplejwt.views import TokenRefreshView

# --- Importa los MÓDULOS de vistas ---
# Importa cada módulo que contiene las vistas que necesitas referenciar.
from .views import (
    authentication,
    users,
    dashboard,
    customers,
    employees,
    orders,
    services_catalog,
    finances,
    forms,
    utilities,
)
# Nota: Ya no importas las clases individuales directamente aquí (excepto TokenRefreshView)

# ------------------- Router Principal -------------------
router = DefaultRouter()

# --- Registrar ViewSets usando los módulos importados ---
# Referencia la clase ViewSet a través del módulo importado.
router.register(r'customers', customers.CustomerViewSet, basename='customer')
router.register(r'employees', employees.EmployeeViewSet, basename='employee')
# Usa kebab-case para consistencia en las URLs
router.register(r'job-positions', employees.JobPositionViewSet, basename='jobposition')
router.register(r'orders', orders.OrderViewSet, basename='order')
router.register(r'services', services_catalog.ServiceViewSet, basename='service')
router.register(r'service-categories', services_catalog.ServiceCategoryViewSet, basename='servicecategory') # Añadido si existe
router.register(r'campaigns', services_catalog.CampaignViewSet, basename='campaign')
router.register(r'invoices', finances.InvoiceViewSet, basename='invoice')
router.register(r'payments', finances.PaymentViewSet, basename='payment')
# Usa kebab-case para consistencia
router.register(r'form-responses', forms.FormResponseViewSet, basename='formresponse')
router.register(r'notifications', utilities.NotificationViewSet, basename='notification') # Añadido si existe
router.register(r'audit-logs', utilities.AuditLogViewSet, basename='auditlog') # Añadido si existe

# --- Rutas Anidadas para Entregables (Usando drf-nested-routers) ---
# Asegúrate que el lookup ('order') coincida con cómo DeliverableViewSet espera el ID.
# drf-nested-routers normalmente pasa el kwarg como '{lookup}_pk', así que 'order_pk'.
# Verifica que tu DeliverableViewSet use self.kwargs.get('order_pk').
orders_router = routers.NestedDefaultRouter(router, r'orders', lookup='order')
orders_router.register(r'deliverables', orders.DeliverableViewSet, basename='order-deliverables')
# Nota: Si tu DeliverableViewSet espera 'order_id', cambia lookup='order' a lookup='order_id'
# o ajusta la vista para que use 'order_pk'.

# ------------------- URLs Principales de la API -------------------
urlpatterns = [
    # --- Incluir URLs del Router Principal ---
    path('', include(router.urls)),

    # --- Incluir URLs del Router Anidado ---
    # Esto registrará las rutas como /orders/{order_pk}/deliverables/
    path('', include(orders_router.urls)),

    # --- Rutas de Autenticación (APIView) ---
    # Referencia las vistas a través de los módulos importados
    path('token/', authentication.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Esta viene de simplejwt
    path('auth/check/', authentication.CheckAuthView.as_view(), name='auth_check'),

    # --- Ruta del Dashboard (APIView) ---
    path('dashboard/', dashboard.DashboardDataView.as_view(), name='dashboard_data'),

    # --- Ruta de Usuario (APIView) ---
    path('users/me/', users.UserMeView.as_view(), name='user-me'), # Usa 'user-me' como tenías

    # --- Rutas Anidadas Manuales (Alternativa si NO usas drf-nested-routers) ---
    # Mantenlas comentadas si usas drf-nested-routers
    # path('orders/<int:order_pk>/deliverables/', orders.DeliverableViewSet.as_view({'get': 'list', 'post': 'create'}), name='order-deliverables-list-manual'),
    # path('orders/<int:order_pk>/deliverables/<int:pk>/', orders.DeliverableViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='order-deliverables-detail-manual'),

    # --- Puedes añadir más rutas personalizadas (APIView o @action) aquí ---
    # path('ruta/especial/', modulo_vistas.VistaEspecial.as_view(), name='vista_especial'),
]