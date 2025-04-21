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

# --- Helper Serializer para User (CORREGIDO Y ACTUALIZADO) ---
class BasicUserSerializer(serializers.ModelSerializer):
    """
    Serializer básico para mostrar información del usuario, incluyendo roles
    y el nombre del puesto de trabajo si es un empleado.
    """
    # --- Fields definidos a nivel de clase (SerializerMethodField, etc.) ---
    full_name = serializers.SerializerMethodField(read_only=True)
    primary_role = serializers.CharField(source='primary_role_name', read_only=True, allow_null=True) # Nombre interno del rol
    primary_role_display_name = serializers.SerializerMethodField(read_only=True, allow_null=True) # Nombre legible del ROL
    secondary_roles = serializers.ListField(source='get_secondary_active_role_names', read_only=True, child=serializers.CharField())
    all_roles = serializers.ListField(source='get_all_active_role_names', read_only=True, child=serializers.CharField())
    is_dragon_user = serializers.BooleanField(source='is_dragon', read_only=True)
    job_position_name = serializers.SerializerMethodField(read_only=True, allow_null=True) # Nombre del PUESTO

    class Meta:
        model = User
        # Listar TODOS los campos que quieres que se muestren en la salida JSON
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'is_staff',
            'primary_role',              # Nombre interno rol
            'primary_role_display_name', # Nombre legible rol
            'secondary_roles',           # Nombres internos roles secundarios
            'all_roles',                 # Todos los nombres internos de roles activos
            'is_dragon_user',            # Flag Dragon
            'job_position_name',         # Nombre del puesto de trabajo
        ]
        # --- ¡CORRECCIÓN IMPORTANTE! ---
        # NO incluir SerializerMethodFields en read_only_fields.
        # Ya son inherentemente read-only.
        # Para este serializer informativo, no necesitamos especificar read_only_fields explícitamente aquí,
        # ya que todos los campos de SerializerMethodField y CharField(read_only=True) ya lo son.
        # Los campos directos del modelo (como 'username', 'email') serán read-only por defecto
        # si no se configuran para escritura en otro lugar.
        # read_only_fields = ['id', 'username', ...] # <-- Solo si necesitas especificar campos de *modelo* como read-only

    def get_full_name(self, obj):
        """Obtiene el nombre completo o el username."""
        name = obj.get_full_name()
        return name if name else obj.username

    def get_primary_role_display_name(self, obj):
        """Devuelve el nombre legible del rol primario."""
        # Intenta usar la propiedad cachead@ 'primary_role' añadida al modelo User
        primary_role_instance = getattr(obj, 'primary_role', None) # Usa getattr para seguridad
        if primary_role_instance and hasattr(primary_role_instance, 'display_name'):
            return primary_role_instance.display_name
        # Fallback: Intenta cargar explícitamente si no estaba precargado
        # (Menos eficiente, pero más robusto si falta select_related)
        try:
            profile = getattr(obj, 'profile', None) or obj.profile # Accede o fuerza carga
            if profile and profile.primary_role:
                return profile.primary_role.display_name
        except UserProfile.DoesNotExist:
             logger.warning(f"Perfil no encontrado para usuario {obj.username} en get_primary_role_display_name.")
        except Exception as e:
            logger.error(f"Error obteniendo display_name de ROL para usuario {obj.username}: {e}")

        return None # Devuelve None si no se encuentra el nombre legible del rol

    def get_job_position_name(self, obj):
        """
        Devuelve el nombre del JobPosition si el usuario es un empleado
        y tiene un puesto asignado. Requiere que 'employee_profile__position'
        se cargue eficientemente (e.g., con select_related).
        """
        try:
            # Accede usando getattr para más seguridad contra AttributeError
            employee_profile = getattr(obj, 'employee_profile', None)
            position = getattr(employee_profile, 'position', None)
            if position and hasattr(position, 'name'):
                return position.name
        except Employee.DoesNotExist:
            # No es un error si el usuario no es un empleado
            pass
        except Exception as e:
            # Loggear otros errores inesperados
            logger.error(f"Error inesperado obteniendo job_position_name para {obj.username}: {e}", exc_info=True)

        return None # Devuelve None si no es empleado, no tiene puesto, o hubo un error

