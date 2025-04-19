# api/models.py

import datetime
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, DecimalField, DurationField, ExpressionWrapper, F, Sum
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

# --- Importa tus constantes de roles ---
try:
    from .roles import Roles
except ImportError:
    # Define placeholders si el archivo no existe (la app podría fallar si no existen realmente)
    class Roles:
        DRAGON = 'dragon'; ADMIN = 'admin'; MARKETING = 'mktg'; FINANCE = 'fin'
        SALES = 'sales'; DEVELOPMENT = 'dev'; AUDIOVISUAL = 'avps'; DESIGN = 'dsgn'
        SUPPORT = 'support'; OPERATIONS = 'ops'; HR = 'hr'
    print("ADVERTENCIA: api/roles.py no encontrado. Usando roles placeholder.")


# --- Helper para obtener usuario actual (requiere django-crum) ---
try:
    from crum import get_current_user
except ImportError:
    get_current_user = lambda: None
    print("ADVERTENCIA: django-crum no está instalado. Los AuditLogs no registrarán el usuario.")

# Configurar logger para este módulo
logger = logging.getLogger(__name__)

# ==============================================================================
# ------ MODELOS DE GESTIÓN DE USUARIOS, ROLES Y PERFILES ---------------------
# ==============================================================================

class UserRole(models.Model):
    """Define los roles disponibles en la aplicación (Primarios y Secundarios)."""
    name = models.CharField(
        _("Internal Name"), max_length=50, unique=True,
        help_text=_("Short internal alias (e.g., 'dev', 'mktg'). Use constants from roles.py.")
    )
    display_name = models.CharField(
        _("Display Name"), max_length=100,
        help_text=_("User-friendly name shown in interfaces.")
    )
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class UserProfile(models.Model):
    """Extiende el modelo User para almacenar el rol principal obligatorio."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, primary_key=True, related_name='profile', verbose_name=_("User")
    )
    primary_role = models.ForeignKey(
        UserRole, on_delete=models.PROTECT, null=True, blank=False, # null=True temporal para señal
        related_name='primary_users', verbose_name=_("Primary Role"),
        help_text=_("The main mandatory role defining the user's core function.")
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        role_name = self.primary_role.display_name if self.primary_role else _("No primary role assigned")
        username = self.user.get_username() if hasattr(self, 'user') else 'N/A'
        return f"{username} - Profile ({role_name})"

    def clean(self):
        if not self.primary_role_id:
            raise ValidationError({'primary_role': _('A primary role must be assigned.')})

class UserRoleAssignment(models.Model):
    """Vincula un Usuario con un Rol SECUNDARIO (Acceso) específico."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='secondary_role_assignments', verbose_name=_("User")
    )
    role = models.ForeignKey(
        UserRole, on_delete=models.CASCADE,
        related_name='secondary_assignments', verbose_name=_("Secondary Role/Access")
    )
    is_active = models.BooleanField(_("Assignment Active"), default=True)
    assigned_at = models.DateTimeField(_("Assigned At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        unique_together = ('user', 'role')
        verbose_name = _("Secondary Role / Access Assignment")
        verbose_name_plural = _("Secondary Role / Access Assignments")
        ordering = ['user__username', 'role__display_name']

    def __str__(self):
        status = _("Active") if self.is_active else _("Inactive")
        username = self.user.get_username() if hasattr(self, 'user') else 'N/A'
        role_name = self.role.display_name if hasattr(self, 'role') else 'N/A'
        return f"{username} - Access: {role_name} ({status})"

    def clean(self):
        if self.user_id and self.role_id:
            try:
                primary_role_id = UserProfile.objects.filter(user_id=self.user_id).values_list('primary_role_id', flat=True).first()
                if primary_role_id and primary_role_id == self.role_id:
                    raise ValidationError({'role': _('This role is already assigned as the primary role for this user.')})
            except Exception as e:
                 logger.warning(f"Excepción durante validación de UserRoleAssignment.clean: {e}")
                 pass

# ==============================================================================
# ---------------------- MODELOS DE LA APLICACIÓN -----------------------------
# ==============================================================================

class Form(models.Model):
    """Modelo para definir estructuras de formularios."""
    name = models.CharField(_("Nombre del Formulario"), max_length=100)
    description = models.TextField(_("Descripción"), blank=True)
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)

    class Meta:
        verbose_name = _("Formulario")
        verbose_name_plural = _("Formularios")
        ordering = ['name']

    def __str__(self):
        return self.name

class FormQuestion(models.Model):
    """Pregunta específica dentro de un formulario."""
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name='questions', verbose_name=_("Formulario")
    )
    question_text = models.TextField(_("Texto de la Pregunta"))
    order = models.PositiveIntegerField(
        _("Orden"), default=0, help_text=_("Orden de aparición en el formulario")
    )
    required = models.BooleanField(_("Requerida"), default=True)

    class Meta:
        ordering = ['form', 'order']
        verbose_name = _("Pregunta de Formulario")
        verbose_name_plural = _("Preguntas de Formularios")

    def __str__(self):
        form_name = self.form.name if hasattr(self, 'form') else 'N/A'
        return f"{form_name} - P{self.order}: {self.question_text[:50]}..."

