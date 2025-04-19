# api/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from decimal import Decimal
from django.db import transaction
from django.utils.translation import gettext_lazy as _ # Importación necesaria para _()
import logging # Importar logging

# Import todos los modelos necesarios, incluyendo los nuevos
from .models import (
    Form, FormQuestion, FormResponse, Customer, JobPosition, Employee,
    Order, ServiceCategory, Campaign, Service, ServiceFeature, Price,
    OrderService, Deliverable, TransactionType, PaymentMethod, Invoice,
    Payment, CampaignService, Provider, Notification, AuditLog,
    # --- NUEVOS MODELOS ---
    UserRole, UserProfile, UserRoleAssignment
)
# Importar constantes de roles
try:
    from .roles import Roles
except ImportError:
    class Roles: # Placeholder si el archivo no existe
        DRAGON = 'dragon'
        ADMIN = 'admin'
        MARKETING = 'mktg'
        # Añade otros roles como placeholders si es necesario
    print("ADVERTENCIA: api/roles.py no encontrado. Usando roles placeholder.")

logger = logging.getLogger(__name__) # Definir logger
User = get_user_model()

# --- Helper Serializer para User (ACTUALIZADO con Roles) ---
class BasicUserSerializer(serializers.ModelSerializer):
    """Serializer básico para mostrar información del usuario, incluyendo roles."""
    full_name = serializers.SerializerMethodField(read_only=True)
    # --- NUEVOS CAMPOS DE ROLES ---
    primary_role = serializers.CharField(source='primary_role_name', read_only=True, allow_null=True) # Permitir null si no asignado
    secondary_roles = serializers.ListField(source='get_secondary_active_role_names', read_only=True, child=serializers.CharField())
    all_roles = serializers.ListField(source='get_all_active_role_names', read_only=True, child=serializers.CharField())
    is_dragon_user = serializers.BooleanField(source='is_dragon', read_only=True)

    class Meta:
        model = User
        # Añadir nuevos campos a la lista
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff',
            'primary_role', 'secondary_roles', 'all_roles', 'is_dragon_user'
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        name = obj.get_full_name()
        return name if name else obj.username

# ---------------------- Autenticación (ACTUALIZADO) ----------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        try:
            # Optimizar consulta incluyendo perfil y roles
            user = User.objects.select_related('profile__primary_role').prefetch_related(
                'secondary_role_assignments__role'
            ).get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed(_("El usuario no existe."), code="user_not_found")

        if not user.check_password(password):
            raise AuthenticationFailed(_("Contraseña incorrecta."), code="invalid_credentials")

        if not user.is_active:
            raise AuthenticationFailed(_("Tu cuenta está inactiva."), code="user_inactive")

        data = super().validate(attrs) # Obtiene access y refresh tokens

        # Serializa el usuario con el serializer actualizado que incluye roles
        user_data = BasicUserSerializer(user).data
        data.update({'user': user_data})
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Añadir roles al payload del token JWT
        token['roles'] = user.get_all_active_role_names # Lista completa de nombres internos
        token['primary_role'] = user.primary_role_name # Rol principal
        token['username'] = user.username
        token['is_dragon'] = user.is_dragon()
        return token

# ---------------------- Formularios (Sin cambios relacionados a roles) ----------------------
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
        fields = ['id', 'customer', 'customer_name', 'form', 'form_name','question', 'question_text', 'text', 'created_at']
        read_only_fields = ['customer', 'created_at', 'customer_name', 'form_name', 'question_text']
        extra_kwargs = {
            'form': {'write_only': True, 'required': True, 'queryset': Form.objects.all()},
            'question': {'write_only': True, 'required': True, 'queryset': FormQuestion.objects.all()}
        }

class FormResponseBulkItemSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(queryset=FormQuestion.objects.all())
    text = serializers.CharField(max_length=5000, allow_blank=True)

class FormResponseBulkCreateSerializer(serializers.Serializer):
    form = serializers.PrimaryKeyRelatedField(queryset=Form.objects.all())
    responses = FormResponseBulkItemSerializer(many=True)

    def validate(self, data):
        form = data['form']
        responses = data['responses']
        for response_item in responses:
            question = response_item['question']
            if question.form_id != form.id:
                raise ValidationError(f"La pregunta ID {question.id} ('{question.question_text[:30]}...') no pertenece al formulario '{form.name}'.")
        # El return data está correctamente indentado aquí
        return data
    # No debe haber un 'return data' fuera del método validate