# ---------------------- Autenticación (ACTUALIZADO con optimización) ----------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        try:
            # --- Optimización CRÍTICA para cargar datos relacionados eficientemente ---
            user = User.objects.select_related(
                'profile__primary_role',    # Para rol primario
                'employee_profile__position' # Para puesto de trabajo
            ).prefetch_related(
                'secondary_role_assignments__role' # Para roles secundarios
            ).get(username=username)
            # -------------------------------------------------------------------------
        except User.DoesNotExist:
            raise AuthenticationFailed(_("El usuario no existe."), code="user_not_found")

        if not user.check_password(password):
            raise AuthenticationFailed(_("Contraseña incorrecta."), code="invalid_credentials")

        if not user.is_active:
            raise AuthenticationFailed(_("Tu cuenta está inactiva."), code="user_inactive")

        data = super().validate(attrs) # Obtiene access y refresh tokens

        # Serializa el usuario. 'user' ya tiene los datos relacionados precargados.
        user_data = BasicUserSerializer(user).data
        data.update({'user': user_data})
        return data

    @classmethod
    def get_token(cls, user):
        # El payload del token JWT generalmente solo necesita identificadores/roles internos
        token = super().get_token(user)
        token['roles'] = user.get_all_active_role_names # Lista completa de nombres internos
        token['primary_role'] = user.primary_role_name # Rol principal (nombre interno)
        token['username'] = user.username
        token['is_dragon'] = user.is_dragon() # Usar el método is_dragon()
        return token

# ---------------------- Formularios (Sin cambios necesarios) ----------------------
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
        read_only_fields = ['id', 'created_at', 'customer_name', 'form_name', 'question_text'] # Añadir 'id'
        # 'customer' no necesita estar en read_only_fields si se asigna automáticamente
        extra_kwargs = {
            'customer': {'write_only': True, 'required': False, 'allow_null': True}, # Permitir que se asigne en la vista
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
        responses_data = data['responses'] # Renombrar para claridad
        form_question_ids = set(form.questions.values_list('id', flat=True))

        for response_item in responses_data:
            question = response_item['question']
            if question.id not in form_question_ids:
                raise ValidationError(f"La pregunta ID {question.id} ('{question.question_text[:30]}...') no pertenece al formulario '{form.name}'.")
            # Validar si la pregunta es requerida y el texto está vacío (opcional aquí, o en el modelo/vista)
            # if question.required and not response_item['text']:
            #    raise ValidationError({f"responses.{question.id}": _("Esta pregunta es requerida.")})
        return data


# ---------------------- Usuarios y Perfiles (Sin cambios necesarios) ----------------------

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
        # Validar email único aquí también si no se hace en otro lugar
        email = attrs.get('email')
        if email and User.objects.filter(email=email).exists():
             raise ValidationError({'email': _('Ya existe un usuario con este email.')})
        # Validar username único
        username = attrs.get('username')
        if username and User.objects.filter(username=username).exists():
             raise ValidationError({'username': _('Ya existe un usuario con este nombre de usuario.')})
        return attrs

    def create(self, validated_data):
        # password2 ya se usó en validate
        validated_data.pop('password2', None)
        # Asegurarnos de que el usuario se cree correctamente
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'], # create_user hashea la contraseña
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )
        # El is_staff se asigna en Customer/Employee create
        return user