class FormResponse(models.Model):
    """Respuesta de un cliente a una pregunta de un formulario."""
    customer = models.ForeignKey(
        'Customer', on_delete=models.CASCADE, related_name='form_responses', verbose_name=_("Cliente")
    )
    form = models.ForeignKey(
        Form, on_delete=models.CASCADE, related_name='responses', verbose_name=_("Formulario")
    )
    question = models.ForeignKey(
        FormQuestion, on_delete=models.CASCADE, related_name='responses', verbose_name=_("Pregunta")
    )
    text = models.TextField(_("Respuesta"), help_text=_("Respuesta proporcionada por el cliente"))
    created_at = models.DateTimeField(_("Fecha de Respuesta"), auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'form', 'question')
        ordering = ['created_at']
        verbose_name = _("Respuesta de Formulario")
        verbose_name_plural = _("Respuestas de Formularios")

    def __str__(self):
        customer_str = str(self.customer) if hasattr(self, 'customer') else 'N/A'
        question_str = str(self.question) if hasattr(self, 'question') else 'N/A'
        return f"{_('Respuesta')} de {customer_str} a {question_str}"

class Customer(models.Model):
    """Perfil de un cliente."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile', verbose_name=_("Usuario")
    )
    phone = models.CharField(_("Teléfono"), max_length=30, null=True, blank=True)
    address = models.TextField(_("Dirección"), null=True, blank=True)
    date_of_birth = models.DateField(_("Fecha de Nacimiento"), null=True, blank=True)
    country = CountryField(
        _("País"), blank=True, null=True, help_text=_("País del cliente")
    )
    company_name = models.CharField(
        _("Nombre de Empresa"), max_length=150, blank=True, null=True, help_text=_("Nombre de la empresa (si aplica)")
    )
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    preferred_contact_method = models.CharField(
        _("Método Contacto Preferido"), max_length=20,
        choices=[('email', 'Email'), ('phone', 'Teléfono'), ('whatsapp', 'WhatsApp'), ('other', 'Otro')],
        null=True, blank=True
    )
    brand_guidelines = models.FileField(
        _("Guías de Marca"), upload_to='customers/brand_guidelines/', null=True, blank=True
    )

    class Meta:
        verbose_name = _("Cliente")
        verbose_name_plural = _("Clientes")
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        display_name = self.company_name or self.user.get_full_name() or self.user.username
        email = self.user.email if hasattr(self, 'user') else 'N/A'
        return f"{display_name} ({email})"

class JobPosition(models.Model):
    """Puesto de trabajo dentro de la organización."""
    name = models.CharField(_("Nombre del Puesto"), max_length=50, unique=True)
    description = models.TextField(_("Descripción"), null=True, blank=True)
    permissions = models.JSONField(
        _("Permisos JSON"), default=dict, blank=True, help_text=_("Permisos específicos para este puesto (estructura JSON)")
    )

    class Meta:
        verbose_name = _("Puesto de Trabajo")
        verbose_name_plural = _("Puestos de Trabajo")
        ordering = ['name']

    def __str__(self):
        return self.name

class Employee(models.Model):
    """Perfil de un empleado."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_profile', verbose_name=_("Usuario")
    )
    hire_date = models.DateField(_("Fecha Contratación"), default=datetime.date.today)
    address = models.TextField(_("Dirección"), null=True, blank=True)
    salary = models.DecimalField(
        _("Salario"), max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    position = models.ForeignKey(
        JobPosition, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name=_("Puesto")
    )

    class Meta:
        verbose_name = _("Empleado")
        verbose_name_plural = _("Empleados")
        ordering = ['user__first_name', 'user__last_name']

    @property
    def is_active(self):
        return self.user.is_active

    def __str__(self):
        position_name = self.position.name if self.position else _("Sin puesto")
        status = _("[ACTIVO]") if self.is_active else _("[INACTIVO]")
        display_name = self.user.get_full_name() or self.user.get_username()
        return f"{display_name} ({position_name}) {status}"

class Order(models.Model):
    """Modelo principal para los pedidos de los clientes."""
    STATUS_CHOICES = [
        ('DRAFT', _('Borrador')), ('CONFIRMED', _('Confirmado')), ('PLANNING', _('Planificación')),
        ('IN_PROGRESS', _('En Progreso')), ('QUALITY_CHECK', _('Control de Calidad')),
        ('PENDING_DELIVERY', _('Pendiente Entrega')), ('DELIVERED', _('Entregado')),
        ('CANCELLED', _('Cancelado')), ('ON_HOLD', _('En Espera')),
    ]
    FINAL_STATUSES = ['DELIVERED', 'CANCELLED']

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='orders',
        help_text=_("Cliente que realiza el pedido"), verbose_name=_("Cliente")
    )
    employee = models.ForeignKey(
        Employee, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='managed_orders', help_text=_("Empleado responsable principal"), verbose_name=_("Empleado Asignado")
    )
    date_received = models.DateTimeField(_("Fecha Recepción"), auto_now_add=True)
    date_required = models.DateTimeField(_("Fecha Requerida"), help_text=_("Fecha límite solicitada por el cliente"))
    status = models.CharField(
        _("Estado"), max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True
    )
    payment_due_date = models.DateTimeField(
        _("Vencimiento Pago"), null=True, blank=True, help_text=_("Fecha límite para el pago (si aplica)")
    )
    note = models.TextField(_("Nota Interna"), null=True, blank=True)
    priority = models.PositiveIntegerField(
        _("Prioridad"), default=3, help_text=_("Prioridad (ej. 1=Alta, 5=Baja)")
    )
    completed_at = models.DateTimeField(
        _("Fecha Completado"), null=True, blank=True, editable=False, help_text=_("Fecha y hora de finalización (status='DELIVERED')")
    )
    total_amount = models.DecimalField(
        _("Monto Total"), max_digits=12, decimal_places=2, default=Decimal('0.00'),
        editable=False, help_text=_("Calculado de OrderService. Actualizado automáticamente.")
    )

    class Meta:
        ordering = ['priority', '-date_received']
        verbose_name = _("Pedido")
        verbose_name_plural = _("Pedidos")

    def __str__(self):
        customer_str = str(self.customer) if hasattr(self, 'customer') else 'N/A'
        return f"{_('Pedido')} #{self.id} ({self.get_status_display()}) - {customer_str}"

    def update_total_amount(self):
        """Calcula y guarda el monto total basado en los servicios asociados."""
        # Se asume que self.services existe en este punto
        total = self.services.aggregate(total=Sum(F('price') * F('quantity')))['total']
        calculated_total = total if total is not None else Decimal('0.00')
        # Actualizar solo si el valor calculado es diferente y el objeto ya existe
        if self.pk and self.total_amount != calculated_total:
             Order.objects.filter(pk=self.pk).update(total_amount=calculated_total)
             self.total_amount = calculated_total # Actualizar instancia en memoria