# ---------------------- Usuarios y Perfiles (ACTUALIZADO) ----------------------

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label="Confirmar Contraseña")
    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {'first_name': {'required': False}, 'last_name': {'required': False}, 'email': {'required': True}}

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise ValidationError({"password": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

# Serializer para UserRole
class UserRoleSerializer(serializers.ModelSerializer):
     class Meta:
        model = UserRole
        fields = ['id', 'name', 'display_name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

# Serializer para UserRoleAssignment
class UserRoleAssignmentSerializer(serializers.ModelSerializer):
     user_info = BasicUserSerializer(source='user', read_only=True)
     role_info = UserRoleSerializer(source='role', read_only=True)
     user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
     role = serializers.PrimaryKeyRelatedField(queryset=UserRole.objects.filter(is_active=True), write_only=True)

     class Meta:
         model = UserRoleAssignment
         fields = ['id', 'user', 'user_info', 'role', 'role_info', 'is_active', 'assigned_at', 'updated_at']
         read_only_fields = ['id', 'user_info', 'role_info', 'assigned_at', 'updated_at']

class JobPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = '__all__'

class CustomerSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Incluye roles
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    class Meta:
        model = Customer
        fields = ['id', 'user', 'phone', 'address', 'date_of_birth', 'country', 'country_display', 'company_name', 'created_at', 'preferred_contact_method', 'brand_guidelines']
        read_only_fields = ['created_at', 'user', 'country_display']

class CustomerCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer()
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True,
        help_text=_("ID del rol principal obligatorio para este cliente.")
    )
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Customer
        fields = ['user', 'primary_role', 'phone', 'address', 'date_of_birth', 'country', 'company_name', 'preferred_contact_method', 'brand_guidelines']

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        customer_specific_data = validated_data

        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        user.is_staff = False # Clientes no son staff
        user.save(update_fields=['is_staff'])

        try:
            user_profile = UserProfile.objects.get(user=user) # La señal ya lo creó
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean()
        except UserProfile.DoesNotExist:
            logger.error(f"Error crítico: No se encontró UserProfile para el usuario recién creado {user.username}")
            # Considera si quieres crear el UserProfile aquí como fallback, aunque la señal debería funcionar
            # UserProfile.objects.create(user=user, primary_role=primary_role_obj)
            raise ValidationError(_("No se pudo inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a {user.username}: {e}")
             user.delete() # Rollback
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', [_('Error asignando rol primario.')])})

        customer, created = Customer.objects.update_or_create(
            user=user, defaults=customer_specific_data
        )
        return customer

class EmployeeSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Incluye roles
    position = JobPositionSerializer(read_only=True)
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', write_only=True, required=False, allow_null=True
    )
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'user', 'is_active', 'hire_date', 'address', 'salary', 'position', 'position_id']
        read_only_fields = ['hire_date', 'user', 'is_active', 'position']

class EmployeeCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer()
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True,
        help_text=_("ID del rol principal obligatorio para este empleado.")
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', required=False, allow_null=True
    )

    class Meta:
        model = Employee
        fields = ['user', 'primary_role', 'position_id', 'address', 'salary', 'hire_date']
        extra_kwargs = { 'hire_date': {'required': False} }

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        employee_specific_data = validated_data

        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()
        user.is_staff = True # Empleados son staff
        user.save(update_fields=['is_staff'])

        try:
            user_profile = UserProfile.objects.get(user=user) # Señal lo crea
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean()
        except UserProfile.DoesNotExist:
            logger.error(f"Error crítico: No se encontró UserProfile para el empleado recién creado {user.username}")
            # Considera crearlo aquí como fallback
            raise ValidationError(_("No se pudo inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a {user.username}: {e}")
             user.delete() # Rollback
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', [_('Error asignando rol primario.')])})

        employee, created = Employee.objects.update_or_create(
            user=user, defaults=employee_specific_data
        )
        return employee


# --- RESTO DE SERIALIZERS (Sin cambios directos necesarios por Roles) ---
# (Revisados brevemente para asegurar que no haya errores obvios)

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta: model = ServiceCategory; fields = '__all__'
class PriceSerializer(serializers.ModelSerializer):
    class Meta: model = Price; fields = ['id', 'service', 'amount', 'currency', 'effective_date']; extra_kwargs = {'service': {'write_only': True, 'required': False}}
class ServiceFeatureSerializer(serializers.ModelSerializer):
    feature_type_display = serializers.CharField(source='get_feature_type_display', read_only=True)
    class Meta: model = ServiceFeature; fields = ['id', 'service', 'feature_type', 'feature_type_display', 'description']; read_only_fields = ['feature_type_display']; extra_kwargs = {'service': {'write_only': True, 'required': False}}
class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True); category = serializers.PrimaryKeyRelatedField(queryset=ServiceCategory.objects.all(), write_only=True); campaign_name = serializers.CharField(source='campaign.campaign_name', read_only=True, allow_null=True); campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all(), write_only=True, required=False, allow_null=True); features = ServiceFeatureSerializer(many=True, read_only=True); price_history = PriceSerializer(many=True, read_only=True); current_eur_price = serializers.SerializerMethodField()
    class Meta: model = Service; fields = ['code', 'name', 'category', 'category_name', 'campaign', 'campaign_name', 'is_active', 'ventulab', 'is_package', 'is_subscription', 'audience', 'detailed_description', 'problem_solved', 'features', 'price_history', 'current_eur_price']; read_only_fields = ['category_name', 'campaign_name', 'features', 'price_history', 'current_eur_price']
    def get_current_eur_price(self, obj): price = obj.get_current_price(currency='EUR'); return price if price is not None else None

