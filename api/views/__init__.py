# api/views/__init__.py
# Este archivo está intencionalmente vacío.
# Sirve para que Python trate el directorio 'views' como un paquete,
# permitiendo importaciones como 'from .authentication import ...'

#api/permissions.py (Contiene las clases de permisos)
#api/services.py (Contiene la lógica de servicio, como FormResponseService)
#api/views/__init__.py (Archivo vacío para marcar el directorio como paquete)
#api/views/authentication.py (Vistas de login y chequeo de autenticación)
#api/views/users.py (Vista UserMeView)
#api/views/dashboard.py (Vista DashboardDataView)
#api/views/customers.py (Vista CustomerViewSet)
#api/views/employees.py (Vistas EmployeeViewSet, JobPositionViewSet)
#api/views/orders.py (Vistas OrderViewSet, DeliverableViewSet)
#api/views/services_catalog.py (Vistas ServiceCategoryViewSet, ServiceViewSet, CampaignViewSet)
#api/views/finances.py (Vistas InvoiceViewSet, PaymentViewSet)
#api/views/forms.py (Vista FormResponseViewSet)
#api/views/utilities.py (Vistas NotificationViewSet, AuditLogViewSet)
#En total, son 13 archivos (11 archivos de código + 1 __init__.py + 1 services.py). Adicionalmente, deberás modificar tu api/urls.py existente #para importar desde estos nuevos módulos.