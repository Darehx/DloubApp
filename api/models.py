from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# ---------------------- Modelos Base ----------------------
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if hasattr(instance, 'is_staff') and instance.is_staff:
            Employee.objects.create(user=instance)
        else:
            Customer.objects.create(user=instance)

# ---------------------- Formularios ----------------------
class Form(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class FormQuestion(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.form.name} - Pregunta {self.order}"

class FormResponse(models.Model):
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'form', 'question')

    def __str__(self):
        return f"Respuesta de {self.customer} a {self.question}"

# ---------------------- Gestión de Clientes ----------------------
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_contact_method = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('other', 'Other')
    ], null=True, blank=True)
    brand_guidelines = models.FileField(upload_to='brand_guidelines/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.user.email}"

class CustomerProject(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='ongoing')
    form = models.ForeignKey(Form, on_delete=models.SET_NULL, null=True, blank=True)
    moodboard = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer} - {self.name}"

# ---------------------- Gestión de Empleados ----------------------
class JobPosition(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    permissions = models.JSONField(default=dict)

    def __str__(self):
        return self.name

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')
    hire_date = models.DateField()
    address = models.TextField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    position = models.ForeignKey(JobPosition, on_delete=models.SET_NULL, null=True, blank=True)
    projects = models.ManyToManyField(CustomerProject, through='EmployeeAssignment')

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.position}"

class EmployeeAssignment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    project = models.ForeignKey(CustomerProject, on_delete=models.CASCADE)
    role = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.employee} en {self.project}"

# ---------------------- Gestión de Pedidos ----------------------
class Order(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('in_progress', 'En Proceso'),
        ('quality_check', 'Control de Calidad'),
        ('delivered', 'Entregado'),
        ('cancelled', 'Cancelado')
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    date_received = models.DateTimeField(auto_now_add=True)
    date_required = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_due_date = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    priority = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Orden #{self.id} - {self.customer}"

class OrderService(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='services')
    service = models.ForeignKey('Service', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Order Services"

    def __str__(self):
        return f"{self.order} - {self.service}"

class Deliverable(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    file = models.FileField(upload_to='deliverables/')
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Entregable v{self.version} para {self.order}"

# ---------------------- Gestión de Pagos ----------------------
class TransactionType(models.Model):
    name = models.CharField(max_length=50)
    requires_approval = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True)
    allowed_currencies = models.JSONField(default=list)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @property
    def total_amount(self):
        return sum(service.price * service.quantity for service in self.order.services.all())

    def __str__(self):
        return f"Factura #{self.id} - {self.order}"

class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    transaction_type = models.ForeignKey(TransactionType, on_delete=models.PROTECT)
    date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    def __str__(self):
        return f"Pago de {self.amount} {self.currency} para {self.invoice}"

# ---------------------- Servicios y Catálogo ----------------------
class Service(models.Model):
    SERVICE_CODES = [
        ('MKT', 'Marketing'),
        ('DEV', 'Development'),
        ('DSGN', 'Design'),
        ('SMM', 'Social Media'),
        ('BRND', 'Branding'),
        ('AVP', 'Audiovisual Production Services'),
        ('PRNT', 'Imprenta')
    ]
    
    code = models.CharField(max_length=10, primary_key=True, choices=SERVICE_CODES)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    ventulab = models.BooleanField(default=False)
    has_subservices = models.BooleanField(default=False)
    campaign = models.ForeignKey('Campaign', on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.name:
            name_mapping = dict(self.SERVICE_CODES)
            self.name = name_mapping.get(self.code, '')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"

class SubService(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="subservices")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.service} - {self.name}"

class Price(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    effective_date = models.DateField(auto_now_add=True)

    class Meta:
        get_latest_by = 'effective_date'

    def __str__(self):
        return f"{self.service} - {self.amount} {self.currency}"

# ---------------------- Campañas y Marketing ----------------------
class Campaign(models.Model):
    campaign_code = models.CharField(max_length=10, primary_key=True)
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    target_audience = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.campaign_code} - {self.campaign_name}"

class CampaignService(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    additional_details = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.campaign} - {self.service}"

# ---------------------- Proveedores y Colaboradores ----------------------
class Provider(models.Model):
    name = models.CharField(max_length=255)
    representative = models.CharField(max_length=255, null=True, blank=True)
    services = models.ManyToManyField(Service)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)

    def __str__(self):
        return self.name

# ---------------------- Mejoras Adicionales ----------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notificación para {self.user}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.action}"

@receiver(post_save, sender=Service)
def create_initial_price(sender, instance, created, **kwargs):
    if created:
        Price.objects.create(
            service=instance,
            amount=100.00,
            currency='USD'
        )