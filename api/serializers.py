# api/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from decimal import Decimal
from django.db import transaction # <--- IMPORTACIÓN AÑADIDA

# Import todos los modelos necesarios
from .models import (
    Form, FormQuestion, FormResponse, Customer, JobPosition, Employee,
    Order, ServiceCategory, Campaign, Service, ServiceFeature, Price,
    OrderService, Deliverable, TransactionType, PaymentMethod, Invoice,
    Payment, CampaignService, Provider, Notification, AuditLog
)
# from django_countries.serializers import CountryFieldMixin # Descomentar si se usa

User = get_user_model()

# --- Helper Serializer para User (Reutilizable) ---
class BasicUserSerializer(serializers.ModelSerializer):
    """Serializer básico para mostrar información del usuario."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_active']
        read_only_fields = fields

    def get_full_name(self, obj):
        name = obj.get_full_name()
        return name if name else obj.username # Devolver username si no hay nombre completo

# ---------------------- Autenticación ----------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed("El usuario no existe.", code="user_not_found")

        if not user.check_password(password):
            raise AuthenticationFailed("Contraseña incorrecta.", code="invalid_credentials")

        if not user.is_active:
            raise AuthenticationFailed("Tu cuenta está inactiva.", code="user_inactive")

        data = super().validate(attrs)

        role = 'employee' if hasattr(user, 'employee_profile') else 'customer'
        user_data = BasicUserSerializer(user).data
        user_data['role'] = role

        data.update({'user': user_data})
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = 'employee' if hasattr(user, 'employee_profile') else 'customer'
        token['username'] = user.username
        return token

# ---------------------- Formularios ----------------------
class FormQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormQuestion
        fields = ['id', 'question_text', 'order', 'required']

class FormSerializer(serializers.ModelSerializer):
    questions = FormQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Form
        fields = ['id', 'name', 'description', 'created_at', 'questions']
        read_only_fields = ['created_at']

class FormResponseSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.__str__', read_only=True)
    form_name = serializers.CharField(source='form.name', read_only=True)
    question_text = serializers.CharField(source='question.question_text', read_only=True)

    class Meta:
        model = FormResponse
        fields = [
            'id', 'customer', 'customer_name', 'form', 'form_name',
            'question', 'question_text', 'text', 'created_at'
        ]
        read_only_fields = [
            'customer', 'created_at', 'customer_name', 'form_name', 'question_text'
        ]
        extra_kwargs = {
            'form': {'write_only': True, 'required': True, 'queryset': Form.objects.all()}, # Añadir queryset
            'question': {'write_only': True, 'required': True, 'queryset': FormQuestion.objects.all()}, # Añadir queryset
        }

class FormResponseBulkItemSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=FormQuestion.objects.all())
    text = serializers.CharField(max_length=5000, allow_blank=True) # Permitir respuestas vacías

class FormResponseBulkCreateSerializer(serializers.Serializer):
    form = serializers.PrimaryKeyRelatedField(queryset=Form.objects.all())
    responses = FormResponseBulkItemSerializer(many=True)

    def validate(self, data):
        """Valida que todas las preguntas pertenezcan al formulario especificado."""
        form = data['form']
        responses = data['responses']
        question_ids_in_form = set(form.questions.values_list('id', flat=True))

        for response_item in responses:
            question = response_item['question']
            if question.form != form: # Más directo que comprobar el ID
                raise ValidationError(f"La pregunta '{question.question_text}' no pertenece al formulario '{form.name}'.")
        return data


# ---------------------- Usuarios y Perfiles ----------------------
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirmar Contraseña")

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise ValidationError({"password": "Las contraseñas no coinciden."})
        # No necesitamos validar email único aquí, el modelo ya lo hace
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2') # No guardar password2
        user = User.objects.create_user(**validated_data)
        return user

class JobPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = '__all__'


class CustomerSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)
    country_display = serializers.CharField(source='get_country_display', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'user', 'phone', 'address', 'date_of_birth', 'country', 'country_display',
            'company_name', 'created_at', 'preferred_contact_method', 'brand_guidelines'
        ]
        read_only_fields = ['created_at', 'user', 'country_display']


class CustomerCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer()
    # Permitir pasar país como código
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Customer
        fields = [
            'user', 'phone', 'address', 'date_of_birth', 'country', 'company_name',
            'preferred_contact_method', 'brand_guidelines'
        ]

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        # Validar email único antes de crear usuario
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': ['Ya existe un usuario con este email.']}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': ['Ya existe un usuario con este nombre de usuario.']}})

        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        customer_data = validated_data
        # Manejar country (django-countries lo asigna directamente si pasas el código)
        # customer_data['country'] = validated_data.get('country') # Ya está en validated_data

        customer, created = Customer.objects.update_or_create(
            user=user, defaults=customer_data
        )
        return customer


class EmployeeSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)
    position = JobPositionSerializer(read_only=True)
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', write_only=True, required=False, allow_null=True
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'is_active', 'hire_date', 'address', 'salary',
            'position', 'position_id'
        ]
        read_only_fields = ['hire_date', 'user', 'is_active', 'position']


class EmployeeCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer()
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', required=False, allow_null=True
    )

    class Meta:
        model = Employee
        fields = ['user', 'position_id', 'address', 'salary', 'hire_date']
        extra_kwargs = {
            'hire_date': {'required': False}
        }

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        # Validar unicidad
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': ['Ya existe un usuario con este email.']}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': ['Ya existe un usuario con este nombre de usuario.']}})

        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        user.is_staff = True # Marcar como staff
        user.save(update_fields=['is_staff'])

        employee, created = Employee.objects.update_or_create(
            user=user, defaults=validated_data
        )
        return employee

# ---------------------- Categorías, Servicios y Precios ----------------------
class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__'

class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Price
        fields = ['id', 'service', 'amount', 'currency', 'effective_date']
        extra_kwargs = {
            'service': {'write_only': True, 'required': False}
        }

class ServiceFeatureSerializer(serializers.ModelSerializer):
    feature_type_display = serializers.CharField(source='get_feature_type_display', read_only=True)

    class Meta:
        model = ServiceFeature
        fields = ['id', 'service', 'feature_type', 'feature_type_display', 'description']
        read_only_fields = ['feature_type_display']
        extra_kwargs = {
            'service': {'write_only': True, 'required': False}
        }


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=ServiceCategory.objects.all(), write_only=True)
    campaign_name = serializers.CharField(source='campaign.campaign_name', read_only=True, allow_null=True)
    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all(), write_only=True, required=False, allow_null=True)
    features = ServiceFeatureSerializer(many=True, read_only=True)
    price_history = PriceSerializer(many=True, read_only=True)
    current_eur_price = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            'code', 'name', 'category', 'category_name', 'campaign', 'campaign_name',
            'is_active', 'ventulab', 'is_package', 'is_subscription',
            'audience', 'detailed_description', 'problem_solved',
            'features', 'price_history', 'current_eur_price'
        ]
        read_only_fields = ['category_name', 'campaign_name', 'features', 'price_history', 'current_eur_price']

    def get_current_eur_price(self, obj):
        price = obj.get_current_price(currency='EUR')
        return price if price is not None else None # Devolver None si no hay precio


# ---------------------- Gestión de Pedidos ----------------------
class OrderServiceCreateSerializer(serializers.ModelSerializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    # Precio puede ser opcional si se calcula automáticamente
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'quantity', 'price', 'note'] # ID es read-only por defecto
        extra_kwargs = {
            # No es necesario definir price aquí si se maneja en save del modelo/serializer
        }

    def validate_price(self, value):
        # Validar que el precio no sea negativo si se proporciona
        if value is not None and value < 0:
             raise ValidationError("El precio no puede ser negativo.")
        return value


class OrderServiceReadSerializer(serializers.ModelSerializer): # No heredar de Create si los campos difieren mucho
    service = ServiceSerializer(read_only=True) # Mostrar detalles completos
    price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Asegurar read_only

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'quantity', 'price', 'note']
        read_only_fields = fields


class EmployeeBasicSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'user']


class ProviderBasicSerializer(serializers.ModelSerializer):
     class Meta:
        model = Provider
        fields = ['id', 'name']


class DeliverableSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    assigned_employee_info = EmployeeBasicSerializer(source='assigned_employee', read_only=True)
    assigned_provider_info = ProviderBasicSerializer(source='assigned_provider', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(user__is_active=True), write_only=True, required=False, allow_null=True
    )
    assigned_provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.filter(is_active=True), write_only=True, required=False, allow_null=True
    )
    file_url = serializers.SerializerMethodField()


    class Meta:
        model = Deliverable
        fields = [
            'id', 'order_id', 'description', 'version', 'file', 'file_url', 'status', 'status_display',
            'due_date', 'assigned_employee', 'assigned_employee_info',
            'assigned_provider', 'assigned_provider_info', 'feedback_notes', 'created_at'
        ]
        read_only_fields = [
            'order_id', 'version', 'created_at', 'assigned_employee_info',
            'assigned_provider_info', 'status_display', 'file_url'
        ]

    def get_file_url(self, obj):
         # Devolver None si no hay archivo, o la URL si existe
         return obj.file.url if obj.file else None


class OrderReadSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    employee = EmployeeBasicSerializer(read_only=True)
    services = OrderServiceReadSerializer(many=True, read_only=True)
    deliverables = DeliverableSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # invoices = InvoiceBasicSerializer(many=True, read_only=True) # Descomentar si se necesita

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'status_display', 'date_received',
            'date_required', 'payment_due_date', 'note', 'priority',
            'completed_at', 'total_amount', 'services', 'deliverables' #, 'invoices'
        ]
        read_only_fields = fields


class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.filter(user__is_active=True), required=False, allow_null=True)
    services = OrderServiceCreateSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'date_required',
            'payment_due_date', 'note', 'priority', 'services'
        ]
        # `total_amount` y `completed_at` son gestionados por el modelo/señales

    def _create_or_update_services(self, order, services_data):
        """Helper para manejar la creación/actualización de servicios."""
        # Opción simple: Borrar existentes y crear nuevos
        order.services.all().delete()
        services_to_create = []
        for service_data in services_data:
            # Autocompletar precio si no se proporciona
            if 'price' not in service_data or service_data['price'] is None:
                service_obj = service_data.get('service')
                if service_obj:
                    base_price = service_obj.get_current_price(currency='EUR') # Asume moneda principal
                    service_data['price'] = base_price if base_price is not None else Decimal('0.00')
                else: # Si service no se pudo obtener (raro si pasó validación)
                     service_data['price'] = Decimal('0.00')

            services_to_create.append(OrderService(order=order, **service_data))
        if services_to_create:
            OrderService.objects.bulk_create(services_to_create)
        # La señal post_save de OrderService llamará a order.update_total_amount()

    @transaction.atomic
    def create(self, validated_data):
        services_data = validated_data.pop('services', [])
        order = Order.objects.create(**validated_data)
        self._create_or_update_services(order, services_data)
        # order.update_total_amount() # No es necesario si la señal funciona bien
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        services_data = validated_data.pop('services', None)

        # Actualizar campos de la orden principal (DRF maneja esto)
        instance = super().update(instance, validated_data)

        if services_data is not None:
            self._create_or_update_services(instance, services_data)
            # instance.update_total_amount() # No es necesario si la señal funciona

        return instance

# ---------------------- Gestión de Pagos ----------------------
class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'

class TransactionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        fields = '__all__'

class InvoiceBasicSerializer(serializers.ModelSerializer):
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
     total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Incluir total

     class Meta:
         model = Invoice
         fields = ['id', 'invoice_number', 'date', 'due_date', 'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due']
         read_only_fields = fields


class PaymentReadSerializer(serializers.ModelSerializer):
     method_name = serializers.CharField(source='method.name', read_only=True)
     transaction_type_name = serializers.CharField(source='transaction_type.name', read_only=True)
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

     class Meta:
         model = Payment
         fields = [
             'id', 'invoice', 'invoice_number', 'method', 'method_name', 'transaction_type',
             'transaction_type_name', 'date', 'amount', 'currency', 'status', 'status_display',
             'transaction_id', 'notes'
        ]
         # Quitar read_only_fields, Meta hereda bien, pero especificar qué NO es read_only si es necesario
         # read_only_fields = [...]


class PaymentCreateSerializer(serializers.ModelSerializer):
     # Filtrar facturas que no estén en estado final
     invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.exclude(status__in=Invoice.FINAL_STATUSES))
     method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.filter(is_active=True))
     transaction_type = serializers.PrimaryKeyRelatedField(queryset=TransactionType.objects.all())

     class Meta:
         model = Payment
         fields = [
             'id', 'invoice', 'method', 'transaction_type', 'amount',
             'currency', 'status', 'transaction_id', 'notes'
         ]
         read_only_fields = ['id'] # ID es lo único que no se debe escribir


class InvoiceSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.CharField(source='order.customer.__str__', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payments = PaymentReadSerializer(many=True, read_only=True)
    # Permitir asignar Order por ID al crear
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), write_only=True, required=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'order', 'order_id', 'customer_name', 'invoice_number', 'date', 'due_date',
            'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due',
            'notes', 'payments'
        ]
        read_only_fields = [
            'id', 'order_id', 'customer_name', 'invoice_number', # invoice_number se autogenera
            'paid_amount', 'status_display', 'total_amount', 'balance_due', 'payments'
        ]
        # 'date' usa default, 'status' puede cambiar por lógica interna o permitirse edición limitada
        # 'due_date', 'notes' son editables


# ---------------------- Campañas ----------------------
class CampaignServiceSerializer(serializers.ModelSerializer):
    # Mostrar nombre y código de servicio, permitir asignar por ID
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_code = serializers.CharField(source='service.code', read_only=True)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), write_only=True)

    class Meta:
        model = CampaignService
        fields = ['id', 'campaign', 'service', 'service_code', 'service_name', 'discount_percentage', 'additional_details']
        read_only_fields = ['id', 'campaign', 'service_code', 'service_name']


class CampaignSerializer(serializers.ModelSerializer):
    included_services = CampaignServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = [
            'campaign_code', 'campaign_name', 'start_date', 'end_date',
            'description', 'target_audience', 'budget', 'is_active', 'included_services'
        ]
        read_only_fields = ['included_services']

    # Considerar add/remove de servicios con drf-writable-nested o acciones personalizadas

# ---------------------- Proveedores y Colaboradores ----------------------
class ProviderSerializer(serializers.ModelSerializer):
    # Mostrar solo códigos/nombres de servicios provistos, permitir asignar por ID
    services_provided_details = ServiceSerializer(source='services_provided', many=True, read_only=True) # Mostrar más detalles si se quiere
    services_provided = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), many=True, write_only=True, required=False
    )

    class Meta:
        model = Provider
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'rating',
            'is_active', 'notes', 'services_provided', 'services_provided_details' # Cambiado nombre para claridad
        ]
        read_only_fields = ['id', 'services_provided_details']

# ---------------------- Mejoras Adicionales ----------------------
class NotificationSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'read', 'created_at', 'link']
        read_only_fields = ['id', 'user', 'created_at', 'link'] # Permitir actualizar 'read'

class AuditLogSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'action', 'timestamp', 'details']
        read_only_fields = fields # Solo lectura