# Serializer para UserRole
class UserRoleSerializer(serializers.ModelSerializer):
     class Meta:
        model = UserRole
        fields = ['id', 'name', 'display_name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

# Serializer para UserRoleAssignment
class UserRoleAssignmentSerializer(serializers.ModelSerializer):
     # Mostrar info básica del usuario y rol asignado (usando los serializers ya definidos)
     user_info = BasicUserSerializer(source='user', read_only=True)
     role_info = UserRoleSerializer(source='role', read_only=True)
     # Campos para crear/actualizar la asignación
     user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
     role = serializers.PrimaryKeyRelatedField(queryset=UserRole.objects.filter(is_active=True), write_only=True)

     class Meta:
         model = UserRoleAssignment
         fields = ['id', 'user', 'user_info', 'role', 'role_info', 'is_active', 'assigned_at', 'updated_at']
         read_only_fields = ['id', 'user_info', 'role_info', 'assigned_at', 'updated_at']

class JobPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = '__all__' # ['id', 'name', 'description', 'permissions']

class CustomerSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Muestra info del usuario con roles/puesto
    country_display = serializers.CharField(source='get_country_display', read_only=True)
    class Meta:
        model = Customer
        fields = [
            'id', 'user', 'phone', 'address', 'date_of_birth', 'country',
            'country_display', 'company_name', 'created_at',
            'preferred_contact_method', 'brand_guidelines'
        ]
        read_only_fields = ['id', 'created_at', 'user', 'country_display'] # Añadir 'id'

class CustomerCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(write_only=True) # Solo para entrada
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True, # Asegurarse que siempre se pida un rol primario
        help_text=_("ID del rol principal obligatorio para este cliente.")
    )
    # Permitir null/blank para country si es opcional
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Customer
        # Incluir campos de Customer y los necesarios para crear el User
        fields = [
            'user', 'primary_role', 'phone', 'address', 'date_of_birth',
            'country', 'company_name', 'preferred_contact_method', 'brand_guidelines'
        ]
        # No necesitamos read_only_fields aquí ya que es para creación

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        customer_specific_data = validated_data # Datos restantes para Customer

        # Re-validar unicidad aquí por si acaso (aunque UserCreateSerializer ya lo hace)
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        # Crear el usuario usando el serializer específico
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        # --- Asignar is_staff y rol primario ---
        user.is_staff = False # Los clientes NO son staff
        user.save(update_fields=['is_staff'])

        try:
            # La señal post_save debería haber creado UserProfile
            user_profile = UserProfile.objects.get(user=user)
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean() # Ejecutar validaciones del modelo UserProfile
        except UserProfile.DoesNotExist:
            # Si la señal falló por alguna razón (muy raro), loggear y fallar
            logger.error(f"Error crítico: No se encontró/creó UserProfile para el usuario recién creado {user.username}")
            raise ValidationError(_("Error interno al inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a {user.username}: {e.message_dict}")
             user.delete() # Rollback manual de la creación del usuario
             # Devolver el error específico del campo si es posible
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', _('Error asignando rol primario.'))})

        # Crear o actualizar el perfil de Cliente
        # Usar update_or_create es seguro si la señal de Customer ya lo creó
        customer, created = Customer.objects.update_or_create(
            user=user, defaults=customer_specific_data
        )
        # Devolver la instancia de Customer creada/actualizada
        # Para que la respuesta de la API sea consistente, serializamos la instancia creada
        # usando el serializer de lectura (CustomerSerializer)
        return customer # La vista usará el serializer adecuado para la respuesta

class EmployeeSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True) # Muestra info detallada del usuario
    position = JobPositionSerializer(read_only=True) # Muestra info del puesto
    # Para actualizar la posición, permitir enviar solo el ID
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', write_only=True,
        required=False, allow_null=True # Permitir quitar o no asignar puesto
    )
    # El campo is_active se obtiene del BasicUserSerializer anidado
    # is_active = serializers.BooleanField(source='user.is_active', read_only=True) # Redundante

    class Meta:
        model = Employee
        fields = [
            'id', 'user', #'is_active', # Quitado porque está en user
            'hire_date', 'address', 'salary',
            'position', # Para lectura
            'position_id' # Para escritura
        ]
        # Campos que solo se leen desde el modelo Employee o User
        read_only_fields = ['id', 'hire_date', 'user', 'position'] # Añadir 'id'


class EmployeeCreateSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(write_only=True)
    primary_role = serializers.PrimaryKeyRelatedField(
        queryset=UserRole.objects.filter(is_active=True),
        write_only=True,
        required=True,
        help_text=_("ID del rol principal obligatorio para este empleado.")
    )
    # Campo para asignar la posición al crear
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPosition.objects.all(), source='position', # Usa source='position' para mapear al campo del modelo
        required=False, allow_null=True, write_only=True # write_only porque se mostrará a través de EmployeeSerializer
    )

    class Meta:
        model = Employee
        fields = [
            'user', 'primary_role', 'position_id', # ID del puesto para crear
            'address', 'salary', 'hire_date'
        ]
        # Hacer hire_date opcional al crear si se desea
        extra_kwargs = { 'hire_date': {'required': False, 'allow_null': True} }

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        primary_role_obj = validated_data.pop('primary_role')
        # Extraer position_id y quitarlo de los datos para Employee
        # El source='position' en el campo ya maneja la asignación
        employee_specific_data = validated_data # position_id ya está mapeado por source

        # Validar unicidad de email/username
        if User.objects.filter(email=user_data['email']).exists():
            raise ValidationError({'user': {'email': [_('Ya existe un usuario con este email.')]}})
        if User.objects.filter(username=user_data['username']).exists():
             raise ValidationError({'user': {'username': [_('Ya existe un usuario con este nombre de usuario.')]}})

        # Crear usuario
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        user = user_serializer.save()

        # Asignar is_staff y rol primario
        user.is_staff = True # Empleados SON staff
        user.save(update_fields=['is_staff'])

        try:
            user_profile = UserProfile.objects.get(user=user) # Señal debería haber creado
            user_profile.primary_role = primary_role_obj
            user_profile.save(update_fields=['primary_role'])
            user_profile.full_clean()
        except UserProfile.DoesNotExist:
            logger.error(f"Error crítico: No se encontró/creó UserProfile para el empleado recién creado {user.username}")
            raise ValidationError(_("Error interno al inicializar el perfil de usuario."))
        except ValidationError as e:
             logger.error(f"Error de validación al asignar rol primario a empleado {user.username}: {e.message_dict}")
             user.delete() # Rollback
             raise ValidationError({'primary_role': e.message_dict.get('primary_role', _('Error asignando rol primario.'))})

        # Crear el perfil de Empleado
        # validated_data ya contiene 'position' gracias a source='position'
        employee = Employee.objects.create(user=user, **employee_specific_data)
        return employee # Devolver instancia creada


# --- RESTO DE SERIALIZERS (Revisados, sin cambios mayores necesarios) ---

class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = '__all__' # ['code', 'name']

class PriceSerializer(serializers.ModelSerializer):
    # Serializer específico para mostrar historial de precios
    class Meta:
        model = Price
        fields = ['id', 'amount', 'currency', 'effective_date'] # No incluir 'service' aquí
        read_only_fields = fields

class ServiceFeatureSerializer(serializers.ModelSerializer):
    feature_type_display = serializers.CharField(source='get_feature_type_display', read_only=True)
    class Meta:
        model = ServiceFeature
        fields = ['id', 'feature_type', 'feature_type_display', 'description'] # No incluir 'service'
        read_only_fields = ['id', 'feature_type_display']

class ServiceSerializer(serializers.ModelSerializer):
    # Mostrar nombres legibles y info relacionada
    category_name = serializers.CharField(source='category.name', read_only=True)
    campaign_name = serializers.CharField(source='campaign.campaign_name', read_only=True, allow_null=True)
    features = ServiceFeatureSerializer(many=True, read_only=True)
    price_history = PriceSerializer(many=True, read_only=True)
    current_eur_price = serializers.SerializerMethodField()

    # Campos para escribir (actualizar/crear)
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
            'code', # Code suele ser inmutable una vez creado
            'category_name', 'campaign_name', 'features', 'price_history', 'current_eur_price'
        ]
        # Opcional: hacer write_only los campos de FK si solo se usan para escribir
        # extra_kwargs = {
        #     'category': {'write_only': True},
        #     'campaign': {'write_only': True},
        # }

    def get_current_eur_price(self, obj):
        price = obj.get_current_price(currency='EUR')
        return price.amount if price else None # Devolver solo el monto

