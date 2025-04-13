# api/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, DurationField, Avg, DecimalField
from django_countries.fields import CountryField
from django.urls import reverse # Para generar links en notificaciones
from django.conf import settings # Para construir URLs absolutas si es necesario
import datetime
from decimal import Decimal

# --- Helper para obtener usuario actual (requiere django-crum) ---
try:
    from crum import get_current_user
except ImportError:
    get_current_user = lambda: None # Fallback si crum no está instalado
    print("ADVERTENCIA: django-crum no está instalado. Los AuditLogs no registrarán el usuario.")

# ==============================================================================
# ---------------------- MODELOS DE LA APLICACIÓN -----------------------------
# ==============================================================================

# ---------------------- Formularios ----------------------
class Form(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Formulario"
        verbose_name_plural = "Formularios"

    def __str__(self):
        return self.name

class FormQuestion(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0, help_text="Orden de aparición en el formulario")
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['form', 'order']
        verbose_name = "Pregunta de Formulario"
        verbose_name_plural = "Preguntas de Formularios"

    def __str__(self):
        return f"{self.form.name} - P{self.order}: {self.question_text[:50]}..."

class FormResponse(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='form_responses')
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE, related_name='responses')
    text = models.TextField(help_text="Respuesta proporcionada por el cliente")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'form', 'question')
        ordering = ['created_at']
        verbose_name = "Respuesta de Formulario"
        verbose_name_plural = "Respuestas de Formularios"

    def __str__(self):
        return f"Respuesta de {self.customer} a {self.question}"

# ---------------------- Gestión de Clientes ----------------------
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=30, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = CountryField(blank=True, null=True, help_text="País del cliente")
    company_name = models.CharField(max_length=150, blank=True, null=True, help_text="Nombre de la empresa (si aplica)")
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_contact_method = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Teléfono'),
        ('whatsapp', 'WhatsApp'),
        ('other', 'Otro')
    ], null=True, blank=True)
    brand_guidelines = models.FileField(upload_to='customers/brand_guidelines/', null=True, blank=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        display_name = self.company_name or self.user.get_full_name() or self.user.username
        return f"{display_name} ({self.user.email})"

# ---------------------- Gestión de Empleados ----------------------
class JobPosition(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    permissions = models.JSONField(default=dict, blank=True, help_text="Permisos específicos para este puesto (estructura JSON)")

    class Meta:
        verbose_name = "Puesto de Trabajo"
        verbose_name_plural = "Puestos de Trabajo"
        ordering = ['name']

    def __str__(self):
        return self.name

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    hire_date = models.DateField(default=datetime.date.today)
    address = models.TextField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    position = models.ForeignKey(JobPosition, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees')

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ['user__first_name', 'user__last_name']

    @property
    def is_active(self):
        return self.user.is_active

    def __str__(self):
        position_name = self.position.name if self.position else "Sin puesto"
        status = "[ACTIVO]" if self.is_active else "[INACTIVO]"
        return f"{self.user.get_full_name() or self.user.username} ({position_name}) {status}"

# ---------------------- Gestión de Pedidos (Core) ----------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'),
        ('PLANNING', 'Planificación'),
        ('IN_PROGRESS', 'En Progreso'),
        ('QUALITY_CHECK', 'Control de Calidad'),
        ('PENDING_DELIVERY', 'Pendiente Entrega'),
        ('DELIVERED', 'Entregado'), # Estado final "completado"
        ('CANCELLED', 'Cancelado'),
        ('ON_HOLD', 'En Espera'),
    ]
    FINAL_STATUSES = ['DELIVERED', 'CANCELLED'] # Para queries

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders', help_text="Cliente que realiza el pedido")
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_orders', help_text="Empleado responsable principal")
    date_received = models.DateTimeField(auto_now_add=True)
    date_required = models.DateTimeField(help_text="Fecha límite solicitada por el cliente")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True) # Indexar status
    payment_due_date = models.DateTimeField(null=True, blank=True, help_text="Fecha límite para el pago (si aplica)")
    note = models.TextField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=3, help_text="Prioridad (ej. 1=Alta, 5=Baja)") # Cambiar default si 3 es más común
    completed_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="Fecha y hora de finalización (status='DELIVERED')")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False, help_text="Calculado de OrderService. Actualizado automáticamente.")

    class Meta:
        ordering = ['priority', '-date_received'] # Ordenar por prioridad ascendente
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.id} ({self.get_status_display()}) - {self.customer}"

    def update_total_amount(self):
        """Calcula y guarda el monto total basado en los servicios asociados."""
        total = self.services.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total']
        self.total_amount = total if total is not None else Decimal('0.00')
        if self.pk: # Solo guardar si el objeto ya existe en la BD
             Order.objects.filter(pk=self.pk).update(total_amount=self.total_amount) # Evita recursión de señales

