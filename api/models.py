from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone # Importar timezone
from django.db.models import Sum, F, ExpressionWrapper, DurationField, Avg # Para cálculos
from django_countries.fields import CountryField # Importar CountryField
import datetime

# ---------------------- Señales para Perfiles ----------------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Evitar error si se crea un superusuario sin perfil directo
        if not hasattr(instance, 'employee_profile') and not hasattr(instance, 'customer_profile'):
            if hasattr(instance, 'is_staff') and instance.is_staff:
                Employee.objects.create(user=instance)
            else:
                Customer.objects.create(user=instance)

# ---------------------- Formularios (Sin cambios respecto a tu versión) ----------------------
class Form(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class FormQuestion(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.form.name} - Pregunta {self.order}"

class FormResponse(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='form_responses')
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'form', 'question')
        ordering = ['created_at']

    def __str__(self):
        return f"Respuesta de {self.customer} a {self.question}"

# ---------------------- Gestión de Clientes ----------------------
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = CountryField(blank=True, null=True, help_text="País del cliente (formato ISO 3166-1 alpha-2)") # Usando django-countries
    company_name = models.CharField(max_length=150, blank=True, null=True, help_text="Nombre de la empresa (si aplica)")
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_contact_method = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('other', 'Other')
    ], null=True, blank=True)
    brand_guidelines = models.FileField(upload_to='brand_guidelines/', null=True, blank=True)

    def __str__(self):
        display_name = self.company_name or self.user.get_full_name() or self.user.username
        return f"{display_name} ({self.user.email})"

class CustomerProject(models.Model): # Considerar si este modelo es redundante con Order
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('planning', 'Planificación'),
        ('ongoing', 'En Progreso'),
        ('completed', 'Completado'),
        ('on_hold', 'En Espera'),
        ('cancelled', 'Cancelado')
    ], default='planning')
    form = models.ForeignKey(Form, on_delete=models.SET_NULL, null=True, blank=True)
    moodboard = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Proyecto '{self.name}' para {self.customer}"

# ---------------------- Gestión de Empleados ----------------------
class JobPosition(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    permissions = models.JSONField(default=dict, help_text="Permisos específicos para este puesto")

    def __str__(self):
        return self.name

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    hire_date = models.DateField(default=datetime.date.today)
    address = models.TextField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # Añadir default
    active = models.BooleanField(default=True)
    position = models.ForeignKey(JobPosition, on_delete=models.SET_NULL, null=True, blank=True)
    # La relación con proyectos ahora se maneja mejor a través de Deliverable.assigned_employee
    # projects = models.ManyToManyField(CustomerProject, through='EmployeeAssignment') # Considerar si es necesario mantenerla

    def __str__(self):
        position_name = self.position.name if self.position else "Sin puesto"
        return f"{self.user.get_full_name()} ({position_name})"

# Considerar si EmployeeAssignment sigue siendo necesario si la asignación se hace por Deliverable
class EmployeeAssignment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    project = models.ForeignKey(CustomerProject, on_delete=models.CASCADE)
    role = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.employee} asignado a {self.project} como {self.role}"

# ---------------------- Gestión de Pedidos (Core) ----------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('CONFIRMED', 'Confirmado'), # Cliente acepta
        ('PLANNING', 'Planificación'),
        ('IN_PROGRESS', 'En Progreso'),
        ('QUALITY_CHECK', 'Control de Calidad'),
        ('PENDING_DELIVERY', 'Pendiente Entrega'),
        ('DELIVERED', 'Entregado'), # Estado final "completado"
        ('CANCELLED', 'Cancelado'),
        ('ON_HOLD', 'En Espera'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders') # Evitar borrar cliente si tiene orden
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_orders', help_text="Empleado responsable principal")
    date_received = models.DateTimeField(auto_now_add=True)
    date_required = models.DateTimeField(help_text="Fecha límite solicitada por el cliente")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    payment_due_date = models.DateTimeField(null=True, blank=True, help_text="Fecha límite para el pago (si aplica)")
    note = models.TextField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=1, help_text="Prioridad (ej. 1=Alta, 5=Baja)")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False, help_text="Fecha y hora de finalización (status='DELIVERED')")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, editable=False, help_text="Calculado de OrderService. Actualizado automáticamente.")

    class Meta:
        ordering = ['-priority', '-date_received'] # Ordenar por prioridad y luego fecha

    def __str__(self):
        return f"Orden #{self.id} ({self.get_status_display()}) - {self.customer}"

    def update_total_amount(self):
        """Calcula y guarda el monto total basado en los servicios asociados."""
        total = self.services.aggregate(
            total=Sum(F('price') * F('quantity'))
        )['total']
        self.total_amount = total or 0.00
        # Guardar sin disparar señales recursivas si es posible (update_fields es bueno)
        self.save(update_fields=['total_amount'])

