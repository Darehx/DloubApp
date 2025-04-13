from django.test import TestCase
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from .models import Customer, Employee, create_user_profile, Service

class CustomerModelTest(TestCase):
    def setUp(self):
        # Desconectar la señal post_save para evitar la creación automática de perfiles
        post_save.disconnect(receiver=create_user_profile, sender=User)
        self.user = User.objects.create_user(
            username=f'testuser_{self._testMethodName}',
            email=f'testuser_{self._testMethodName}@example.com',
            password='testpassword'
        )

        # Crear un cliente de prueba
        self.customer = Customer.objects.create(
            user=self.user,
            phone='123-456-7890',
            address='123 Test Street'
        )

    def tearDown(self):
        # Reconectar la señal post_save después de cada prueba
        post_save.connect(receiver=create_user_profile, sender=User)

from .serializers import OrderSerializer

class OrderSerializerTest(TestCase):
    def setUp(self):
        # Desconectar la señal post_save para evitar la creación automática de perfiles
        post_save.disconnect(receiver=create_user_profile, sender=User)

        # Crear un usuario de prueba
        self.user = User.objects.create_user(
            username=f'testuser_{self._testMethodName}',
            email=f'testuser_{self._testMethodName}@example.com',
            password='testpassword'
        )

        # Crear un cliente de prueba
        self.customer = Customer.objects.create(
            user=self.user,
            phone='123-456-7890',
            address='123 Test Street'
        )

        # Crear un servicio de prueba
        self.service = Service.objects.create(
            code='TEST',
            name='Test Service'
        )

        # Datos para el serializer
        self.order_data = {
            'customer': self.customer.id,
            'date_required': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
            'services': [
                {
                    'service': self.service.code,
                    'quantity': 2,
                    'price': 100.00
                }
            ]
        }

    def tearDown(self):
        # Reconectar la señal post_save después de cada prueba
        post_save.connect(receiver=create_user_profile, sender=User)

    def test_order_serializer_valid_data(self):
        serializer = OrderSerializer(data=self.order_data)
        self.assertTrue(serializer.is_valid())

    def test_order_serializer_create_order(self):
        serializer = OrderSerializer(data=self.order_data)
        self.assertTrue(serializer.is_valid())
        order = serializer.save()

        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.services.count(), 1)
        self.assertEqual(order.services.first().service, self.service)
        self.assertEqual(order.services.first().quantity, 2)
        self.assertEqual(order.services.first().price, 100.00)

    def test_customer_creation(self):
        # Verificar que el cliente se creó correctamente
        self.assertTrue(isinstance(self.customer, Customer))
        self.assertEqual(self.customer.__str__(), f"{self.user.get_full_name()} - {self.user.email}")

    def test_customer_fields(self):
        # Verificar los valores de los campos del cliente
        self.assertEqual(self.customer.phone, '123-456-7890')
        self.assertEqual(self.customer.address, '123 Test Street')

    def test_customer_user_relationship(self):
        # Verificar la relación entre el cliente y el usuario
        self.assertEqual(self.customer.user.username, f'testuser_{self._testMethodName}')
        self.assertEqual(self.customer.user.email, f'testuser_{self._testMethodName}@example.com')
        self.assertEqual(self.customer.user.email, f'testuser_{self._testMethodName}@example.com')

import datetime
from .models import Order

class OrderModelTest(TestCase):
    def setUp(self):
        # Desconectar la señal post_save para evitar la creación automática de perfiles
        post_save.disconnect(receiver=create_user_profile, sender=User)

        # Crear un usuario de prueba
        self.user = User.objects.create_user(
            username=f'testuser_{self._testMethodName}',
            email=f'testuser_{self._testMethodName}@example.com',
            password='testpassword'
        )

        # Crear un cliente de prueba
        self.customer = Customer.objects.create(
            user=self.user,
            phone='123-456-7890',
            address='123 Test Street'
        )

        #Crear un pedido de prueba
        self.order = Order.objects.create(
            customer = self.customer,
            date_required = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        )

    def tearDown(self):
        # Reconectar la señal post_save después de cada prueba
        post_save.connect(receiver=create_user_profile, sender=User)

    def test_order_creation(self):
        # Verificar que el pedido se creó correctamente
        self.assertTrue(isinstance(self.order, Order))
class ServiceModelTest(TestCase):
    def setUp(self):
        # Desconectar la señal post_save para evitar la creación automática de perfiles
        post_save.disconnect(receiver=create_user_profile, sender=User)

        # Crear un servicio de prueba
        self.service = Service.objects.create(
            code='TEST',
            name='Test Service',
            is_active=True,
            ventulab=False
        )

    def tearDown(self):
        # Reconectar la señal post_save después de cada prueba
        post_save.connect(receiver=create_user_profile, sender=User)

    def test_service_creation(self):
        # Verificar que el servicio se creó correctamente
        self.assertTrue(isinstance(self.service, Service))
        self.assertEqual(self.service.__str__(), "TEST - Test Service")

    def test_service_fields(self):
        # Verificar los valores de los campos del servicio
        self.assertEqual(self.service.code, 'TEST')
        self.assertEqual(self.service.name, 'Test Service')
        self.assertEqual(self.service.is_active, True)
        self.assertEqual(self.service.ventulab, False)

from .models import Campaign, JobPosition, Employee

class EmployeeModelTest(TestCase):
    def setUp(self):
        # Desconectar la señal post_save para evitar la creación automática de perfiles
        post_save.disconnect(receiver=create_user_profile, sender=User)

        # Crear un puesto de trabajo de prueba
        self.job_position = JobPosition.objects.create(
            name='Test Position',
            description='Test Description'
        )

        # Crear un usuario de prueba
        self.user = User.objects.create_user(
            username=f'testuser_{self._testMethodName}',
            email=f'testuser_{self._testMethodName}@example.com',
            password='testpassword'
        )

        # Crear un empleado de prueba
        self.employee = Employee.objects.create(
            user=self.user,
            position=self.job_position,
            salary=50000.00,
            address='456 Employee Street'
        )

    def tearDown(self):
        # Reconectar la señal post_save después de cada prueba
        post_save.connect(receiver=create_user_profile, sender=User)

    def test_employee_creation(self):
        # Verificar que el empleado se creó correctamente
        self.assertTrue(isinstance(self.employee, Employee))
        self.assertEqual(self.employee.__str__(), f"{self.user.get_full_name()} - {self.job_position}")

    def test_employee_fields(self):
        # Verificar los valores de los campos del empleado
        self.assertEqual(self.employee.position, self.job_position)
        self.assertEqual(self.employee.salary, 50000.00)
        self.assertEqual(self.employee.address, '456 Employee Street')