# ---------------------- Categorías y Campañas ----------------------
class ServiceCategory(models.Model):
    code = models.CharField(max_length=10, primary_key=True, help_text="Código corto de la categoría (ej. MKT, DEV)")
    name = models.CharField(max_length=100, help_text="Nombre descriptivo de la categoría")

    class Meta:
        verbose_name = "Categoría de Servicio"
        verbose_name_plural = "Categorías de Servicios"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

class Campaign(models.Model):
    campaign_code = models.CharField(max_length=20, primary_key=True)
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateTimeField(help_text="Fecha y hora de inicio de la campaña")
    end_date = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora de fin (opcional)")
    description = models.TextField(null=True, blank=True)
    target_audience = models.JSONField(default=dict, blank=True, help_text="Descripción del público objetivo (JSON)")
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True, help_text="¿La campaña está activa actualmente?")

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Campaña"
        verbose_name_plural = "Campañas"

    def __str__(self):
        status = "[ACTIVA]" if self.is_active else "[INACTIVA]"
        return f"{self.campaign_name} ({self.campaign_code}) {status}"

# ---------------------- Servicios y Precios ----------------------
class Service(models.Model):
    code = models.CharField(max_length=10, primary_key=True, help_text="Código único del servicio (ej. OD001)")
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, related_name='services', help_text="Categoría principal del servicio")
    name = models.CharField(max_length=255, help_text="Nombre descriptivo del servicio")
    is_active = models.BooleanField(default=True, help_text="¿El servicio está activo y disponible para la venta?")
    ventulab = models.BooleanField(default=False, help_text="¿Es un servicio interno o especial de Ventulab?")
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='promoted_services', help_text="Campaña promocional asociada directa (opcional)")
    is_package = models.BooleanField(default=False, help_text="¿Este servicio es un paquete que agrupa otros?")
    is_subscription = models.BooleanField(default=False, help_text="¿Este servicio es una suscripción recurrente?")

    # Campos combinados de serviceDetails
    audience = models.TextField(blank=True, null=True, help_text="Público objetivo principal de este servicio")
    detailed_description = models.TextField(blank=True, null=True, help_text="Descripción más detallada del servicio")
    problem_solved = models.TextField(blank=True, null=True, help_text="Qué problema o necesidad soluciona este servicio")

    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"

    def __str__(self):
        package_indicator = " [Paquete]" if self.is_package else ""
        subscription_indicator = " [Suscripción]" if self.is_subscription else ""
        status = "[ACTIVO]" if self.is_active else "[INACTIVO]"
        return f"{self.name} ({self.code}){package_indicator}{subscription_indicator} {status}"

    def get_current_price(self, currency='EUR'):
        """Obtiene el precio más reciente para una moneda específica."""
        latest_price = self.price_history.filter(currency=currency).order_by('-effective_date').first()
        return latest_price.amount if latest_price else None

class ServiceFeature(models.Model):
    FEATURE_TYPES = [
        ('differentiator', 'Diferenciador'),
        ('benefit', 'Beneficio'),
        ('caracteristicas', 'Características'),
        ('process', 'Proceso'),
        ('result', 'Resultado Esperado'),
    ]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='features')
    feature_type = models.CharField(max_length=20, choices=FEATURE_TYPES, help_text="Tipo de característica")
    description = models.TextField(help_text="Descripción de la característica, beneficio, etc.")

    class Meta:
        ordering = ['service', 'feature_type']
        verbose_name = "Característica de Servicio"
        verbose_name_plural = "Características de Servicios"

    def __str__(self):
        return f"{self.service.code} - {self.get_feature_type_display()}: {self.description[:50]}..."

