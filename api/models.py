from django.db import models


# Campaigns Table
class Campaign(models.Model):
    campaign_code = models.CharField(max_length=10, primary_key=True)
    campaign_name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.campaign_name


# Customers Table
class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_contact_method = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# CustomerProjects Table
class CustomerProject(models.Model):
    project_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    project_name = models.CharField(max_length=100)
    project_description = models.TextField(null=True, blank=True)
    project_status = models.CharField(max_length=50, null=True, blank=True)
    form = models.ForeignKey('Form', on_delete=models.CASCADE)

    def __str__(self):
        return self.project_name


# Employees Table
class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    position = models.ForeignKey('JobPosition', on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)
    phone = models.CharField(max_length=20, null=True, blank=True)
    hire_date = models.DateTimeField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    active_status = models.BooleanField(default=True)
    bank_account = models.CharField(max_length=50, null=True, blank=True)
    social_security = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# EmployeeBenefits Table
class EmployeeBenefit(models.Model):
    benefit_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    benefit_type = models.CharField(max_length=50)
    benefit_details = models.TextField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.benefit_type


# EmployeePaymentMethods Table
class EmployeePaymentMethod(models.Model):
    payment_method_id = models.AutoField(primary_key=True)
    method_name = models.CharField(max_length=50)
    details = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.method_name


# EmployeePayments Table
class EmployeePayment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    payment_method = models.ForeignKey(EmployeePaymentMethod, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.payment_id}"


# JobPositions Table
class JobPosition(models.Model):
    position_id = models.AutoField(primary_key=True)
    position_name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.position_name


# Form_Forms Table
class Form(models.Model):
    form_id = models.AutoField(primary_key=True)
    form_name = models.CharField(max_length=255)

    def __str__(self):
        return self.form_name


# Form_Questions Table
class FormQuestion(models.Model):
    question_id = models.AutoField(primary_key=True)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question_text = models.TextField()
    question_type = models.CharField(max_length=50)

    def __str__(self):
        return self.question_text


# Form_Responses Table
class FormResponse(models.Model):
    response_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    form = models.ForeignKey(Form, on_delete=models.CASCADE)
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE)
    response_text = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Response {self.response_id}"


# Investments Table
class Investment(models.Model):
    investment_id = models.AutoField(primary_key=True)
    service_code = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    usd = models.FloatField(null=True, blank=True)
    clp = models.FloatField(null=True, blank=True)
    cop = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name


# Otros modelos restantes (Invoices, Payments, Services, etc.)
# Aquí seguirías el mismo esquema: llaves primarias, relaciones, etc.

# Orders Table
class Order(models.Model):
    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.ForeignKey('OrderStatus', on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Order {self.order_id}"


# OrderStatus Table
class OrderStatus(models.Model):
    status_id = models.AutoField(primary_key=True)
    status_name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.status_name


# OrderDetails Table
class OrderDetail(models.Model):
    order_detail_id = models.AutoField(primary_key=True)
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    service_code = models.CharField(max_length=50)  # Relacionado con un servicio
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Detail {self.order_detail_id} for Order {self.order.order_id}"


# Invoices Table
class Invoice(models.Model):
    invoice_id = models.AutoField(primary_key=True)
    order = models.ForeignKey('Order', on_delete=models.CASCADE)
    invoice_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="Pending")  # Status: Pending, Paid, Overdue
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Invoice {self.invoice_id}"


# Payments Table
class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.CASCADE)
    transaction_type = models.ForeignKey('TransactionType', on_delete=models.CASCADE)
    reference_number = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.payment_id}"


# PaymentMethods Table
class PaymentMethod(models.Model):
    method_id = models.AutoField(primary_key=True)
    method_name = models.CharField(max_length=50)
    details = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.method_name


# TransactionTypes Table
class TransactionType(models.Model):
    transaction_type_id = models.AutoField(primary_key=True)
    type_name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.type_name