class ServiceCategory(models.Model):
    """Categorías para agrupar servicios."""
    code = models.CharField(
        _("Código Categoría"), max_length=10, primary_key=True,
        help_text=_("Código corto de la categoría (ej. MKT, DEV)")
    )
    name = models.CharField(
        _("Nombre Categoría"), max_length=100, help_text=_("Nombre descriptivo de la categoría")
    )

    class Meta:
        verbose_name = _("Categoría de Servicio")
        verbose_name_plural = _("Categorías de Servicios")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

class Campaign(models.Model):
    """Campañas de marketing o promocionales."""
    campaign_code = models.CharField(_("Código Campaña"), max_length=20, primary_key=True)
    campaign_name = models.CharField(_("Nombre Campaña"), max_length=255)
    start_date = models.DateTimeField(_("Fecha Inicio"), help_text=_("Fecha y hora de inicio de la campaña"))
    end_date = models.DateTimeField(
        _("Fecha Fin"), null=True, blank=True, help_text=_("Fecha y hora de fin (opcional)")
    )
    description = models.TextField(_("Descripción"), null=True, blank=True)
    target_audience = models.JSONField(
        _("Público Objetivo"), default=dict, blank=True, help_text=_("Descripción del público objetivo (JSON)")
    )
    budget = models.DecimalField(
        _("Presupuesto"), max_digits=12, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(
        _("Activa"), default=True, help_text=_("¿La campaña está activa actualmente?")
    )

    class Meta:
        ordering = ['-start_date']
        verbose_name = _("Campaña")
        verbose_name_plural = _("Campañas")

    def __str__(self):
        status = _("[ACTIVA]") if self.is_active else _("[INACTIVA]")
        return f"{self.campaign_name} ({self.campaign_code}) {status}"

class Service(models.Model):
    """Servicios ofrecidos por la agencia."""
    code = models.CharField(
        _("Código Servicio"), max_length=10, primary_key=True, help_text=_("Código único del servicio (ej. OD001)")
    )
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.PROTECT, related_name='services',
        help_text=_("Categoría principal del servicio"), verbose_name=_("Categoría")
    )
    name = models.CharField(
        _("Nombre Servicio"), max_length=255, help_text=_("Nombre descriptivo del servicio")
    )
    is_active = models.BooleanField(
        _("Activo"), default=True, help_text=_("¿El servicio está activo y disponible para la venta?")
    )
    ventulab = models.BooleanField(
        _("Ventulab"), default=False, help_text=_("¿Es un servicio interno o especial de Ventulab?")
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promoted_services', help_text=_("Campaña promocional asociada directa (opcional)"),
        verbose_name=_("Campaña Asociada")
    )
    is_package = models.BooleanField(
        _("Es Paquete"), default=False, help_text=_("¿Este servicio es un paquete que agrupa otros?")
    )
    is_subscription = models.BooleanField(
        _("Es Suscripción"), default=False, help_text=_("¿Este servicio es una suscripción recurrente?")
    )
    audience = models.TextField(
        _("Público Objetivo"), blank=True, null=True, help_text=_("Público objetivo principal de este servicio")
    )
    detailed_description = models.TextField(
        _("Descripción Detallada"), blank=True, null=True, help_text=_("Descripción más detallada del servicio")
    )
    problem_solved = models.TextField(
        _("Problema que Soluciona"), blank=True, null=True, help_text=_("Qué problema o necesidad soluciona este servicio")
    )

    class Meta:
        ordering = ['category', 'name']
        verbose_name = _("Servicio")
        verbose_name_plural = _("Servicios")

    def __str__(self):
        package_indicator = _(" [Paquete]") if self.is_package else ""
        subscription_indicator = _(" [Suscripción]") if self.is_subscription else ""
        status = _("[ACTIVO]") if self.is_active else _("[INACTIVO]")
        return f"{self.name} ({self.code}){package_indicator}{subscription_indicator} {status}"

    def get_current_price(self, currency='EUR'):
        """Obtiene el precio más reciente para una moneda específica."""
        latest_price = self.price_history.filter(currency=currency).order_by('-effective_date').first()
        return latest_price.amount if latest_price else None