class Price(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='price_history')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR', help_text="Código ISO 4217 (ej. EUR, USD, CLP, COP)")
    effective_date = models.DateField(default=datetime.date.today, help_text="Fecha desde la que este precio es válido")

    class Meta:
        get_latest_by = 'effective_date'
        ordering = ['service', 'currency', '-effective_date']
        unique_together = ['service', 'currency', 'effective_date'] # Evitar duplicados exactos
        verbose_name = "Precio Histórico"
        verbose_name_plural = "Historial de Precios"

    def __str__(self):
        return f"Precio de {self.service.code} - {self.amount} {self.currency} (desde {self.effective_date})"

# ---------------------- Detalles de la Orden (Servicios y Entregables) ----------------------
class OrderService(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='services')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='order_lines') # Proteger servicio
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Precio unitario en el momento de añadir a la orden")
    note = models.TextField(blank=True, help_text="Notas específicas para este servicio en esta orden")

    class Meta:
        verbose_name = "Servicio del Pedido"
        verbose_name_plural = "Servicios del Pedido"
        ordering = ['order', 'id'] # Ordenar por creación dentro del pedido

    def __str__(self):
        return f"Servicio '{self.service.name}' x{self.quantity} en Pedido #{self.order.id}"

    def save(self, *args, **kwargs):
        # Autocompletar precio si es cero y existe precio base (solo en creación)
        if (self.price is None or self.price == Decimal('0.00')) and not self.pk:
             base_price = self.service.get_current_price(currency='EUR') # Asume EUR o la moneda principal
             if base_price is not None:
                 self.price = base_price
        super().save(*args, **kwargs)
        # La señal post_save/post_delete se encargará de actualizar Order.total_amount

