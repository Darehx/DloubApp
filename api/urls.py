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

# Crear un router y registrar todos los viewsets
router = DefaultRouter()
router.register('form_responses', FormResponseViewSet)
router.register('customers', CustomerViewSet)
router.register('employees', EmployeeViewSet)
router.register('orders', OrderViewSet)
router.register('deliverables', DeliverableViewSet)
router.register('services', ServiceViewSet)
router.register('campaigns', CampaignViewSet)
router.register('invoices', InvoiceViewSet)
router.register('payments', PaymentViewSet)

urlpatterns = [
    # Incluye las URLs generadas automáticamente por el router
    path('', include(router.urls)),

    # URL personalizada para la acción de creación masiva de respuestas
    path('form_responses/bulk_create/', FormResponseViewSet.as_view({'post': 'bulk_create'}), name='bulk-create-response'),

    # URL personalizada para obtener el token de autenticación (JWT)
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
]