class OrderServiceCreateSerializer(serializers.ModelSerializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True)); price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    class Meta: model = OrderService; fields = ['id', 'service', 'quantity', 'price', 'note']
    def validate_price(self, value):
        if value is not None and value < 0:
            raise ValidationError("El precio no puede ser negativo.")
        return value
class OrderServiceReadSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True); price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta: model = OrderService; fields = ['id', 'service', 'quantity', 'price', 'note']; read_only_fields = fields

class EmployeeBasicSerializer(serializers.ModelSerializer): # Ya actualizado para usar BasicUserSerializer
    user = BasicUserSerializer(read_only=True)
    class Meta: model = Employee; fields = ['id', 'user']

class ProviderBasicSerializer(serializers.ModelSerializer):
     class Meta: model = Provider; fields = ['id', 'name']

class DeliverableSerializer(serializers.ModelSerializer):
    assigned_employee_info = EmployeeBasicSerializer(source='assigned_employee', read_only=True) # Usa serializer actualizado
    order_id = serializers.IntegerField(source='order.id', read_only=True); assigned_provider_info = ProviderBasicSerializer(source='assigned_provider', read_only=True); status_display = serializers.CharField(source='get_status_display', read_only=True); assigned_employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.filter(user__is_active=True), write_only=True, required=False, allow_null=True); assigned_provider = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.filter(is_active=True), write_only=True, required=False, allow_null=True); file_url = serializers.SerializerMethodField()
    class Meta: model = Deliverable; fields = ['id', 'order_id', 'description', 'version', 'file', 'file_url', 'status', 'status_display', 'due_date', 'assigned_employee', 'assigned_employee_info', 'assigned_provider', 'assigned_provider_info', 'feedback_notes', 'created_at']; read_only_fields = ['order_id', 'version', 'created_at', 'assigned_employee_info', 'assigned_provider_info', 'status_display', 'file_url']
    def get_file_url(self, obj): return obj.file.url if obj.file else None

class OrderReadSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True) # Usa serializer actualizado
    employee = EmployeeBasicSerializer(read_only=True) # Usa serializer actualizado
    services = OrderServiceReadSerializer(many=True, read_only=True); deliverables = DeliverableSerializer(many=True, read_only=True); status_display = serializers.CharField(source='get_status_display', read_only=True)
    class Meta: model = Order; fields = ['id', 'customer', 'employee', 'status', 'status_display', 'date_received', 'date_required', 'payment_due_date', 'note', 'priority', 'completed_at', 'total_amount', 'services', 'deliverables']; read_only_fields = fields