# ---------------------- Servicios y Catálogo ----------------------
class Service(models.Model):
    SERVICE_CODES = [
        ('MKT', 'Marketing Digital'),
        ('DEV', 'Desarrollo Web/App'),
        ('DSGN', 'Diseño Gráfico'),
        ('SMM', 'Gestión Redes Sociales'),
        ('BRND', 'Branding y Estrategia'),
        ('AVP', 'Producción Audiovisual'),
        ('PRNT', 'Servicios de Imprenta'),
        ('CONS', 'Consultoría'),
        ('SEO', 'Optimización SEO'),
        ('SEM', 'Publicidad SEM/PPC'),
        ('CONT', 'Creación de Contenido'),
        # Añade más códigos según necesidad
    ]

    code = models.CharField(max_length=10, primary_key=True, choices=SERVICE_CODES)
    name = models.CharField(max_length=255, blank=True, help_text="Nombre descriptivo del servicio (autocompletado si está vacío)")
    is_active = models.BooleanField(default=True)
    ventulab = models.BooleanField(default=False, help_text="¿Es un servicio específico de Ventulab?") # Asumiendo que es relevante
    has_subservices = models.BooleanField(default=False, help_text="¿Este servicio principal tiene sub-servicios detallados?")
    is_subscription = models.BooleanField(default=False, help_text="Marcar si este servicio es una suscripción recurrente")
    # campaign = models.ForeignKey('Campaign', on_delete=models.SET_NULL, null=True, blank=True) # Movido a CampaignService

    def save(self, *args, **kwargs):
        if not self.name:
            name_mapping = dict(self.SERVICE_CODES)
            self.name = name_mapping.get(self.code, f'Servicio {self.code}')
        super().save(*args, **kwargs)

    def __str__(self):
        status = "[ACTIVO]" if self.is_active else "[INACTIVO]"
        return f"{self.name} ({self.code}) {status}"

class SubService(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="subservices")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Costo adicional si se selecciona este subservicio")

    def __str__(self):
        return f"{self.service.name} - {self.name}"

class Price(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='price_history')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR', help_text="Código ISO 4217 (ej. EUR, USD)") # Cambiar default si es necesario
    effective_date = models.DateField(default=datetime.date.today, help_text="Fecha desde la que este precio es válido")

    class Meta:
        get_latest_by = 'effective_date'
        ordering = ['service', '-effective_date']

    def __str__(self):
        return f"Precio de {self.service} - {self.amount} {self.currency} (desde {self.effective_date})"