class Deliverable(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('ASSIGNED', 'Asignado'),
        ('IN_PROGRESS', 'En Progreso'),
        ('PENDING_APPROVAL', 'Pendiente Aprobación Cliente'),
        ('PENDING_INTERNAL_APPROVAL', 'Pendiente Aprobación Interna'),
        ('REQUIRES_INFO', 'Requiere Info Adicional'),
        ('REVISION_REQUESTED', 'Revisión Solicitada'),
        ('APPROVED', 'Aprobado'),
        ('COMPLETED', 'Completado'),
        ('REJECTED', 'Rechazado'),
    ]
    FINAL_STATUSES = ['COMPLETED', 'REJECTED'] # Constante para queries

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliverables')
    file = models.FileField(upload_to='deliverables/%Y/%m/', null=True, blank=True, help_text="Archivo entregable (opcional inicialmente)")
    description = models.TextField(help_text="Descripción clara de la tarea o entregable")
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True) # Indexar status
    due_date = models.DateField(null=True, blank=True, help_text="Fecha límite para este entregable")
    assigned_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables')
    assigned_provider = models.ForeignKey('Provider', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables')
    feedback_notes = models.TextField(blank=True, help_text="Comentarios o feedback recibido")

    class Meta:
        ordering = ['order', 'due_date', 'created_at']
        verbose_name = "Entregable/Tarea"
        verbose_name_plural = "Entregables/Tareas"

    def __str__(self):
        due = f" (Vence: {self.due_date})" if self.due_date else ""
        return f"Entregable '{self.description[:30]}...' ({self.get_status_display()}){due} - Pedido #{self.order.id}"

# ---------------------- Gestión de Pagos ----------------------
class TransactionType(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Ej: Pago Cliente, Reembolso, Gasto Proveedor")
    requires_approval = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Tipo de Transacción"
        verbose_name_plural = "Tipos de Transacciones"
        ordering = ['name']

    def __str__(self):
        return self.name

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="Ej: Transferencia, Tarjeta, PayPal")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"
        ordering = ['name']

    def __str__(self):
        return f"{self.name}{'' if self.is_active else ' (Inactivo)'}"

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('SENT', 'Enviada'),
        ('PAID', 'Pagada'),
        ('PARTIALLY_PAID', 'Parcialmente Pagada'),
        ('OVERDUE', 'Vencida'),
        ('CANCELLED', 'Cancelada'),
        ('VOID', 'Anulada Post-Pago'),
    ]
    FINAL_STATUSES = ['PAID', 'CANCELLED', 'VOID']

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='invoices', help_text="Pedido al que corresponde la factura")
    invoice_number = models.CharField(max_length=50, unique=True, blank=True, help_text="Número de factura (puede autogenerarse)")
    date = models.DateField(default=datetime.date.today, help_text="Fecha de emisión de la factura")
    due_date = models.DateField(help_text="Fecha de vencimiento del pago")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', db_index=True)
    notes = models.TextField(blank=True, help_text="Notas o términos de la factura")

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"

    @property
    def total_amount(self):
        """Retorna el monto total del pedido asociado."""
        return self.order.total_amount

    @property
    def balance_due(self):
        """Calcula el saldo pendiente."""
        return self.total_amount - self.paid_amount

    def update_paid_amount_and_status(self, trigger_notifications=True):
        """Actualiza el monto pagado y el estado basado en los pagos asociados."""
        original_status = self.status # Guardar estado antes de calcular
        total_paid = self.payments.filter(status='COMPLETED').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

        new_status = self.status # Empezar con el estado actual
        if self.status not in ['CANCELLED', 'VOID']:
            if total_paid >= self.total_amount and self.total_amount > 0:
                new_status = 'PAID'
            elif total_paid > 0:
                new_status = 'PARTIALLY_PAID'
            elif self.status == 'SENT' and self.due_date and self.due_date < timezone.now().date():
                new_status = 'OVERDUE'
            elif self.status == 'OVERDUE' and self.due_date and self.due_date >= timezone.now().date():
                 new_status = 'SENT'

        status_changed = (new_status != self.status)
        paid_amount_changed = (total_paid != self.paid_amount)

        # Guardar si el monto pagado o el estado cambiaron
        if status_changed or paid_amount_changed:
            self.paid_amount = total_paid
            self.status = new_status
            self.save(update_fields=['paid_amount', 'status'])

            # Disparar notificación si cambió a OVERDUE y el flag está activo
            if trigger_notifications and status_changed and self.status == 'OVERDUE' and self.order.customer:
                 message = f"Recordatorio: La factura {self.invoice_number} para el pedido #{self.order.id} ha vencido."
                 create_notification(self.order.customer.user, message, self)


    def save(self, *args, **kwargs):
        # Autogenerar número de factura si está vacío al crear
        # Hacerlo en pre_save podría ser ligeramente más limpio, pero aquí funciona
        if not self.pk and not self.invoice_number:
            last_invoice = Invoice.objects.order_by('id').last()
            next_id = (last_invoice.id + 1) if last_invoice else 1
            current_year = datetime.date.today().year
            # Asegurarse que el número sea único para el año (más robusto)
            while Invoice.objects.filter(invoice_number=f"INV-{current_year}-{next_id:04d}").exists():
                next_id +=1
            self.invoice_number = f"INV-{current_year}-{next_id:04d}"

        # Evitar llamar a update_paid_amount_and_status desde save para no causar bucles si se llama desde señal
        # La lógica de estado se maneja principalmente por la señal del pago
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Factura {self.invoice_number} ({self.get_status_display()}) - {self.order.customer}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
        ('REFUNDED', 'Reembolsado'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, help_text="Método utilizado para el pago")
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.PROTECT, help_text="Tipo de transacción (ej. pago, reembolso)")
    date = models.DateTimeField(default=timezone.now, help_text="Fecha y hora en que se registró el pago")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED', db_index=True) # Indexar
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID de la transacción externa si aplica")
    notes = models.TextField(blank=True, help_text="Notas sobre el pago")

    class Meta:
        ordering = ['-date']
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

    def __str__(self):
        return f"Pago ({self.get_status_display()}) de {self.amount} {self.currency} para Factura {self.invoice.invoice_number}"

