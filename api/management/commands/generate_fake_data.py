# -*- coding: utf-8 -*-
import random
from datetime import datetime, timedelta
from decimal import Decimal

import faker
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Customer, Employee, Service, Order, OrderService,
    Campaign, PaymentMethod, TransactionType,
    Invoice, Payment, UserRole, UserProfile, UserRoleAssignment,
    Deliverable, Provider, JobPosition
)

fake = faker.Faker('es_ES')
fake.date_between = lambda **kwargs: fake.date_between(start_date='-4m', end_date='today')  # 4 meses de historia
User = get_user_model()

class Command(BaseCommand):
    help = 'Genera datos falsos para la aplicación (enero-abril 2025)'

    def add_arguments(self, parser):
        parser.add_argument('--clientes', type=int, default=50)
        parser.add_argument('--empleados', type=int, default=15)
        parser.add_argument('--pedidos', type=int, default=200)
   

    def handle(self, *args, **options):
        self.stdout.write("Iniciando generación de datos históricos (ene-abr 2025)...")

        with transaction.atomic():
            self.crear_usuarios_y_perfiles()
            self.crear_metodos_pago()
            self.crear_tipos_transaccion()
            self.crear_proveedores()
            self.crear_clientes(options['clientes'])
            self.crear_empleados(options['empleados'])
            self.crear_campanas()
            self.crear_pedidos(options['pedidos'])

            self.crear_facturas_pagos()
            self.crear_entregables()
            self.asignar_roles_secundarios()

        self.stdout.write(self.style.SUCCESS("¡Datos históricos generados exitosamente!"))

    # ... (los métodos crear_roles/usuarios/proveedores se mantienen igual)

    def crear_pedidos(self, cantidad):
        clientes = Customer.objects.all()
        empleados = Employee.objects.all()
        # Filtrar servicios con precios establecidos
        servicios_con_precio = Service.objects.filter(price_history__isnull=False).distinct()
        
        for _ in range(cantidad):
            cliente = random.choice(clientes)
            empleado = random.choice(empleados) if random.random() > 0.3 else None
            
            order = Order.objects.create(
                customer=cliente,
                employee=empleado,
                date_received=fake.date_time_between_dates(
                    datetime_start=datetime(2025, 1, 1),
                    datetime_end=datetime(2025, 4, 30)
                ),
                date_required=fake.date_time_between(start_date='now', end_date='+30d'),
                status=random.choice(['CONFIRMED', 'IN_PROGRESS', 'DELIVERED']),
                priority=random.randint(1, 5),
                payment_due_date=fake.date_time_between(start_date='now', end_date='+15d')
            )
            
            # Seleccionar servicios con precios disponibles
            servicios = random.sample(
                list(servicios_con_precio),
                k=random.randint(1, min(5, len(servicios_con_precio)))
            )
            
            for servicio in servicios:
                # Obtener moneda aleatoria de las disponibles para el servicio
                monedas = servicio.price_history.values_list('currency', flat=True).distinct()
                currency = random.choice(monedas) if monedas else 'EUR'
                
                OrderService.objects.create(
                    order=order,
                    service=servicio,
                    quantity=random.randint(1, 10),
                    price=servicio.get_current_price(currency=currency) or Decimal('0.00'),
                    note=fake.sentence()
                )
                
            order.update_total_amount()