class OrderServiceCreateSerializer(serializers.ModelSerializer):
    # Para añadir/actualizar servicios en una orden
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'quantity', 'price', 'note']
        read_only_fields = ['id'] # ID es de solo lectura

    def validate_price(self, value):
        if value is not None and value < Decimal('0.00'):
            raise ValidationError(_("El precio no puede ser negativo."))
        return value

class OrderServiceReadSerializer(serializers.ModelSerializer):
    # Para mostrar servicios dentro de una orden (lectura)
    service = ServiceSerializer(read_only=True) # Mostrar info completa del servicio
    price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'quantity', 'price', 'note']
        read_only_fields = fields # Todo es de solo lectura aquí

class EmployeeBasicSerializer(serializers.ModelSerializer):
    # Serializer MUY básico para mostrar solo info mínima del empleado
    # Usa BasicUserSerializer para info del usuario (nombre, puesto, etc.)
    user = BasicUserSerializer(read_only=True)
    class Meta:
        model = Employee
        fields = ['id', 'user']
        read_only_fields = fields

class ProviderBasicSerializer(serializers.ModelSerializer):
     # Serializer MUY básico para mostrar solo info mínima del proveedor
     class Meta:
        model = Provider
        fields = ['id', 'name']
        read_only_fields = fields

class DeliverableSerializer(serializers.ModelSerializer):
    # Mostrar info de empleado/proveedor asignado
    assigned_employee_info = EmployeeBasicSerializer(source='assigned_employee', read_only=True)
    assigned_provider_info = ProviderBasicSerializer(source='assigned_provider', read_only=True)
    # Mostrar info legible
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_url = serializers.SerializerMethodField()

    # Campos para escribir (asignar empleado/proveedor)
    assigned_employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(user__is_active=True), # Solo activos
        write_only=True, required=False, allow_null=True
    )
    assigned_provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.filter(is_active=True), # Solo activos
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Deliverable
        fields = [
            'id', 'order_id', 'description', 'version', 'file', 'file_url',
            'status', 'status_display', 'due_date',
            'assigned_employee', 'assigned_employee_info', # write / read
            'assigned_provider', 'assigned_provider_info', # write / read
            'feedback_notes', 'created_at'
        ]
        read_only_fields = [
            'id', 'order_id', 'version', 'created_at', 'status_display', 'file_url',
            'assigned_employee_info', 'assigned_provider_info' # Info es solo lectura
        ]
        # Opcional: Hacer 'file' read_only si solo se sube/actualiza por endpoint específico

    def get_file_url(self, obj):
        return obj.file.url if obj.file else None

class OrderReadSerializer(serializers.ModelSerializer):
    # Serializer para LEER detalles de una orden
    customer = CustomerSerializer(read_only=True) # Info completa del cliente
    employee = EmployeeBasicSerializer(read_only=True) # Info básica del empleado asignado
    services = OrderServiceReadSerializer(many=True, read_only=True) # Lista de servicios detallada
    deliverables = DeliverableSerializer(many=True, read_only=True) # Lista de entregables detallada
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # El total_amount se calcula en el modelo, aquí solo se lee
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'status_display',
            'date_received', 'date_required', 'payment_due_date', 'note',
            'priority', 'completed_at', 'total_amount', 'services', 'deliverables'
        ]
        read_only_fields = fields # Este serializer es solo para lectura