# ---------------------- Detalles de la Orden (Servicios y Entregables) ----------------------
class OrderService(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='services')
    service = models.ForeignKey(Service, on_delete=models.PROTECT) # Evitar borrar servicio si está en una orden
    # sub_service = models.ForeignKey(SubService, on_delete=models.SET_NULL, null=True, blank=True) # Si necesitas detallar subservicio
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio unitario en el momento de añadir a la orden")
    note = models.TextField(blank=True, help_text="Notas específicas para este servicio en esta orden")

    class Meta:
        verbose_name_plural = "Servicios de la Orden"
        ordering = ['order']

    def __str__(self):
        return f"Servicio '{self.service.name}' x{self.quantity} en {self.order}"

    def save(self, *args, **kwargs):
        # Podrías autocompletar el precio desde Price si no se especifica
        if self.price is None or self.price == 0:
             latest_price = Price.objects.filter(service=self.service).latest()
             if latest_price:
                 self.price = latest_price.amount
        super().save(*args, **kwargs)
        # Disparar actualización del total de la orden (si no usas señal)
        # self.order.update_total_amount()

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
        ('COMPLETED', 'Completado'), # Estado final operativo
        ('REJECTED', 'Rechazado'), # Estado final alternativo
    ]
    FINAL_STATUSES = ['COMPLETED', 'REJECTED'] # Constante para queries

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliverables')
    file = models.FileField(upload_to='deliverables/%Y/%m/', null=True, blank=True, help_text="Archivo entregable (opcional inicialmente)")
    description = models.TextField(help_text="Descripción clara de la tarea o entregable")
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING')
    due_date = models.DateField(null=True, blank=True, help_text="Fecha límite para este entregable")
    assigned_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables')
    assigned_provider = models.ForeignKey('Provider', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_deliverables')
    feedback_notes = models.TextField(blank=True, help_text="Comentarios o feedback recibido")

    class Meta:
        ordering = ['order', 'due_date', 'created_at'] # Ordenar por orden, fecha límite, creación

    def __str__(self):
        due = f" (Vence: {self.due_date})" if self.due_date else ""
        return f"Entregable '{self.description[:30]}...' ({self.get_status_display()}){due} - {self.order}"

# ---------------------- Gestión de Pagos ----------------------
class TransactionType(models.Model):
    name = models.CharField(max_length=50, unique=True) # Ej: Pago Cliente, Reembolso, Gasto Proveedor
    requires_approval = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True) # Ej: Transferencia, Tarjeta, PayPal
    is_active = models.BooleanField(default=True)
    # allowed_currencies = models.JSONField(default=list) # Simplificado, la moneda está en Payment/Invoice

    def __str__(self):
        return self.name

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Borrador'),
        ('SENT', 'Enviada'),
        ('PAID', 'Pagada'),
        ('PARTIALLY_PAID', 'Parcialmente Pagada'),
        ('OVERDUE', 'Vencida'), # Factura pasada de fecha y no pagada completamente
        ('CANCELLED', 'Cancelada'), # Anulada antes de ser pagada
        ('VOID', 'Anulada Post-Pago'), # Anulada después de ser pagada (requiere lógica adicional)
    ]
    FINAL_STATUSES = ['PAID', 'CANCELLED', 'VOID'] # Constante para queries

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='invoices') # Proteger orden
    invoice_number = models.CharField(max_length=50, unique=True, blank=True, help_text="Número de factura (puede autogenerarse)")
    date = models.DateField(default=datetime.date.today)
    due_date = models.DateField()
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    notes = models.TextField(blank=True, help_text="Notas o términos de la factura")

    class Meta:
        ordering = ['-date', '-id']

    @property
    def total_amount(self):
        # Usar el total precalculado de la orden si existe y es fiable
        if hasattr(self.order, 'total_amount') and self.order.total_amount is not None:
            return self.order.total_amount
        # Fallback a calcular desde servicios (menos eficiente)
        return self.order.services.aggregate(total=Sum(F('price') * F('quantity')))['total'] or 0.00

    @property
    def balance_due(self):
        return self.total_amount - self.paid_amount

    def update_paid_amount_and_status(self):
        """Actualiza el monto pagado y el estado basado en los pagos asociados."""
        total_paid = self.payments.filter(status='COMPLETED').aggregate(
            total=Sum('amount')
        )['total'] or 0.00
        self.paid_amount = total_paid

        # Actualizar estado (lógica simplificada)
        if self.status not in ['CANCELLED', 'VOID']: # No cambiar estados finales manualmente establecidos
            if self.paid_amount >= self.total_amount and self.total_amount > 0:
                self.status = 'PAID'
            elif self.paid_amount > 0:
                self.status = 'PARTIALLY_PAID'
            elif self.due_date and self.due_date < timezone.now().date():
                # Solo marcar como vencida si fue enviada y no pagada
                 if self.status == 'SENT':
                    self.status = 'OVERDUE'
            # No revertir a SENT automáticamente si estaba OVERDUE o PARTIALLY_PAID
            elif self.status == 'DRAFT':
                 pass # Mantener DRAFT hasta que se marque como SENT manualmente
            elif self.status not in ['OVERDUE', 'PARTIALLY_PAID']: # Si no es Borrador, Vencida o Parcial
                 self.status = 'SENT' # Asumir enviada si no cumple otras condiciones y no es DRAFT/FINAL

        self.save(update_fields=['paid_amount', 'status'])

    def save(self, *args, **kwargs):
        # Autogenerar número de factura si está vacío (ejemplo simple)
        if not self.invoice_number:
            last_invoice = Invoice.objects.order_by('id').last()
            next_id = (last_invoice.id + 1) if last_invoice else 1
            self.invoice_number = f"INV-{datetime.date.today().year}-{next_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Factura {self.invoice_number} ({self.get_status_display()}) - {self.order.customer}"