# ---------------------- Campañas y Servicios Asociados ----------------------
class CampaignService(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='included_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='campaign_assignments')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Descuento aplicado a este servicio en la campaña (%)")
    additional_details = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('campaign', 'service')
        verbose_name = "Servicio de Campaña"
        verbose_name_plural = "Servicios de Campañas"

    def __str__(self):
        discount_str = f" ({self.discount_percentage}%)" if self.discount_percentage > 0 else ""
        return f"Servicio {self.service.name} en Campaña {self.campaign.campaign_name}{discount_str}"

# ---------------------- Proveedores y Colaboradores ----------------------
class Provider(models.Model):
    name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    services_provided = models.ManyToManyField(Service, blank=True, related_name='providers', help_text="Servicios que ofrece este proveedor")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('5.0'), help_text="Calificación interna (1-5)")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Notas internas sobre el proveedor")

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['name']

    def __str__(self):
        status = "[ACTIVO]" if self.is_active else "[INACTIVO]"
        return f"{self.name} {status}"

# ---------------------- Mejoras Adicionales (Auditoría, Notificaciones) ----------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    read = models.BooleanField(default=False, db_index=True) # Indexar para búsquedas rápidas de no leídas
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(null=True, blank=True, help_text="Enlace relevante (ej. a un pedido, tarea)")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        status = "[Leída]" if self.read else "[No Leída]"
        return f"Notificación para {self.user.username} {status}: {self.message[:50]}..."

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs') # Permitir acciones del sistema
    action = models.CharField(max_length=255, help_text="Descripción de la acción realizada") # Aumentar longitud
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True) # Indexar para búsquedas por fecha
    details = models.JSONField(default=dict, blank=True, help_text="Detalles adicionales en formato JSON")
    # Opcional: Enlace genérico al objeto afectado
    # content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    # object_id = models.PositiveIntegerField(null=True, blank=True)
    # content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"

    def __str__(self):
        user_str = self.user.username if self.user else "Sistema"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {user_str}: {self.action}"


# ==============================================================================
# ---------------------- SEÑALES DE LA APLICACIÓN -----------------------------
# ==============================================================================

# ---------------------- Señales de Perfil ----------------------
@receiver(post_save, sender=User)
def create_user_profile_signal(sender, instance, created, **kwargs):
    """Crea perfil Customer o Employee al crear un User."""
    if created:
        if not hasattr(instance, 'employee_profile') and not hasattr(instance, 'customer_profile'):
            if hasattr(instance, 'is_staff') and instance.is_staff:
                Employee.objects.get_or_create(user=instance) # Usar get_or_create por si acaso
            else:
                Customer.objects.get_or_create(user=instance)


# ---------------------- Señales de Pedidos ----------------------
@receiver(post_save, sender=OrderService)
@receiver(post_delete, sender=OrderService)
def update_order_total_on_service_change_signal(sender, instance, **kwargs):
    """Actualiza Order.total_amount cuando se añade/elimina/guarda un OrderService."""
    if hasattr(instance, 'order') and instance.order:
        instance.order.update_total_amount()

@receiver(pre_save, sender=Order)
def set_order_completion_date_signal(sender, instance, **kwargs):
    """Establece Order.completed_at cuando status pasa a DELIVERED."""
    original_instance = None
    if instance.pk:
        try:
            original_instance = Order.objects.get(pk=instance.pk)
        except Order.DoesNotExist: pass

    if not instance.pk or original_instance:
        original_status = original_instance.status if original_instance else None
        if instance.status == 'DELIVERED' and original_status != 'DELIVERED':
            instance.completed_at = timezone.now()
        elif instance.status != 'DELIVERED' and original_status == 'DELIVERED':
             instance.completed_at = None
        elif not instance.pk and instance.status == 'DELIVERED':
            instance.completed_at = timezone.now()


