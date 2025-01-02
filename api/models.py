from django.db import models


class Campaigns(models.Model):
    campaign_code = models.CharField(max_length=10, primary_key=True)
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.campaign_name


class Customer(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_contact_method = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('other', 'Other')
    ], null=True, blank=True)


class CustomerProject(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], null=True, blank=True)
    form_id = models.IntegerField()  # Relación pendiente


class Employee(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    hire_date = models.DateField()
    address = models.TextField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)
    position = models.ForeignKey('JobPosition', on_delete=models.SET_NULL, null=True, blank=True)


class JobPosition(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    date_received = models.DateTimeField(auto_now_add=True)
    date_required = models.DateTimeField()
    status = models.ForeignKey('OrderStatus', on_delete=models.CASCADE)
    payment_due_date = models.DateTimeField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)


class OrderStatus(models.Model):
    name = models.CharField(max_length=50)


class PaymentMethod(models.Model):
    name = models.CharField(max_length=50, unique=True)


class Payment(models.Model):
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE)
    method = models.ForeignKey(PaymentMethod, on_delete=models.CASCADE)
    transaction_type_id = models.IntegerField()  # Relación pendiente
    date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)


class Invoice(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)


class Service(models.Model):
    code = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ventulab = models.BooleanField(default=False, help_text="Indica si el servicio es parte del programa Ventulab")
    has_subservices = models.BooleanField(default=False, help_text="Indica si el servicio tiene subservicios asociados")
    campaign = models.ForeignKey('Campaigns', on_delete=models.SET_NULL, null=True, blank=True, help_text="Campaña asociada al servicio")
    def __str__(self):
        return self.name or self.code


class SubService(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="subservices", help_text="Servicio principal al que pertenece este subservicio")
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True, help_text="Descripción del subservicio")
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Costo adicional por el subservicio")

    def __str__(self):
        return self.name



class ServiceFeature(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    feature_type = models.CharField(max_length=50)
    description = models.TextField()


class Package(models.Model):
    name = models.CharField(max_length=100, unique=True)


class PackageDetail(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    details = models.CharField(max_length=255)
    cost = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)


class Provider(models.Model):
    name = models.CharField(max_length=255)
    representative = models.CharField(max_length=255, null=True, blank=True)
    social_name = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    whatsapp = models.CharField(max_length=20, null=True, blank=True)
    website = models.URLField(null=True, blank=True)


class Form(models.Model):
    name = models.CharField(max_length=255, unique=True)


class FormQuestion(models.Model):
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    text = models.TextField()
    type = models.CharField(max_length=50)


class FormResponse(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    text = models.TextField(null=True, blank=True)


class Investment(models.Model):
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=255, null=True, blank=True)
    usd = models.FloatField(null=True, blank=True)
    clp = models.FloatField(null=True, blank=True)
    cop = models.FloatField(null=True, blank=True)


class Price(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    usd = models.FloatField(null=True, blank=True)
    clp = models.FloatField(null=True, blank=True)
    cop = models.FloatField(null=True, blank=True)


class CampaignService(models.Model):
    campaign = models.ForeignKey(Campaigns, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    additional_details = models.TextField(null=True, blank=True)