class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'), # Ej. esperando confirmación bancaria
        ('COMPLETED', 'Completado'),
        ('FAILED', 'Fallido'),
        ('REFUNDED', 'Reembolsado'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.PROTECT) # Asegura que exista tipo
    date = models.DateTimeField(default=timezone.now) # Usar default=timezone.now
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR') # Coincidir con Price
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID de la transacción externa si aplica")
    notes = models.TextField(blank=True, help_text="Notas sobre el pago")

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Pago ({self.get_status_display()}) de {self.amount} {self.currency} para Factura {self.invoice.invoice_number}"

# ---------------------- Campañas y Marketing ----------------------
class Campaign(models.Model):
    campaign_code = models.CharField(max_length=20, primary_key=True) # Aumentar longitud si es necesario
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    target_audience = models.JSONField(default=dict, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.campaign_name} ({self.campaign_code})"

class CampaignService(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='included_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Descuento aplicado a este servicio en la campaña")
    additional_details = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('campaign', 'service')

    def __str__(self):
        return f"Servicio {self.service.name} en Campaña {self.campaign.campaign_name}"

# ---------------------- Proveedores y Colaboradores ----------------------
class Provider(models.Model):
    name = models.CharField(max_length=255, unique=True)
    contact_person = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    services_provided = models.ManyToManyField(Service, blank=True, related_name='providers', help_text="Servicios que ofrece este proveedor")
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0, help_text="Calificación interna (1-5)")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# ---------------------- Mejoras Adicionales (Auditoría, Notificaciones) ----------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(null=True, blank=True, help_text="Enlace relevante (ej. a una orden, tarea)")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "[Leída]" if self.read else "[No Leída]"
        return f"Notificación para {self.user.username} {status}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Permitir acciones del sistema
    action = models.CharField(max_length=100, help_text="Descripción de la acción realizada")
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, blank=True, help_text="Detalles adicionales en formato JSON")
    related_object_id = models.PositiveIntegerField(null=True, blank=True) # ID del objeto afectado
    # Para enlazar el objeto afectado genéricamente (opcional pero útil)
    # content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    # object_repr = models.CharField(max_length=200, blank=True) # Representación textual del objeto

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.username if self.user else "Sistema"
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} - {user_str}: {self.action}"

# ---------------------- Registro de Señales ----------------------

# Actualizar total de la orden cuando cambia un servicio
@receiver(post_save, sender=OrderService)
@receiver(post_delete, sender=OrderService)
def update_order_total_on_service_change(sender, instance, **kwargs):
     # Asegurarse que la orden todavía existe (importante para post_delete)
     if hasattr(instance, 'order') and instance.order:
        instance.order.update_total_amount()

# Establecer fecha de completado de la orden
@receiver(pre_save, sender=Order)
def set_order_completion_date(sender, instance, **kwargs):
     if instance.pk: # Solo si el objeto ya existe
         try:
             original_instance = Order.objects.get(pk=instance.pk)
             # Si el estado cambia A 'DELIVERED' y antes no lo era
             if original_instance.status != 'DELIVERED' and instance.status == 'DELIVERED':
                 instance.completed_at = timezone.now()
             # Si el estado deja de ser 'DELIVERED' (reversión)
             elif original_instance.status == 'DELIVERED' and instance.status != 'DELIVERED':
                  instance.completed_at = None
         except Order.DoesNotExist:
             # Si se está creando nuevo y el estado inicial es DELIVERED (raro, pero posible)
             if instance.status == 'DELIVERED' and instance.completed_at is None:
                 instance.completed_at = timezone.now()
     elif instance.status == 'DELIVERED': # Si se crea nuevo directamente como DELIVERED
         instance.completed_at = timezone.now()

# Actualizar estado de la factura cuando se guarda/elimina un pago
@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def update_invoice_status_on_payment(sender, instance, **kwargs):
     # Asegurarse que la factura todavía existe
     if hasattr(instance, 'invoice') and instance.invoice:
        instance.invoice.update_paid_amount_and_status()

# Crear precio inicial para un servicio nuevo (ya lo tenías)
@receiver(post_save, sender=Service)
def create_initial_price(sender, instance, created, **kwargs):
    if created and not instance.price_history.exists(): # Solo si no tiene precios aún
        Price.objects.create(
            service=instance,
            amount=100.00, # O un valor por defecto más adecuado, quizás 0
            currency='EUR' # Coincidir con default
        )

# Crear perfil al crear usuario (ya lo tenías, con ajuste para evitar error)
# (El código del perfil está al inicio del archivo)