class OrderCreateUpdateSerializer(serializers.ModelSerializer):
    # Serializer para CREAR o ACTUALIZAR una orden
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    employee = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(user__is_active=True),
        required=False, allow_null=True # Empleado es opcional
    )
    # Usar el serializer de creación para los servicios anidados
    services = OrderServiceCreateSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'employee', 'status', 'date_required',
            'payment_due_date', 'note', 'priority', 'services'
        ]
        read_only_fields = ['id'] # ID no se puede cambiar

    def _create_or_update_services(self, order, services_data):
        """Helper para manejar la creación/actualización de servicios anidados."""
        # Eliminar servicios existentes y crear los nuevos (estrategia simple)
        # Podría ser más complejo para actualizar existentes si se necesita
        current_service_ids = {s.id for s in order.services.all()}
        incoming_service_data_map = {item.get('id'): item for item in services_data if item.get('id')}
        ids_to_update = current_service_ids.intersection(incoming_service_data_map.keys())
        ids_to_delete = current_service_ids - ids_to_update

        # Eliminar
        if ids_to_delete:
            OrderService.objects.filter(order=order, id__in=ids_to_delete).delete()

        services_to_create_bulk = []
        services_to_update_bulk = []

        for service_data in services_data:
            service_id = service_data.get('id')
            service_obj = service_data.get('service') # PKRelatedField ya validó que existe

            # Asignar precio si no viene
            if 'price' not in service_data or service_data['price'] is None:
                base_price = service_obj.get_current_price(currency='EUR') if service_obj else None
                service_data['price'] = base_price if base_price is not None else Decimal('0.00')

            if service_id in ids_to_update:
                # Preparar para actualizar (si bulk_update fuera fácil, si no, actualizar uno a uno)
                 instance = OrderService.objects.get(id=service_id, order=order)
                 instance.service = service_data['service']
                 instance.quantity = service_data['quantity']
                 instance.price = service_data['price']
                 instance.note = service_data.get('note', '')
                 services_to_update_bulk.append(instance) # Necesitaría bulk_update con Django 4+
            elif not service_id:
                # Preparar para crear
                services_to_create_bulk.append(OrderService(order=order, **service_data))

        # Ejecutar operaciones DB
        if services_to_create_bulk:
            OrderService.objects.bulk_create(services_to_create_bulk)
        if services_to_update_bulk:
             # Django < 4 no tiene bulk_update fácil con todos los campos
             # Actualizar uno a uno o usar bulk_update si la versión lo permite
             for instance in services_to_update_bulk:
                 instance.save(update_fields=['service', 'quantity', 'price', 'note'])
             # O si Django >= 4:
             # OrderService.objects.bulk_update(services_to_update_bulk, ['service', 'quantity', 'price', 'note'])


    @transaction.atomic
    def create(self, validated_data):
        services_data = validated_data.pop('services', [])
        # Crear la orden principal
        order = Order.objects.create(**validated_data)
        # Crear los servicios asociados
        self._create_or_update_services(order, services_data)
        # La señal post_save de OrderService actualizará el total_amount
        order.refresh_from_db() # Recargar para obtener el total actualizado
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        services_data = validated_data.pop('services', None) # None indica que no se enviaron servicios
        # Actualizar campos de la orden principal
        # super().update() maneja los campos directos del modelo Order
        instance = super().update(instance, validated_data)

        # Si se envió una lista de servicios (incluso vacía), actualizarlos
        if services_data is not None:
            self._create_or_update_services(instance, services_data)

        # La señal post_save/post_delete de OrderService actualizará el total_amount
        instance.refresh_from_db() # Recargar para obtener el total actualizado
        return instance

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__' # ['id', 'name', 'is_active']

class TransactionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        fields = '__all__' # ['id', 'name', 'requires_approval']

class InvoiceBasicSerializer(serializers.ModelSerializer):
     # Para listas de facturas, mostrar info esencial
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     # Calcular balance y total (son properties en el modelo)
     balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
     total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
     # Info básica del cliente
     customer_name = serializers.CharField(source='order.customer.__str__', read_only=True)

     class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer_name', 'date', 'due_date',
            'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due'
        ]
        read_only_fields = fields

class PaymentReadSerializer(serializers.ModelSerializer):
     # Para mostrar detalles de un pago
     method_name = serializers.CharField(source='method.name', read_only=True)
     transaction_type_name = serializers.CharField(source='transaction_type.name', read_only=True)
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)

     class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_number', 'method', 'method_name',
            'transaction_type', 'transaction_type_name', 'date', 'amount',
            'currency', 'status', 'status_display', 'transaction_id', 'notes'
        ]
        read_only_fields = fields # Serializer solo para lectura