class ServiceFeature(models.Model):
    """Características, beneficios o detalles de un servicio."""
    FEATURE_TYPES = [
        ('differentiator', _('Diferenciador')), ('benefit', _('Beneficio')),
        ('caracteristicas', _('Características')), ('process', _('Proceso')),
        ('result', _('Resultado Esperado')),
    ]
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name='features', verbose_name=_("Servicio")
    )
    feature_type = models.CharField(
        _("Tipo"), max_length=20, choices=FEATURE_TYPES, help_text=_("Tipo de característica")
    )
    description = models.TextField(
        _("Descripción"), help_text=_("Descripción de la característica, beneficio, etc.")
    )

    class Meta:
        ordering = ['service', 'feature_type']
        verbose_name = _("Característica de Servicio")
        verbose_name_plural = _("Características de Servicios")

    def __str__(self):
        service_code = self.service.code if hasattr(self, 'service') else 'N/A'
        return f"{service_code} - {self.get_feature_type_display()}: {self.description[:50]}..."

class Price(models.Model):
    """Historial de precios para un servicio."""
    service = models.ForeignKey(
        Service, on_delete=models.CASCADE, related_name='price_history', verbose_name=_("Servicio")
    )
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    currency = models.CharField(
        _("Moneda"), max_length=3, default='EUR', help_text=_("Código ISO 4217 (ej. EUR, USD, CLP, COP)")
    )
    effective_date = models.DateField(
        _("Fecha Efectiva"), default=datetime.date.today, help_text=_("Fecha desde la que este precio es válido")
    )

    class Meta:
        get_latest_by = 'effective_date'
        ordering = ['service', 'currency', '-effective_date']
        unique_together = ['service', 'currency', 'effective_date']
        verbose_name = _("Precio Histórico")
        verbose_name_plural = _("Historial de Precios")

    def __str__(self):
        service_code = self.service.code if hasattr(self, 'service') else 'N/A'
        return f"{_('Precio')} de {service_code} - {self.amount} {self.currency} ({_('desde')} {self.effective_date})"

