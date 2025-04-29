# api/serializers/finances.py
"""
Serializers para Facturas, Pagos, Métodos de Pago y Tipos de Transacción.
"""
from decimal import Decimal
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Importar modelos necesarios
from ..models import PaymentMethod, TransactionType, Invoice, Payment, Order

class PaymentMethodSerializer(serializers.ModelSerializer):
    """ Serializer para Métodos de Pago. """
    class Meta:
        model = PaymentMethod
        fields = '__all__' # ['id', 'name', 'is_active']

class TransactionTypeSerializer(serializers.ModelSerializer):
    """ Serializer para Tipos de Transacción. """
    class Meta:
        model = TransactionType
        fields = '__all__' # ['id', 'name', 'requires_approval']

class InvoiceBasicSerializer(serializers.ModelSerializer):
    """ Serializer básico para listas de facturas. """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    customer_name = serializers.CharField(source='order.customer.__str__', read_only=True) # Asume __str__ en Customer

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'customer_name', 'date', 'due_date',
            'status', 'status_display', 'total_amount', 'paid_amount', 'balance_due'
        ]
        read_only_fields = fields # Solo lectura

class PaymentReadSerializer(serializers.ModelSerializer):
    """ Serializer para MOSTRAR detalles de un pago. """
    method_name = serializers.CharField(source='method.name', read_only=True)
    transaction_type_name = serializers.CharField(source='transaction_type.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'invoice_number', 'method', 'method_name',
            'transaction_type', 'transaction_type_name', 'date', 'amount',
            'currency', 'status', 'status_display', 'transaction_id', 'notes'
        ]
        read_only_fields = fields

class PaymentCreateSerializer(serializers.ModelSerializer):
    """ Serializer para CREAR un nuevo pago. """
    invoice = serializers.PrimaryKeyRelatedField(
         queryset=Invoice.objects.exclude(status__in=getattr(Invoice, 'FINAL_STATUSES', ['PAID', 'CANCELLED', 'VOID'])) # Excluir facturas finales
    )
    method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.filter(is_active=True))
    transaction_type = serializers.PrimaryKeyRelatedField(queryset=TransactionType.objects.all())

    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'method', 'transaction_type', 'date', # Añadir date aquí si el usuario lo puede definir
            'amount', 'currency', 'status', 'transaction_id', 'notes'
        ]
        read_only_fields = ['id']

    def validate_amount(self, value):
        if value <= Decimal('0.00'):
             raise ValidationError(_("El monto del pago debe ser positivo."))
        return value

    def validate(self, data):
        invoice = data['invoice']
        amount = data['amount']
        # Usar la property balance_due si existe y es confiable
        if hasattr(invoice, 'balance_due') and amount > invoice.balance_due:
             raise ValidationError(
                 {'amount': _(f"El monto del pago ({amount}) excede el balance pendiente ({invoice.balance_due}).")}
             )
        # Si no, calcular balance manualmente (menos ideal)
        # balance = invoice.total_amount - invoice.paid_amount
        # if amount > balance:
        #     raise ValidationError(...)
        return data


class InvoiceSerializer(serializers.ModelSerializer):
    """ Serializer detallado para ver/crear/actualizar una Factura. """
    # Campos legibles
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.CharField(source='order.customer.__str__', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payments = PaymentReadSerializer(many=True, read_only=True) # Pagos asociados

    # Campo para escribir (FK a Order)
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), # Podrías filtrar órdenes que aún no tienen factura
        write_only=True,
        required=True
    )

    class Meta:
        model = Invoice
        fields = [
            'id', 'order', 'order_id', 'customer_name', 'invoice_number', 'date',
            'due_date', 'status', 'status_display', 'total_amount', 'paid_amount',
            'balance_due', 'notes', 'payments'
        ]
        read_only_fields = [
            'id', 'order_id', 'customer_name', 'invoice_number', # Autogenerado
            'paid_amount', 'status_display', 'total_amount', 'balance_due', 'payments'
        ]
        # 'order' es write_only por definición aquí