class PaymentCreateSerializer(serializers.ModelSerializer):
     # Para crear un nuevo pago
     invoice = serializers.PrimaryKeyRelatedField(
         queryset=Invoice.objects.exclude(status__in=Invoice.FINAL_STATUSES) # No pagar facturas finales
     )
     method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.filter(is_active=True))
     transaction_type = serializers.PrimaryKeyRelatedField(queryset=TransactionType.objects.all())

     class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'method', 'transaction_type', 'amount',
            'currency', 'status', 'transaction_id', 'notes'
        ]
        read_only_fields = ['id'] # ID se autogenera

     def validate_amount(self, value):
        if value <= Decimal('0.00'):
             raise ValidationError(_("El monto del pago debe ser positivo."))
        return value

     # Opcional: Validar que el monto no exceda el balance pendiente
     def validate(self, data):
         invoice = data['invoice']
         amount = data['amount']
         if amount > invoice.balance_due:
             raise ValidationError(
                 {'amount': _(f"El monto del pago ({amount}) excede el balance pendiente ({invoice.balance_due}).")}
             )
         return data


class InvoiceSerializer(serializers.ModelSerializer):
    # Para ver/crear/actualizar una factura detallada
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.CharField(source='order.customer.__str__', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Calculado
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Calculado
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True) # Calculado por señal
    payments = PaymentReadSerializer(many=True, read_only=True) # Lista de pagos asociados

    # Campo para escribir (asociar orden al crear)
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), write_only=True, required=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'order', 'order_id', 'customer_name', 'invoice_number', 'date',
            'due_date', 'status', 'status_display', 'total_amount', 'paid_amount',
            'balance_due', 'notes', 'payments'
        ]
        read_only_fields = [
            'id', 'order_id', 'customer_name', 'invoice_number', # Se autogenera
            'paid_amount', 'status_display', 'total_amount', 'balance_due', 'payments'
        ]

class CampaignServiceSerializer(serializers.ModelSerializer):
    # Para mostrar/gestionar servicios dentro de una campaña
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_code = serializers.CharField(source='service.code', read_only=True)
    # Campo para escribir (asociar servicio)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), write_only=True)

    class Meta:
        model = CampaignService
        # Incluir 'campaign' para contexto, pero será read_only si se anida
        fields = [
            'id', 'campaign', 'service', 'service_code', 'service_name',
            'discount_percentage', 'additional_details'
        ]
        read_only_fields = ['id', 'campaign', 'service_code', 'service_name']

class CampaignSerializer(serializers.ModelSerializer):
    # Serializer para Campañas
    # Mostrar servicios incluidos usando el serializer anidado
    included_services = CampaignServiceSerializer(many=True, read_only=True)
    # Opcional: Permitir añadir/actualizar servicios al crear/actualizar campaña
    # included_services_write = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Campaign
        fields = [
            'campaign_code', 'campaign_name', 'start_date', 'end_date',
            'description', 'target_audience', 'budget', 'is_active',
            'included_services', # 'included_services_write'
        ]
        read_only_fields = ['campaign_code', 'included_services'] # Code es PK

class ProviderSerializer(serializers.ModelSerializer):
    # Serializer para Proveedores
    # Mostrar detalles de servicios asociados
    services_provided_details = ServiceSerializer(source='services_provided', many=True, read_only=True)
    # Campo para escribir (asignar servicios por ID)
    services_provided = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), many=True, write_only=True, required=False
    )

    class Meta:
        model = Provider
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone', 'rating',
            'is_active', 'notes', 'services_provided', 'services_provided_details'
        ]
        read_only_fields = ['id', 'services_provided_details']

class NotificationSerializer(serializers.ModelSerializer):
    # Mostrar notificaciones
    user = BasicUserSerializer(read_only=True) # Info básica del usuario receptor

    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'read', 'created_at', 'link']
        read_only_fields = fields # Este serializer es solo para lectura

class AuditLogSerializer(serializers.ModelSerializer):
    # Mostrar logs de auditoría
    user = BasicUserSerializer(read_only=True) # Info básica del usuario que realizó la acción

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'action', 'timestamp', 'details']
        read_only_fields = fields # Solo lectura