class OrderService(models.Model):
    """Servicio específico incluido en un pedido."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='services', verbose_name=_("Pedido"))
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='order_lines', verbose_name=_("Servicio"))
    quantity = models.PositiveIntegerField(_("Cantidad"), default=1)
    price = models.DecimalField(
        _("Precio Unitario"), max_digits=12, decimal_places=2,
        help_text=_("Precio unitario en el momento de añadir a la orden")
    )
    note = models.TextField(_("Nota"), blank=True, help_text=_("Notas específicas para este servicio en esta orden"))

    class Meta:
        verbose_name = _("Servicio del Pedido")
        verbose_name_plural = _("Servicios del Pedido")
        ordering = ['order', 'id']

    def __str__(self):
        service_name = self.service.name if hasattr(self, 'service') else 'N/A'
        order_id = self.order_id if hasattr(self, 'order_id') else 'N/A'
        return f"{_('Servicio')} '{service_name}' x{self.quantity} en {_('Pedido')} #{order_id}"

    def save(self, *args, **kwargs):
        # Asignar precio base si es nuevo y no tiene precio
        if not self.pk and (self.price is None or self.price <= Decimal('0.00')):
            base_price = None
            try:
                 if self.service_id:
                      service_instance = Service.objects.get(pk=self.service_id)
                      base_price = service_instance.get_current_price(currency='EUR')
            except Service.DoesNotExist: logger.warning(f"Servicio ID {self.service_id} no encontrado al guardar OrderService.")
            except Exception as e: logger.error(f"Error obteniendo precio base para servicio ID {self.service_id}: {e}")
            self.price = base_price if base_price is not None else Decimal('0.00')
        super().save(*args, **kwargs) # Llamar al save original

class Deliverable(models.Model):
    """Entregable o tarea asociada a un pedido."""
    STATUS_CHOICES = [
        ('PENDING', _('Pendiente')), ('ASSIGNED', _('Asignado')), ('IN_PROGRESS', _('En Progreso')),
        ('PENDING_APPROVAL', _('Pendiente Aprobación Cliente')), ('PENDING_INTERNAL_APPROVAL', _('Pendiente Aprobación Interna')),
        ('REQUIRES_INFO', _('Requiere Info Adicional')), ('REVISION_REQUESTED', _('Revisión Solicitada')),
        ('APPROVED', _('Aprobado')), ('COMPLETED', _('Completado')), ('REJECTED', _('Rechazado')),
    ]
    FINAL_STATUSES = ['COMPLETED', 'REJECTED']

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliverables', verbose_name=_("Pedido"))
    file = models.FileField(_("Archivo"), upload_to='deliverables/%Y/%m/', null=True, blank=True, help_text=_("Archivo entregable (opcional inicialmente)"))
    description = models.TextField(_("Descripción"), help_text=_("Descripción clara de la tarea o entregable"))
    created_at = models.DateTimeField(_("Fecha de Creación"), auto_now_add=True)
    version = models.PositiveIntegerField(_("Versión"), default=1)
    status = models.CharField(_("Estado"), max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    due_date = models.DateField(_("Fecha Límite"), null=True, blank=True, help_text=_("Fecha límite para este entregable"))
    assigned_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables', verbose_name=_("Empleado Asignado"))
    assigned_provider = models.ForeignKey('Provider', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables', verbose_name=_("Proveedor Asignado"))
    feedback_notes = models.TextField(_("Notas de Feedback"), blank=True, help_text=_("Comentarios o feedback recibido"))

    class Meta:
        ordering = ['order', 'due_date', 'created_at']
        verbose_name = _("Entregable/Tarea")
        verbose_name_plural = _("Entregables/Tareas")

    def __str__(self):
        due = f" ({_('Vence')}: {self.due_date})" if self.due_date else ""
        order_id = self.order_id if hasattr(self, 'order_id') else 'N/A'
        status_display = self.get_status_display()
        desc_short = (self.description[:27] + '...') if len(self.description) > 30 else self.description
        return f"{_('Entregable')} '{desc_short}' ({status_display}){due} - {_('Pedido')} #{order_id}"

class TransactionType(models.Model):
    """Tipos de transacciones financieras."""
    name = models.CharField(
        _("Nombre Tipo Transacción"), max_length=50, unique=True,
        help_text=_("Ej: Pago Cliente, Reembolso, Gasto Proveedor")
    )
    requires_approval = models.BooleanField(_("Requiere Aprobación"), default=False)

    class Meta:
        verbose_name = _("Tipo de Transacción")
        verbose_name_plural = _("Tipos de Transacciones")
        ordering = ['name']

    def __str__(self):
        return self.name

class PaymentMethod(models.Model):
    """Métodos de pago aceptados."""
    name = models.CharField(
        _("Nombre Método Pago"), max_length=50, unique=True,
        help_text=_("Ej: Transferencia, Tarjeta, PayPal")
    )
    is_active = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Método de Pago")
        verbose_name_plural = _("Métodos de Pago")
        ordering = ['name']

    def __str__(self):
        return f"{self.name}{'' if self.is_active else _(' (Inactivo)')}"

class Invoice(models.Model):
    """Facturas emitidas a clientes."""
    STATUS_CHOICES = [
        ('DRAFT', _('Borrador')), ('SENT', _('Enviada')), ('PAID', _('Pagada')),
        ('PARTIALLY_PAID', _('Parcialmente Pagada')), ('OVERDUE', _('Vencida')),
        ('CANCELLED', _('Cancelada')), ('VOID', _('Anulada Post-Pago')),
    ]
    FINAL_STATUSES = ['PAID', 'CANCELLED', 'VOID']

    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name='invoices',
        help_text=_("Pedido al que corresponde la factura"), verbose_name=_("Pedido")
    )
    invoice_number = models.CharField(
        _("Número Factura"), max_length=50, unique=True, blank=True,
        help_text=_("Número de factura (puede autogenerarse)")
    )
    date = models.DateField(_("Fecha Emisión"), default=datetime.date.today, help_text=_("Fecha de emisión de la factura"))
    due_date = models.DateField(_("Fecha Vencimiento"), help_text=_("Fecha de vencimiento del pago"))
    paid_amount = models.DecimalField(
        _("Monto Pagado"), max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False
    )
    status = models.CharField(
        _("Estado"), max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True
    )
    notes = models.TextField(_("Notas/Términos"), blank=True, help_text=_("Notas o términos de la factura"))

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = _("Factura")
        verbose_name_plural = _("Facturas")

    @property
    def total_amount(self):
        return self.order.total_amount if hasattr(self, 'order') and self.order else Decimal('0.00')
    @property
    def balance_due(self):
        return self.total_amount - self.paid_amount

    def update_paid_amount_and_status(self, trigger_notifications=True):
        """Actualiza montos y estado según pagos. Llama a create_notification si vence."""
        original_status = self.status
        # Usar try-except por si payments no está disponible aún (raro)
        try: total_paid = self.payments.filter(status='COMPLETED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        except Exception: total_paid = Decimal('0.00')
        new_status = self.status; current_total = self.total_amount
        if self.status not in self.FINAL_STATUSES + ['DRAFT']: # No cambiar estados finales o borrador automáticamente
            if total_paid >= current_total and current_total > 0: new_status = 'PAID'
            elif total_paid > 0: new_status = 'PARTIALLY_PAID'
            elif self.due_date and self.due_date < timezone.now().date(): new_status = 'OVERDUE'
            elif self.status == 'OVERDUE' and self.due_date and self.due_date >= timezone.now().date(): new_status = 'SENT' # Volver a SENT si ya no está vencida
            else: new_status = 'SENT' # Estado por defecto si no es final/borrador/pagada/vencida
        status_changed = (new_status != self.status); paid_amount_changed = (total_paid != self.paid_amount)
        if (status_changed or paid_amount_changed) and self.pk:
             Invoice.objects.filter(pk=self.pk).update(paid_amount=total_paid, status=new_status)
             self.paid_amount = total_paid; self.status = new_status # Actualizar instancia
             if trigger_notifications and status_changed and self.status == 'OVERDUE' and hasattr(self, 'order') and self.order.customer:
                 message = f"Recordatorio: La factura {self.invoice_number} para el pedido #{self.order_id} ha vencido."
                 # Llamar a la función global definida más abajo
                 create_notification(self.order.customer.user, message, self)

    def save(self, *args, **kwargs):
        # Autogenerar número de factura
        if not self.pk and not self.invoice_number:
            last_invoice = Invoice.objects.order_by('id').last(); next_id = (last_invoice.id + 1) if last_invoice else 1
            current_year = datetime.date.today().year; self.invoice_number = f"INV-{current_year}-{next_id:04d}"
            while Invoice.objects.filter(invoice_number=self.invoice_number).exists(): next_id +=1; self.invoice_number = f"INV-{current_year}-{next_id:04d}"
        super().save(*args, **kwargs) # Guardar primero

    def __str__(self):
        customer_str = str(self.order.customer) if hasattr(self, 'order') and self.order else 'N/A'
        return f"{_('Factura')} {self.invoice_number} ({self.get_status_display()}) - {customer_str}"

class Payment(models.Model):
    """Registro de un pago asociado a una factura."""
    STATUS_CHOICES = [ ('PENDING', _('Pendiente')), ('COMPLETED', _('Completado')), ('FAILED', _('Fallido')), ('REFUNDED', _('Reembolsado')), ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments', verbose_name=_("Factura"))
    method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, help_text=_("Método utilizado para el pago"), verbose_name=_("Método de Pago"))
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.PROTECT, help_text=_("Tipo de transacción (ej. pago, reembolso)"), verbose_name=_("Tipo Transacción"))
    date = models.DateTimeField(_("Fecha Pago"), default=timezone.now, help_text=_("Fecha y hora en que se registró el pago"))
    amount = models.DecimalField(_("Monto"), max_digits=12, decimal_places=2)
    currency = models.CharField(_("Moneda"), max_length=3, default='EUR')
    status = models.CharField(_("Estado"), max_length=20, choices=STATUS_CHOICES, default='COMPLETED', db_index=True)
    transaction_id = models.CharField(_("ID Transacción Externa"), max_length=100, blank=True, null=True, help_text=_("ID de la transacción externa si aplica"))
    notes = models.TextField(_("Notas"), blank=True, help_text=_("Notas sobre el pago"))

    class Meta:
        ordering = ['-date']
        verbose_name = _("Pago")
        verbose_name_plural = _("Pagos")

    def __str__(self):
        invoice_num = self.invoice.invoice_number if hasattr(self, 'invoice') else 'N/A'
        return f"{_('Pago')} ({self.get_status_display()}) de {self.amount} {self.currency} para {_('Factura')} {invoice_num}"

class CampaignService(models.Model):
    """Relación entre una campaña y un servicio incluido."""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='included_services', verbose_name=_("Campaña"))
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='campaign_assignments', verbose_name=_("Servicio"))
    discount_percentage = models.DecimalField(_("Descuento (%)"), max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text=_("Descuento aplicado a este servicio en la campaña (%)"))
    additional_details = models.TextField(_("Detalles Adicionales"), null=True, blank=True)

    class Meta:
        unique_together = ('campaign', 'service')
        verbose_name = _("Servicio de Campaña")
        verbose_name_plural = _("Servicios de Campañas")

    def __str__(self):
        discount_str = f" ({self.discount_percentage}%)" if self.discount_percentage > 0 else ""
        service_name = self.service.name if hasattr(self, 'service') else 'N/A'
        campaign_name = self.campaign.campaign_name if hasattr(self, 'campaign') else 'N/A'
        return f"{_('Servicio')} {service_name} en {_('Campaña')} {campaign_name}{discount_str}"

class Provider(models.Model):
    """Proveedores o colaboradores externos."""
    name = models.CharField(_("Nombre Proveedor"), max_length=255, unique=True)
    contact_person = models.CharField(_("Persona de Contacto"), max_length=255, null=True, blank=True)
    email = models.EmailField(_("Email"), null=True, blank=True)
    phone = models.CharField(_("Teléfono"), max_length=30, null=True, blank=True)
    services_provided = models.ManyToManyField(
        Service, blank=True, related_name='providers',
        help_text=_("Servicios que ofrece este proveedor"), verbose_name=_("Servicios Ofrecidos")
    )
    rating = models.DecimalField(
        _("Calificación"), max_digits=3, decimal_places=1, default=Decimal('5.0'),
        help_text=_("Calificación interna (1-5)")
    )
    is_active = models.BooleanField(_("Activo"), default=True)
    notes = models.TextField(_("Notas Internas"), blank=True, help_text=_("Notas internas sobre el proveedor"))

    class Meta:
        verbose_name = _("Proveedor")
        verbose_name_plural = _("Proveedores")
        ordering = ['name']

    def __str__(self):
        status = _("[ACTIVO]") if self.is_active else _("[INACTIVO]")
        return f"{self.name} {status}"

class Notification(models.Model):
    """Notificaciones para usuarios."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', verbose_name=_("Usuario"))
    message = models.TextField(_("Mensaje"))
    read = models.BooleanField(_("Leída"), default=False, db_index=True)
    created_at = models.DateTimeField(_("Fecha Creación"), auto_now_add=True)
    link = models.URLField(_("Enlace"), null=True, blank=True, help_text=_("Enlace relevante (ej. a un pedido, tarea)"))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Notificación")
        verbose_name_plural = _("Notificaciones")

    def __str__(self):
        status = _("[Leída]") if self.read else _("[No Leída]")
        username = self.user.username if hasattr(self, 'user') else 'N/A'
        return f"{_('Notificación')} para {username} {status}: {self.message[:50]}..."

