# api/views/services_catalog.py
from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend

# Importaciones relativas
from ..models import ServiceCategory, Service, Campaign # Quitar Feature/Price si no hay ViewSet para ellos
from ..permissions import AllowAny, CanManageServices, CanManageCampaigns, IsAdminOrDragon

# --- Importaciones de Serializers Corregidas ---
from ..serializers.services_catalog import (
    ServiceCategorySerializer, ServiceSerializer, CampaignSerializer
    # Quitar Price/Feature/CampaignService si no hay ViewSet para ellos
    # PriceSerializer, ServiceFeatureSerializer, CampaignServiceSerializer
)
# ----------------------------------------------


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para listar y ver categorías de servicios.
    """
    queryset = ServiceCategory.objects.prefetch_related('services').all()
    # Usa el serializer importado correctamente
    serializer_class = ServiceCategorySerializer
    permission_classes = [AllowAny]


class ServiceViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Servicios.
    """
    queryset = Service.objects.select_related(
        'category',
        'campaign'
    ).prefetch_related(
        'features',
        'price_history'
    ).all()
    # Usa el serializer importado correctamente
    serializer_class = ServiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'category': ['exact'], 'category__name': ['exact', 'icontains'],
        'is_active': ['exact'], 'is_package': ['exact'],
        'is_subscription': ['exact'], 'name': ['icontains'],
        'ventulab': ['exact'], 'campaign': ['exact', 'isnull'],
    }

    def get_permissions(self):
        """ Permisos: Lectura pública, escritura restringida. """
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [AllowAny]
        else:
            self.permission_classes = [CanManageServices]
        return super().get_permissions()


class CampaignViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Campañas de marketing/promocionales.
    """
    queryset = Campaign.objects.prefetch_related(
        'campaignservice_set__service' # Ajustar related_name si es diferente
    ).all()
    # Usa el serializer importado correctamente
    serializer_class = CampaignSerializer
    permission_classes = [CanManageCampaigns]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'is_active': ['exact'],
        'start_date': ['date', 'date__gte', 'date__lte'],
        'end_date': ['date', 'date__gte', 'date__lte', 'isnull'],
        'name': ['icontains'],
    }