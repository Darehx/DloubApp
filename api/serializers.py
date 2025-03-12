from rest_framework import serializers
from .models import *
from django.contrib.auth.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# ---------------------- Autenticación ----------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Agregar claims personalizados al token
        token['role'] = 'customer' if hasattr(user, 'customer_profile') else 'employee'
        token['full_name'] = user.get_full_name()

        return token
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

# ---------------------- Formularios ----------------------
class FormSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = '__all__'

class FormQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormQuestion
        fields = '__all__'

class FormResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormResponse
        fields = ['id', 'customer', 'form', 'question', 'text', 'created_at']
        read_only_fields = ['customer', 'created_at']

class FormResponseBulkCreateSerializer(serializers.Serializer):
    customer = serializers.IntegerField()
    form = serializers.IntegerField()
    responses = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(max_length=1000)
        )
    )

    def validate(self, data):
        # Validar que el cliente exista
        try:
            customer = Customer.objects.get(id=data['customer'])
        except Customer.DoesNotExist:
            raise serializers.ValidationError({"customer": "Cliente no encontrado."})

        # Validar que el formulario exista
        try:
            form = Form.objects.get(id=data['form'])
        except Form.DoesNotExist:
            raise serializers.ValidationError({"form": "Formulario no encontrado."})

        # Validar que las preguntas existan
        for response in data['responses']:
            question_id = response.get('question')
            if not question_id:
                raise serializers.ValidationError({"responses": "Falta el campo 'question' en una respuesta."})
            try:
                FormQuestion.objects.get(id=question_id, form=form)
            except FormQuestion.DoesNotExist:
                raise serializers.ValidationError({"responses": f"Pregunta con ID {question_id} no encontrada en el formulario."})

        return data

    def create(self, validated_data):
        customer_id = validated_data['customer']
        form_id = validated_data['form']
        responses_data = validated_data['responses']

        customer = Customer.objects.get(id=customer_id)
        form = Form.objects.get(id=form_id)

        responses = [
            FormResponse(
                customer=customer,
                form=form,
                question_id=response['question'],
                text=response['text']
            ) for response in responses_data
        ]

        return FormResponse.objects.bulk_create(responses)

# ---------------------- Usuarios y Perfiles ----------------------

class JobPositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPosition
        fields = '__all__'


class CustomerCreateSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Customer
        fields = ['user', 'phone', 'address', 'date_of_birth', 'preferred_contact_method']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data.get('password', ''),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', '')
        )
        customer = Customer.objects.create(user=user, **validated_data)
        return customer

class CustomerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['created_at']

class EmployeeCreateSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Employee
        fields = ['user', 'position', 'address', 'salary', 'active']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data.get('password', ''),
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', '')
        )
        employee = Employee.objects.create(user=user, **validated_data)
        return employee

class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    position = serializers.StringRelatedField()

    class Meta:
        model = Employee
        fields = '__all__'
        read_only_fields = ['hire_date']

# ---------------------- Gestión de Pedidos ----------------------
class OrderServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = OrderService
        fields = ['id', 'service', 'service_name', 'quantity', 'price', 'note']

class OrderSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False)
    services = OrderServiceSerializer(many=True, source='services')
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['date_received', 'status']

    def get_status_display(self, obj):
        return obj.get_status_display()

    def create(self, validated_data):
        services_data = validated_data.pop('services', [])
        order = Order.objects.create(**validated_data)

        for service_data in services_data:
            OrderService.objects.create(order=order, **service_data)

        return order

class DeliverableSerializer(serializers.ModelSerializer):
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = Deliverable
        fields = '__all__'
        read_only_fields = ['version', 'approved', 'created_at']

    def get_preview_url(self, obj):
        return obj.file.url if obj.file else None

# ---------------------- Gestión de Pagos ----------------------
class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['date', 'paid_amount']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['date']

# ---------------------- Servicios y Catálogo ----------------------
class SubServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubService
        fields = '__all__'

class ServiceSerializer(serializers.ModelSerializer):
    subservices = SubServiceSerializer(many=True, read_only=True)
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = '__all__'

    def get_current_price(self, obj):
        price = obj.price_set.last()
        return {
            'amount': price.amount if price else 0,
            'currency': price.currency if price else 'USD'
        }

# ---------------------- Campañas ----------------------
class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = '__all__'

class CampaignServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignService
        fields = '__all__'
        
# ---------------------- Gestión de Pagos ----------------------
class TransactionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        fields = '__all__'

# ---------------------- Proveedores y Colaboradores ----------------------
class ProviderSerializer(serializers.ModelSerializer):
    services = serializers.StringRelatedField(many=True)  # Muestra los nombres de los servicios relacionados

    class Meta:
        model = Provider
        fields = '__all__'

# ---------------------- Mejoras Adicionales ----------------------
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at']

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = ['timestamp']
        
        