class AuditLog(models.Model):
    """Registro de auditoría de acciones importantes."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs', verbose_name=_("Usuario")
    )
    action = models.CharField(
        _("Acción"), max_length=255, help_text=_("Descripción de la acción realizada")
    )
    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True, db_index=True)
    details = models.JSONField(
        _("Detalles"), default=dict, blank=True, help_text=_("Detalles adicionales en formato JSON")
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _("Registro de Auditoría")
        verbose_name_plural = _("Registros de Auditoría")

    def __str__(self):
        user_str = self.user.username if self.user else _("Sistema")
        timestamp_str = self.timestamp.strftime('%Y-%m-%d %H:%M') if self.timestamp else 'N/A'
        return f"{timestamp_str} - {user_str}: {self.action}"

# ==============================================================================
# ---------------------- MÉTODOS AÑADIDOS AL MODELO USER ----------------------
# ==============================================================================

UserModel = get_user_model()

# --- Propiedades y Métodos para Roles (Con Caché) ---
@property
def primary_role(self):
    cache_key = '_primary_role_cache'
    if not hasattr(self, cache_key):
        role = None
        try:
            profile = getattr(self, 'profile', None)
            if profile and profile.primary_role and profile.primary_role.is_active:
                role = profile.primary_role
        except Exception: pass # Captura genérica por si profile no es UserProfile
        setattr(self, cache_key, role)
    return getattr(self, cache_key)

@property
def primary_role_name(self):
    role = self.primary_role; return role.name if role else None

@property
def get_secondary_active_roles(self):
    cache_key = '_secondary_roles_cache'
    if not hasattr(self, cache_key):
        primary_role_id = None
        try: primary_role_id = self.profile.primary_role_id
        except Exception: pass
        qs = UserRole.objects.none()
        if self.pk:
             qs = UserRole.objects.filter(secondary_assignments__user_id=self.pk, secondary_assignments__is_active=True, is_active=True).distinct()
             if primary_role_id: qs = qs.exclude(id=primary_role_id)
        setattr(self, cache_key, qs)
    return getattr(self, cache_key)

@property
def get_secondary_active_role_names(self):
    return list(self.get_secondary_active_roles.values_list('name', flat=True))

@property
def get_all_active_role_names(self):
    all_roles = set(self.get_secondary_active_role_names)
    p_role_name = self.primary_role_name
    if p_role_name: all_roles.add(p_role_name)
    return list(all_roles)

def has_role(self, role_name):
    if not role_name: return False
    if self.primary_role_name == role_name: return True
    return role_name in self.get_secondary_active_role_names

def is_dragon(self):
    # Asegurarse que Roles.DRAGON existe antes de llamar a has_role
    dragon_role_name = getattr(Roles, 'DRAGON', None)
    return self.has_role(dragon_role_name) if dragon_role_name else False

UserModel.add_to_class("primary_role", primary_role)
UserModel.add_to_class("primary_role_name", primary_role_name)
UserModel.add_to_class("get_secondary_active_roles", get_secondary_active_roles)
UserModel.add_to_class("get_secondary_active_role_names", get_secondary_active_role_names)
UserModel.add_to_class("get_all_active_role_names", get_all_active_role_names)
UserModel.add_to_class("has_role", has_role)
UserModel.add_to_class("is_dragon", is_dragon)


# ==============================================================================
# ---------------------- SEÑALES DE LA APLICACIÓN -----------------------------
# ==============================================================================

# --- Señal para crear UserProfile ---
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile_signal(sender, instance, created, **kwargs):
    if created: UserProfile.objects.get_or_create(user=instance)

# --- Señal para crear Customer/Employee ---
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_customer_or_employee_profile_signal(sender, instance, created, **kwargs):
    if created:
        has_employee = Employee.objects.filter(user=instance).exists()
        has_customer = Customer.objects.filter(user=instance).exists()
        if not has_employee and not has_customer:
            if instance.is_staff: Employee.objects.get_or_create(user=instance)
            else: Customer.objects.get_or_create(user=instance)

# --- Señales de Pedidos ---
@receiver(post_save, sender=OrderService)
@receiver(post_delete, sender=OrderService)
def update_order_total_on_service_change_signal(sender, instance, **kwargs):
    if instance.order_id:
        try:
            order = Order.objects.get(pk=instance.order_id)
            order.update_total_amount()
        except Order.DoesNotExist: logger.warning(f"Order {instance.order_id} no encontrada al actualizar total desde OrderService {instance.id}. Posiblemente eliminada.")
        except Exception as e: logger.error(f"Error inesperado actualizando total de Order {instance.order_id} desde OrderService {instance.id}: {e}")

@receiver(pre_save, sender=Order)
def set_order_completion_date_signal(sender, instance, **kwargs):
    original_instance = None
    if instance.pk:
        try: original_instance = Order.objects.get(pk=instance.pk)
        except Order.DoesNotExist: pass
    if not instance.pk or original_instance:
        original_status = original_instance.status if original_instance else None
        if instance.status == 'DELIVERED' and original_status != 'DELIVERED': instance.completed_at = timezone.now()
        elif instance.status != 'DELIVERED' and (original_status == 'DELIVERED' or (not instance.pk and instance.status != 'DELIVERED')): instance.completed_at = None # Limpiar si ya no está entregado
        # elif not instance.pk and instance.status == 'DELIVERED': instance.completed_at = timezone.now() # Cubierto por primer if si status es DELIVERED

# --- Señales de Pagos y Facturas ---
@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def update_invoice_status_on_payment_signal(sender, instance, **kwargs):
    if instance.invoice_id:
        try:
            invoice = Invoice.objects.select_related('order__customer__user').get(pk=instance.invoice_id) # Optimizar
            invoice.update_paid_amount_and_status()
        except Invoice.DoesNotExist: logger.warning(f"Invoice {instance.invoice_id} no encontrada al actualizar estado desde Payment {instance.id}. Posiblemente eliminada.")
        except Exception as e: logger.error(f"Error inesperado actualizando estado de Invoice {instance.invoice_id} desde Payment {instance.id}: {e}")

# --- Helper Función Global para Notificaciones ---
def create_notification(user_recipient, message, link_obj=None):
    UserModelForCheck = get_user_model()
    if not user_recipient or not isinstance(user_recipient, UserModelForCheck): return
    link_url = None
    if link_obj and hasattr(link_obj, 'pk') and link_obj.pk:
        try:
            model_name = link_obj.__class__.__name__.lower(); app_label = link_obj._meta.app_label
            link_url = reverse(f'admin:{app_label}_{model_name}_change', args=[link_obj.pk])
        except Exception: pass # Silenciar error si URL no se puede generar
    try: Notification.objects.create(user=user_recipient, message=message, link=link_url)
    except Exception as e: logger.error(f"Error al crear notificación para {user_recipient.username}: {e}")

# --- Señales de Auditoría ---
def log_action(instance, action_verb, details_dict=None):
    user = get_current_user(); model_name = instance.__class__.__name__
    try: instance_str = str(instance)
    except Exception: instance_str = f"ID {instance.pk}" if instance.pk else "objeto no guardado/eliminado"
    action_str = f"{model_name} {action_verb}: {instance_str}"
    log_details = {'model': model_name, 'pk': instance.pk if instance.pk else None, 'representation': instance_str}
    if details_dict: log_details.update(details_dict)
    try: AuditLog.objects.create(user=user, action=action_str, details=log_details)
    except Exception as e: logger.error(f"Error al crear AuditLog: {e}")

AUDITED_MODELS = [Order, Invoice, Deliverable, Customer, Employee, Service, Payment, Provider, Campaign, UserProfile, UserRoleAssignment]

@receiver(post_save)
def audit_log_save_signal(sender, instance, created, **kwargs):
    if sender in AUDITED_MODELS:
        action_verb = "Creado" if created else "Actualizado"; details = {}
        if hasattr(instance, 'status'): status_val = getattr(instance, 'status', None); display_method = getattr(instance, 'get_status_display', None); details['status'] = display_method() if callable(display_method) else status_val
        if isinstance(instance, UserProfile) and instance.primary_role: details['primary_role'] = instance.primary_role.name
        if isinstance(instance, UserRoleAssignment) and instance.role: details['role'] = instance.role.name; details['assignment_active'] = instance.is_active
        log_action(instance, action_verb, details)

@receiver(post_delete)
def audit_log_delete_signal(sender, instance, **kwargs):
    if sender in AUDITED_MODELS: log_action(instance, "Eliminado")

# --- Señales de Notificación ---
@receiver(post_save, sender=Deliverable)
def notify_deliverable_signal(sender, instance, created, **kwargs):
    original_instance = None; assigned_employee_changed = False; status_changed = False
    current_assigned_employee_id = instance.assigned_employee_id # Cachear ID actual

    if not created and instance.pk:
        try: original_instance = Deliverable.objects.select_related('assigned_employee').get(pk=instance.pk)
        except Deliverable.DoesNotExist: pass

    if original_instance:
         if current_assigned_employee_id != original_instance.assigned_employee_id: assigned_employee_changed = True
         original_status = original_instance.status
         if original_status != instance.status: status_changed = True
    elif created: # Si es nuevo
        if current_assigned_employee_id: assigned_employee_changed = True # Se asignó al crear
        status_changed = True # El status siempre cambia de 'nada' a 'PENDING' (o lo que sea)
    else: original_status = None; status_changed = True # Caso raro: sin pk pero no creado

    # Notificar nueva asignación
    if assigned_employee_changed and instance.assigned_employee:
        if hasattr(instance.assigned_employee, 'user') and instance.assigned_employee.user:
            message = f"Te han asignado la tarea '{instance.description[:50]}...' del Pedido #{instance.order_id}"
            create_notification(instance.assigned_employee.user, message, instance)
        else: logger.warning(f"Empleado asignado ID {current_assigned_employee_id} a Deliverable {instance.id} no tiene usuario.")

    # Notificar cambio de estado relevante
    if status_changed:
        recipient, message = None, None
        try:
            # Solo notificar cambios de estado específicos, no todos
            notify_states = ['PENDING_APPROVAL', 'REVISION_REQUESTED', 'REQUIRES_INFO', 'APPROVED', 'COMPLETED'] # Estados que podrían generar notificación
            if instance.status in notify_states:
                if instance.status == 'PENDING_APPROVAL' and instance.order.customer:
                     recipient = instance.order.customer.user
                     message = f"La tarea '{instance.description[:50]}...' del Pedido #{instance.order_id} está lista para tu aprobación."
                elif instance.status in ['REVISION_REQUESTED', 'REQUIRES_INFO'] and instance.assigned_employee and hasattr(instance.assigned_employee, 'user'):
                     recipient = instance.assigned_employee.user
                     message = f"La tarea '{instance.description[:50]}...' (Pedido #{instance.order_id}) requiere tu atención: {instance.get_status_display()}."
                elif instance.status == 'APPROVED' and instance.assigned_employee and hasattr(instance.assigned_employee, 'user'):
                      recipient = instance.assigned_employee.user # Notificar al empleado que se aprobó? O al cliente?
                      message = f"La tarea '{instance.description[:50]}...' (Pedido #{instance.order_id}) ha sido aprobada."
                # Añadir más lógica según necesites
            if recipient and message: create_notification(recipient, message, instance)
        except Order.DoesNotExist: logger.warning(f"Orden {instance.order_id} no encontrada al notificar sobre Deliverable {instance.id}")
        except Exception as e: logger.error(f"Error procesando notificación para Deliverable {instance.id}: {e}")