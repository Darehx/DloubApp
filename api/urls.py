from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FormResponseViewSet,
    CustomerViewSet,
    EmployeeViewSet,
    OrderViewSet,
    DeliverableViewSet,
    ServiceViewSet,
    CampaignViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    CustomTokenObtainPairView  # Asegúrate de que esta línea esté presente
)

# Crear un router
router = DefaultRouter()

# Registrar ViewSets en el router
router.register(r'form_responses', FormResponseViewSet, basename='form_responses')
router.register(r'customers', CustomerViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'deliverables', DeliverableViewSet)
router.register(r'services', ServiceViewSet)
router.register(r'campaigns', CampaignViewSet)
router.register(r'invoices', InvoiceViewSet, basename='invoices')
router.register(r'payments', PaymentViewSet, basename='payments')

# Definir las rutas
urlpatterns = [
    # Incluir todas las URLs generadas por el router
    path('', include(router.urls)),
    
    # URL personalizada para la acción de creación masiva de respuestas
    path('form_responses/bulk_create/', FormResponseViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-response'),
    
    # URL personalizada para obtener el token de autenticación (JWT)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
]