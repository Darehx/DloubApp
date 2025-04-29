# api/serializers/services_catalog.py
"""
Serializers para el catálogo de servicios, campañas, precios y características.
"""
from rest_framework import serializers

# Importar modelos necesarios
from ..models import (
    ServiceCategory, Price, ServiceFeature, Service, Campaign, CampaignService
)

class ServiceCategorySerializer(serializers.ModelSerializer):
    """ Serializer para Categorías de Servicio. """
    class Meta:
        model = ServiceCategory
        fields = '__all__' # ['code', 'name']

class PriceSerializer(serializers.ModelSerializer):
    """ Serializer para mostrar historial de Precios. """
    class Meta:
        model = Price
        fields = ['id', 'amount', 'currency', 'effective_date']
        read_only_fields = fields # Solo lectura

class ServiceFeatureSerializer(serializers.ModelSerializer):
    """ Serializer para mostrar Características de Servicio. """
    feature_type_display = serializers.CharField(source='get_feature_type_display', read_only=True)
    class Meta:
        model = ServiceFeature
        # No incluir 'service' si se anida
        fields = ['id', 'feature_type', 'feature_type_display', 'description']
        read_only_fields = ['id', 'feature_type_display']

class ServiceSerializer(serializers.ModelSerializer):
    """ Serializer para leer/escribir información de Servicios. """
    # Campos legibles
    category_name = serializers.CharField(source='category.name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.campaign_name', read_only=True, allow_null=True)
    features = ServiceFeatureSerializer(many=True, read_only=True)
    price_history = PriceSerializer(many=True, read_only=True)
    current_eur_price = serializers.SerializerMethodField()

    # Campos para escribir (FKs)
    category = serializers.PrimaryKeyRelatedField(queryset=ServiceCategory.objects.all(), write_only=True)
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all(), write_only=True, required=False, allow_null=True)

    class Meta:
        model = Service
        fields = [
            'code', 'name', 'category', 'category_name', 'campaign', 'campaign_name',
            'is_active', 'ventulab', 'is_package', 'is_subscription', 'audience',
            'detailed_description', 'problem_solved', 'features', 'price_history',
            'current_eur_price'
        ]
        read_only_fields = [
            'code', 'category_name', 'campaign_name', 'features',
            'price_history', 'current_eur_price'
        ]
        # Hacer los campos FK write_only si no se quieren devolver explícitamente
        # extra_kwargs = {
        #     'category': {'write_only': True},
        #     'campaign': {'write_only': True},
        # }

    def get_current_eur_price(self, obj):
        """ Devuelve el monto del precio actual en EUR. """
        price = obj.get_current_price(currency='EUR')
        return price.amount if price else None

class CampaignServiceSerializer(serializers.ModelSerializer):
    """ Serializer para la relación entre Campaña y Servicio. """
    # Campos legibles
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_code = serializers.CharField(source='service.code', read_only=True)
    # Campos para escribir (asociar servicio)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), write_only=True)

    class Meta:
        model = CampaignService
        fields = [
            'id', 'campaign', 'service', 'service_code', 'service_name',
            'discount_percentage', 'additional_details'
        ]
        # 'campaign' es read_only si este serializer se anida dentro de CampaignSerializer
        read_only_fields = ['id', 'campaign', 'service_code', 'service_name']

class CampaignSerializer(serializers.ModelSerializer):
    """ Serializer para Campañas, incluyendo servicios asociados. """
    # Mostrar servicios incluidos (lectura)
    included_services = CampaignServiceSerializer(many=True, read_only=True, source='campaignservice_set') # Ajustar source si related_name es diferente

    class Meta:
        model = Campaign
        fields = [
            'campaign_code', 'campaign_name', 'start_date', 'end_date',
            'description', 'target_audience', 'budget', 'is_active',
            'included_services',
        ]
        read_only_fields = ['campaign_code', 'included_services']