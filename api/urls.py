# api/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers # Para rutas anidadas (opcional pero recomendado para delivera)
from rest_framework_simplejwt.views import TokenRefreshView

# Importa tus vistas desde views.py
from .views import (
    # Vistas de Autenticación
    CustomTokenObtainPairView,
    CheckAuthView,

    # ViewSets
    CustomerViewSet,
    EmployeeViewSet,
    JobPositionViewSet,
    OrderViewSet,
    DeliverableViewSet,
    ServiceViewSet,
    CampaignViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    FormResponseViewSet,
    UserMeView,# Añadido

    # Vistas Personalizadas (APIView)
    DashboardDataView,
)

# ------------------- Router Principal -------------------
# Crea un router para registrar los ViewSets principales
router = DefaultRouter()

# Registrar ViewSets principales
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'job_positions', JobPositionViewSet, basename='jobposition')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'campaigns', CampaignViewSet, basename='campaign')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'form_responses', FormResponseViewSet, basename='formresponse') # Añadido

# --- Rutas Anidadas para Entregables (Recomendado) ---
# Crea un router anidado bajo 'orders' para 'deliverables'
# Esto generará URLs como /api/orders/{order_pk}/deliverables/ y /api/orders/{order_pk}/deliverables/{deliverable_pk}/
# Nota: Necesitarás instalar `drf-nested-routers`: pip install drf-nested-routers
orders_router = routers.NestedDefaultRouter(router, r'orders', lookup='order')
orders_router.register(r'deliverables', DeliverableViewSet, basename='order-deliverables')
# Si no quieres instalar drf-nested-routers, usa las rutas manuales comentadas abajo.

# ------------------- URLs Principales de la API -------------------
urlpatterns = [
    # --- Incluir URLs del Router Principal ---
    path('', include(router.urls)),

    # --- Incluir URLs del Router Anidado (si usas drf-nested-routers) ---
    path('', include(orders_router.urls)),

    # --- Rutas de Autenticación ---
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/check/', CheckAuthView.as_view(), name='auth_check'),

    # --- Ruta del Dashboard ---
    path('dashboard/', DashboardDataView.as_view(), name='dashboard_data'),


    path('users/me/', UserMeView.as_view(), name='user-me'),
    # --- Rutas Anidadas Manuales (Alternativa si NO usas drf-nested-routers) ---
    # Descomenta estas líneas y comenta las de orders_router si prefieres rutas manuales:
    # path('orders/<int:order_pk>/deliverables/', DeliverableViewSet.as_view({'get': 'list', 'post': 'create'}), name='order-deliverables-list'),
    # path('orders/<int:order_pk>/deliverables/<int:pk>/', DeliverableViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='order-deliverables-detail'),

    # --- Puedes añadir más rutas personalizadas aquí si es necesario ---

]

# Nota: Asegúrate de que las rutas anidadas (ya sea con drf-nested-routers o manuales)
# coincidan con cómo tu DeliverableViewSet espera obtener el 'order_id' o 'order_pk'.
# La implementación actual de DeliverableViewSet parece esperar 'order_id' de self.kwargs,
# lo cual funcionaría con la versión manual que usa <int:order_pk>.
# Si usas drf-nested-routers, asegúrate que el lookup='order' esté correcto.
# Si da error, ajusta el `lookup` en el router anidado o cómo accedes a la clave en la vista.