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
    CustomTokenObtainPairView
)

# Crear un router
router = DefaultRouter()

# Registrar ViewSets en el router sin necesidad de basename, solo cuando sea necesario
router.register(r'form_responses', FormResponseViewSet, basename='form_responses')  # Aquí usamos basename porque es necesario
router.register(r'customers', CustomerViewSet)
router.register(r'employees', EmployeeViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'deliverables', DeliverableViewSet, basename='deliverables')  # Agrega basename aquí
router.register(r'services', ServiceViewSet)
router.register(r'campaigns', CampaignViewSet)
router.register(r'invoices', InvoiceViewSet, basename='invoices')  # Agrega basename aquí
router.register(r'payments', PaymentViewSet, basename='payments')  # Agrega basename aquí

# Definir las rutas
urlpatterns = [
    # Incluir todas las URLs generadas por el router
    path('', include(router.urls)),

    # URL personalizada para la acción de creación masiva de respuestas
    path('form_responses/bulk_create/', FormResponseViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-response'),

    # URL personalizada para obtener el token de autenticación (JWT)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