class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all()); employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.filter(user__is_active=True), required=False, allow_null=True); services = OrderServiceCreateSerializer(many=True, required=False)
    class Meta: model = Order; fields = ['id', 'customer', 'employee', 'status', 'date_required', 'payment_due_date', 'note', 'priority', 'services']
    def _create_or_update_services(self, order, services_data):
        order.services.all().delete(); services_to_create = []
        for service_data in services_data:
            if 'price' not in service_data or service_data['price'] is None: service_obj = service_data.get('service'); base_price = service_obj.get_current_price(currency='EUR') if service_obj else None; service_data['price'] = base_price if base_price is not None else Decimal('0.00')
            services_to_create.append(OrderService(order=order, **service_data))
        if services_to_create: OrderService.objects.bulk_create(services_to_create)
    @transaction.atomic
    def create(self, validated_data): services_data = validated_data.pop('services', []); order = Order.objects.create(**validated_data); self._create_or_update_services(order, services_data); return order
    @transaction.atomic
    def update(self, instance, validated_data):
        services_data = validated_data.pop('services', None)
        instance = super().update(instance, validated_data)
        if services_data is not None:
            self._create_or_update_services(instance, services_data)
        return instance

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta: model = PaymentMethod; fields = '__all__'
class TransactionTypeSerializer(serializers.ModelSerializer):
    class Meta: model = TransactionType; fields = '__all__'
class InvoiceBasicSerializer(serializers.ModelSerializer):
     status_display = serializers.CharField(source='get_status_display', read_only=True); balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True); total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
     class Meta: model = Invoice; fields = ['id', 'invoice_number', 'date', 'due_date', 'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due']; read_only_fields = fields
class PaymentReadSerializer(serializers.ModelSerializer):
     method_name = serializers.CharField(source='method.name', read_only=True); transaction_type_name = serializers.CharField(source='transaction_type.name', read_only=True); status_display = serializers.CharField(source='get_status_display', read_only=True); invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
     class Meta: model = Payment; fields = ['id', 'invoice', 'invoice_number', 'method', 'method_name', 'transaction_type', 'transaction_type_name', 'date', 'amount', 'currency', 'status', 'status_display', 'transaction_id', 'notes']
class PaymentCreateSerializer(serializers.ModelSerializer):
     invoice = serializers.PrimaryKeyRelatedField(queryset=Invoice.objects.exclude(status__in=Invoice.FINAL_STATUSES)); method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.filter(is_active=True)); transaction_type = serializers.PrimaryKeyRelatedField(queryset=TransactionType.objects.all())
     class Meta: model = Payment; fields = ['id', 'invoice', 'method', 'transaction_type', 'amount', 'currency', 'status', 'transaction_id', 'notes']; read_only_fields = ['id']
class InvoiceSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True); customer_name = serializers.CharField(source='order.customer.__str__', read_only=True); status_display = serializers.CharField(source='get_status_display', read_only=True); total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True); balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True); payments = PaymentReadSerializer(many=True, read_only=True); order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), write_only=True, required=True)
    class Meta: model = Invoice; fields = ['id', 'order', 'order_id', 'customer_name', 'invoice_number', 'date', 'due_date', 'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due', 'notes', 'payments']; read_only_fields = ['id', 'order_id', 'customer_name', 'invoice_number', 'paid_amount', 'status_display', 'total_amount', 'balance_due', 'payments']

class CampaignServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True); service_code = serializers.CharField(source='service.code', read_only=True); service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), write_only=True)
    class Meta: model = CampaignService; fields = ['id', 'campaign', 'service', 'service_code', 'service_name', 'discount_percentage', 'additional_details']; read_only_fields = ['id', 'campaign', 'service_code', 'service_name']
class CampaignSerializer(serializers.ModelSerializer):
    included_services = CampaignServiceSerializer(many=True, read_only=True)
    class Meta: model = Campaign; fields = ['campaign_code', 'campaign_name', 'start_date', 'end_date', 'description', 'target_audience', 'budget', 'is_active', 'included_services']; read_only_fields = ['included_services']

class ProviderSerializer(serializers.ModelSerializer):
    services_provided_details = ServiceSerializer(source='services_provided', many=True, read_only=True); services_provided = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True, write_only=True, required=False)
    class Meta: model = Provider; fields = ['id', 'name', 'contact_person', 'email', 'phone', 'rating', 'is_active', 'notes', 'services_provided', 'services_provided_details']; read_only_fields = ['id', 'services_provided_details']

class NotificationSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Usa serializer actualizado
    class Meta: model = Notification; fields = ['id', 'user', 'message', 'read', 'created_at', 'link']; read_only_fields = ['id', 'user', 'created_at', 'link']
class AuditLogSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Usa serializer actualizado
    class Meta: model = AuditLog; fields = ['id', 'user', 'action', 'timestamp', 'details']; read_only_fields = fields