# ---------------------- Señales de Pagos y Facturas ----------------------
@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def update_invoice_status_on_payment_signal(sender, instance, **kwargs):
    """Actualiza Invoice.paid_amount y status cuando se guarda/elimina un Payment."""
    # Se recalcula siempre para simplificar la lógica de "estaba completado?"
    if hasattr(instance, 'invoice') and instance.invoice:
        instance.invoice.update_paid_amount_and_status(trigger_notifications=True)


# ---------------------- Señales de Auditoría ----------------------
def log_action(instance, action_verb, details_dict=None):
    """Helper: Crea entradas de AuditLog."""
    user = get_current_user()
    model_name = instance.__class__.__name__
    action_str = f"{model_name} {action_verb}: {str(instance)}"
    log_details = {
        'model': model_name,
        'pk': instance.pk if instance.pk else None, # Manejar caso de borrado donde pk puede no estar
        'representation': str(instance),
    }
    if details_dict: log_details.update(details_dict)
    AuditLog.objects.create(user=user, action=action_str, details=log_details)

# Lista de modelos a auditar
AUDITED_MODELS = [Order, Invoice, Deliverable, Customer, Employee, Service, Payment, Provider, Campaign]

@receiver(post_save)
def audit_log_save_signal(sender, instance, created, **kwargs):
    """Registra creación/actualización para modelos auditados."""
    if sender in AUDITED_MODELS:
        action_verb = "Creado" if created else "Actualizado"
        details = {}
        if hasattr(instance, 'status'):
             details['status'] = instance.get_status_display() if hasattr(instance, 'get_status_display') else instance.status
        log_action(instance, action_verb, details)

@receiver(post_delete)
def audit_log_delete_signal(sender, instance, **kwargs):
    """Registra eliminación para modelos auditados."""
    if sender in AUDITED_MODELS:
        log_action(instance, "Eliminado")


# ---------------------- Señales de Notificación ----------------------
def create_notification(user_recipient, message, link_obj=None):
    """Helper: Crea notificaciones."""
    if not user_recipient or not isinstance(user_recipient, User): return
    link_url = None
    if link_obj:
        try:
            model_name = link_obj.__class__.__name__.lower()
            app_label = link_obj._meta.app_label
            link_url = reverse(f'admin:{app_label}_{model_name}_change', args=[link_obj.pk])
        except Exception: pass # Ignorar si no se puede generar link
    Notification.objects.create(user=user_recipient, message=message, link=link_url)

@receiver(post_save, sender=Deliverable)
def notify_deliverable_signal(sender, instance, created, **kwargs):
    """Notifica sobre asignación o cambios de estado de Deliverable."""
    original_instance = None
    if not created and instance.pk:
        try: original_instance = Deliverable.objects.get(pk=instance.pk)
        except Deliverable.DoesNotExist: pass

    # Notificar Asignación
    assigned_employee_changed = False
    if original_instance:
         if instance.assigned_employee != original_instance.assigned_employee: assigned_employee_changed = True
    elif created and instance.assigned_employee: assigned_employee_changed = True

    if assigned_employee_changed and instance.assigned_employee:
        message = f"Te han asignado la tarea '{instance.description[:50]}...' del Pedido #{instance.order.id}"
        create_notification(instance.assigned_employee.user, message, instance)

    # Notificar Cambio de Estado
    status_changed = False
    original_status = original_instance.status if original_instance else None
    if original_status != instance.status: status_changed = True

    if status_changed:
        recipient, message = None, None
        if instance.status == 'PENDING_APPROVAL' and instance.order.customer:
             recipient = instance.order.customer.user
             message = f"La tarea '{instance.description[:50]}...' del Pedido #{instance.order.id} está lista para tu aprobación."
        elif instance.status in ['REVISION_REQUESTED', 'REQUIRES_INFO'] and instance.assigned_employee:
             recipient = instance.assigned_employee.user
             message = f"La tarea '{instance.description[:50]}...' (Pedido #{instance.order.id}) ahora está en estado: {instance.get_status_display()}."
        # ... (añadir más casos) ...
        if recipient and message: create_notification(recipient, message, instance)

# La notificación de factura vencida se maneja dentro de Invoice.update_paid_amount_and_status