# api/management/commands/seed_operational_data.py
import random
# Import Python's standard datetime directly
import datetime
from decimal import Decimal, ROUND_HALF_UP # Import ROUND_HALF_UP for rounding
from faker import Faker
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone # Still needed for timezone.now()
from django.db import transaction, IntegrityError
from django_countries import countries # To get valid country codes

# Import models needed for CREATION and DELETION
from api.models import (
    Customer, JobPosition, Employee, Provider,
    Order, OrderService, Deliverable, TransactionType, PaymentMethod, Invoice,
    Payment
)
# Import models needed only for READING (linking)
from api.models import Service, Price

# --- Configuration ---
NUM_MOCK_CUSTOMERS = 25
NUM_MOCK_EMPLOYEES = 8
NUM_MOCK_PROVIDERS = 5
NUM_MOCK_ORDERS = 70         # Target number of orders
NUM_INVOICES_RATIO = 0.85 # Approx. % of mock orders getting an invoice
NUM_PAYMENTS_RATIO = 0.75 # Approx. % of mock invoices getting payment(s)
NUM_DELIVERABLES_PER_ORDER_MAX = 4

# Usernames for mock users (to potentially identify/clean them later)
MOCK_CUSTOMER_USERNAME_PREFIX = "mockcust_"
MOCK_EMPLOYEE_USERNAME_PREFIX = "mockemp_"

User = get_user_model()
fake = Faker('es_ES') # Use Spanish localization
fake_en = Faker('en_US') # For company names etc.

# Get valid country codes from django-countries
VALID_COUNTRY_CODES = [code for code, name in list(countries)]

# Helper to round Decimal nicely
def round_decimal(d, places=2):
    if not isinstance(d, Decimal):
        d = Decimal(str(d)) # Convert if not already Decimal
    # Use quantize for proper decimal rounding
    return d.quantize(Decimal('1e-' + str(places)), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = ('Seeds the database with mock Customers, Employees, Providers, '
            'and Orders/Invoices/Payments/Deliverables, '
            'keeping existing Services/Prices/Campaigns intact.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear previously seeded MOCK data before creating new data.',
        )

    @transaction.atomic # Ensure all or nothing
    def handle(self, *args, **options):

        if options['clear']:
            self.stdout.write(self.style.WARNING(
                "Attempting to clear previously seeded mock data... "
                "(Deletes Payments, Invoices, Deliverables, OrderServices, Orders, Providers, "
                "mock Customers/Employees/Users, mock JobPositions, mock PaymentMethods, mock TransactionTypes)"
            ))
            # Clear data in reverse order of dependency for MOCKED items ONLY
            Payment.objects.filter(invoice__order__customer__user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            Invoice.objects.filter(order__customer__user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            Deliverable.objects.filter(order__customer__user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            OrderService.objects.filter(order__customer__user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            Order.objects.filter(customer__user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            Provider.objects.filter(name__startswith='Mock Provider').delete()
            Customer.objects.filter(user__username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX).delete()
            Employee.objects.filter(user__username__startswith=MOCK_EMPLOYEE_USERNAME_PREFIX).delete()
            User.objects.filter(username__startswith=MOCK_CUSTOMER_USERNAME_PREFIX,is_staff=False, is_superuser=False).delete()
            User.objects.filter(username__startswith=MOCK_EMPLOYEE_USERNAME_PREFIX, is_staff=True, is_superuser=False).delete()
            JobPosition.objects.filter(name__startswith='Mock Position').delete()
            PaymentMethod.objects.filter(name__startswith='Mock Method').delete()
            TransactionType.objects.filter(name__startswith='Mock Type').delete()
            self.stdout.write(self.style.SUCCESS("Previously seeded mock data cleared (based on prefixes/assumptions)."))

        # --- 1. Fetch Existing Services ---
        self.stdout.write("Fetching existing active Services...")
        existing_active_services = list(Service.objects.filter(is_active=True))
        if not existing_active_services:
            self.stderr.write(self.style.ERROR("No active services found in the database. Cannot create mock orders with services."))
            return
        self.stdout.write(f"Found {len(existing_active_services)} active services.")

        # --- 2. Create Supporting Mock Data ---
        self.stdout.write("Creating Supporting Mock Data (Positions, Payment Methods, Transaction Types)...")
        positions_data = [
            {'name': 'Mock Position Ventas', 'permissions': {}},
            {'name': 'Mock Position Soporte', 'permissions': {}},
            {'name': 'Mock Position Manager', 'permissions': {'admin': True}},
        ]
        mock_positions = []
        for data in positions_data:
            pos, created = JobPosition.objects.get_or_create(name=data['name'], defaults=data)
            mock_positions.append(pos)
        methods_data = [
            {'name': 'Mock Method Transfer', 'is_active': True},
            {'name': 'Mock Method Card', 'is_active': True},
        ]
        mock_payment_methods = []
        for data in methods_data:
             meth, created = PaymentMethod.objects.get_or_create(name=data['name'], defaults=data)
             mock_payment_methods.append(meth)
        trans_types_data = [
            {'name': 'Mock Type Pago', 'requires_approval': False},
            {'name': 'Mock Type Reembolso', 'requires_approval': True},
        ]
        mock_transaction_types = []
        for data in trans_types_data:
             tt, created = TransactionType.objects.get_or_create(name=data['name'], defaults=data)
             mock_transaction_types.append(tt)
        try:
            mock_pago_cliente_tt = TransactionType.objects.get(name='Mock Type Pago')
            mock_reembolso_tt = TransactionType.objects.get(name='Mock Type Reembolso')
        except TransactionType.DoesNotExist as e:
            self.stderr.write(self.style.ERROR(f"Could not find required mock TransactionTypes: {e}"))
            return

        # --- 3. Create Mock Users ---
        self.stdout.write("Creating Mock Users...")
        mock_users_list = []
        mock_employee_users = []
        mock_customer_users = []
        # Create Employee Users
        for i in range(NUM_MOCK_EMPLOYEES):
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"{MOCK_EMPLOYEE_USERNAME_PREFIX}{first_name.lower()}{random.randint(1, 999)}"
            while User.objects.filter(username=username).exists():
                 username = f"{MOCK_EMPLOYEE_USERNAME_PREFIX}{first_name.lower()}{random.randint(1000, 9999)}"
            email = f"{username}@mockmail.com"
            try:
                user, created = User.objects.get_or_create(username=username, defaults={
                        'email': email, 'first_name': first_name, 'last_name': last_name,
                        'is_active': random.choices([True, False], weights=[95, 5], k=1)[0], 'is_staff': True })
                if created:
                    user.set_password('password123'); user.save()
                elif not user.is_staff:
                    user.is_staff = True; user.save(update_fields=['is_staff'])
                mock_users_list.append(user); mock_employee_users.append(user)
            except IntegrityError: self.stderr.write(f"Skipping duplicate mock employee user (email?): {username}")
            except Exception as e: self.stderr.write(f"Error creating/getting mock employee user {username}: {e}")
        # Create Customer Users
        for i in range(NUM_MOCK_CUSTOMERS):
            first_name = fake.first_name(); last_name = fake.last_name()
            username = f"{MOCK_CUSTOMER_USERNAME_PREFIX}{first_name.lower()}{random.randint(1, 999)}"
            while User.objects.filter(username=username).exists():
                 username = f"{MOCK_CUSTOMER_USERNAME_PREFIX}{first_name.lower()}{random.randint(1000, 9999)}"
            email = f"{username}@mockmail.com"
            try:
                user, created = User.objects.get_or_create(username=username, defaults={
                        'email': email, 'first_name': first_name, 'last_name': last_name,
                        'is_active': True, 'is_staff': False })
                if created:
                    user.set_password('password123'); user.save()
                elif user.is_staff:
                     user.is_staff = False; user.save(update_fields=['is_staff'])
                mock_users_list.append(user); mock_customer_users.append(user)
            except IntegrityError: self.stderr.write(f"Skipping duplicate mock customer user (email?): {username}")
            except Exception as e: self.stderr.write(f"Error creating/getting mock customer user {username}: {e}")

        # --- 4. Create Mock Employees ---
        self.stdout.write("Creating Mock Employees...")
        mock_employees = []; active_mock_employees = []
        if not mock_positions: self.stderr.write(self.style.ERROR("No mock Job Positions available."))
        else:
             valid_employee_users = [u for u in mock_employee_users if u.username.startswith(MOCK_EMPLOYEE_USERNAME_PREFIX)]
             for user in valid_employee_users:
                 try:
                     employee, created = Employee.objects.get_or_create(user=user, defaults={
                             'hire_date': fake.date_between(start_date='-3y', end_date='today'), 'address': fake.address(),
                             'salary': Decimal(random.randrange(25000, 70000, 1000)), 'position': random.choice(mock_positions)})
                     mock_employees.append(employee)
                     if user.is_active: active_mock_employees.append(employee)
                 except IntegrityError as e: self.stderr.write(self.style.ERROR(f"IntegrityError during Employee get_or_create for User {user.id} ({user.username}): {e}."))
                 except Exception as e: self.stderr.write(f"Error during Employee get_or_create for User {user.id} ({user.username}): {e}")

        # --- 5. Create Mock Customers ---
        self.stdout.write("Creating Mock Customers...")
        mock_customers = []
        valid_customer_users = [u for u in mock_customer_users if u.username.startswith(MOCK_CUSTOMER_USERNAME_PREFIX)]
        for user in valid_customer_users:
             try:
                 customer, created = Customer.objects.get_or_create(user=user, defaults={
                         'phone': fake.phone_number(), 'address': fake.address(), 'date_of_birth': fake.date_of_birth(minimum_age=20, maximum_age=75),
                         'country': random.choice(VALID_COUNTRY_CODES), 'company_name': fake.company() if random.choice([True, False]) else None,
                         'preferred_contact_method': random.choice(['email', 'phone', 'whatsapp'])})
                 mock_customers.append(customer)
             except IntegrityError as e: self.stderr.write(self.style.ERROR(f"IntegrityError during Customer get_or_create for User {user.id} ({user.username}): {e}."))
             except Exception as e: self.stderr.write(f"Error during Customer get_or_create for User {user.id} ({user.username}): {e}")

        # --- 6. Create Mock Providers ---
        self.stdout.write("Creating Mock Providers...")
        mock_providers = []
        for i in range(NUM_MOCK_PROVIDERS):
             provider_name = f"Mock Provider {fake.company_suffix()} {i+1}"
             provider, created = Provider.objects.get_or_create(name=provider_name, defaults={
                     'contact_person': fake.name(), 'email': fake.company_email(), 'phone': fake.phone_number(),
                     'rating': Decimal(random.uniform(3.5, 5.0)), 'is_active': True, 'notes': f"Mock provider for testing {fake.catch_phrase()}."})
             mock_providers.append(provider)

        # --- 7. Create Mock Orders ---
        self.stdout.write("Creating Mock Orders...")
        mock_orders = []
        order_statuses = [s[0] for s in Order.STATUS_CHOICES]
        if not mock_customers: self.stderr.write(self.style.ERROR("No mock customers created/found."))
        else:
            for i in range(NUM_MOCK_ORDERS):
                customer = random.choice(mock_customers)
                assigned_employee = random.choice(active_mock_employees) if active_mock_employees and random.choices([True, False], weights=[75, 25], k=1)[0] else None
                date_rec = fake.date_time_between(start_date='-18m', end_date='now', tzinfo=datetime.timezone.utc)
                date_req = date_rec + datetime.timedelta(days=random.randint(7, 45))
                status = random.choice(order_statuses)
                completed = None
                if status == 'DELIVERED':
                    completed_base = date_rec + datetime.timedelta(days=random.randint(5, 40))
                    completed = min(timezone.now(), completed_base)
                    completed = max(date_rec + datetime.timedelta(days=1), completed)
                    completed = max(date_req, completed) if random.choice([True,True,False]) else completed
                try:
                    order = Order.objects.create(customer=customer, employee=assigned_employee, date_received=date_rec, date_required=date_req,
                        status=status, payment_due_date=date_req + datetime.timedelta(days=random.choice([7, 15, 30])),
                        note=f"Mock order note: {fake.sentence(nb_words=5)}" if random.choice([True, False]) else '', priority=random.randint(1, 5), completed_at=completed)
                    mock_orders.append(order)
                except Exception as e: self.stderr.write(f"Error creating mock Order {i+1}: {e}")

            # --- 8. Create Mock OrderServices (linking to EXISTING services) ---
            self.stdout.write("Creating Mock Order Services (using existing Services)...")
            orders_processed_count = 0
            if not mock_orders: self.stdout.write("Warning: No mock orders were created.")
            else:
                for order in mock_orders:
                    num_services_in_order = random.randint(1, 4)
                    if not existing_active_services: continue
                    selected_services = random.sample(existing_active_services, k=min(len(existing_active_services), num_services_in_order))
                    order_services_created = []
                    if not selected_services: continue
                    for service in selected_services:
                        relevant_price = Price.objects.filter(service=service, effective_date__lte=order.date_received.date()).order_by('-effective_date', '-id').first()
                        price_amount = Decimal('0.00')
                        if relevant_price: price_amount = relevant_price.amount
                        else:
                            most_recent_price = Price.objects.filter(service=service).order_by('-effective_date', '-id').first()
                            if most_recent_price: price_amount = most_recent_price.amount
                            else:
                                 # Assign fallback and round it here
                                 price_amount = round_decimal(Decimal(random.uniform(5.0, 25.0)))
                                 self.stderr.write(f"ERROR: No price found ANYWHERE for Service {service.code}. Assigning random fallback {price_amount} for Order {order.id}.")
                        if price_amount <= 0 and not getattr(service, 'ventulab', False):
                            price_amount = round_decimal(Decimal(random.uniform(1.0, 10.0)))
                        try:
                            order_service = OrderService.objects.create(order=order, service=service, quantity=random.randint(1, 2),
                                price=round_decimal(price_amount), # Ensure price is rounded before saving
                                note=f"Mock service note: {fake.bs()}" if random.choices([True, False], weights=[15, 85], k=1)[0] else '')
                            order_services_created.append(order_service)
                        except Exception as e: self.stderr.write(f"Error creating OrderService for Order {order.id}, Service {service.code}: {e}")
                    if order_services_created:
                        order.update_total_amount(); orders_processed_count += 1
                self.stdout.write(f"Created OrderServices for {orders_processed_count} mock orders.")

            # --- 9. Create Mock Invoices ---
            self.stdout.write("Creating Mock Invoices...")
            mock_invoices = []
            orders_eligible_for_invoice = [o for o in mock_orders if hasattr(o, 'total_amount') and o.total_amount is not None and o.total_amount > 0]
            if not orders_eligible_for_invoice: self.stdout.write("Warning: No mock orders eligible for invoicing.")
            else:
                 orders_to_invoice = random.sample(orders_eligible_for_invoice, k=min(len(orders_eligible_for_invoice), int(len(mock_orders) * NUM_INVOICES_RATIO)))
                 invoice_statuses = [s[0] for s in Invoice.STATUS_CHOICES if s[0] != 'DRAFT']
                 for order in orders_to_invoice:
                     invoice_date = order.date_received.date() + datetime.timedelta(days=random.randint(0, 5))
                     invoice_date = min(timezone.now().date(), invoice_date)
                     invoice_date = max(order.date_received.date(), invoice_date)
                     due_date = invoice_date + datetime.timedelta(days=random.choice([15, 30, 45]))
                     status = random.choice(invoice_statuses)
                     if status not in ['PAID', 'CANCELLED', 'VOID'] and due_date < timezone.now().date(): status = 'OVERDUE'
                     elif status == 'OVERDUE' and due_date >= timezone.now().date(): status = 'SENT'
                     try:
                         invoice = Invoice.objects.create(order=order, date=invoice_date, due_date=due_date, status=status,
                             notes=f"Mock invoice terms: {fake.sentence(nb_words=8)}" if random.choice([True, False]) else '')
                         mock_invoices.append(invoice)
                     except Exception as e: self.stderr.write(f"Error creating Invoice for Order {order.id}: {e}")

            # --- 10. Create Mock Payments ---
            self.stdout.write("Creating Mock Payments...")
            if not mock_invoices: self.stdout.write("Warning: No mock invoices created.")
            elif not mock_payment_methods or not mock_transaction_types: self.stderr.write(self.style.ERROR("Mock Payment Methods or Transaction Types not available."))
            else:
                 invoices_to_pay = random.sample(mock_invoices, k=min(len(mock_invoices), int(len(mock_invoices) * NUM_PAYMENTS_RATIO)))
                 payment_statuses = [s[0] for s in Payment.STATUS_CHOICES]
                 for invoice in invoices_to_pay:
                     try:
                          invoice.refresh_from_db()
                          if not hasattr(invoice, 'total_amount') or invoice.total_amount is None: continue
                          if invoice.status in ['PAID', 'CANCELLED', 'VOID']: continue
                     except Invoice.DoesNotExist: continue
                     payments_for_invoice = random.randint(1, 2)
                     total_paid_so_far = invoice.paid_amount
                     invoice_total = invoice.total_amount
                     for _ in range(payments_for_invoice):
                         if total_paid_so_far >= invoice_total: break
                         payment_date_base = invoice.date + datetime.timedelta(days=random.randint(0, 35))
                         payment_date = min(timezone.now().date(), payment_date_base)
                         payment_date = max(invoice.date, payment_date)
                         amount_to_pay = Decimal('0.00')
                         payment_scenario = random.choice(['full', 'partial', 'over'])
                         remaining = invoice_total - total_paid_so_far
                         if remaining <= 0: continue

                         # --- FIX TypeError HERE ---
                         if payment_scenario == 'full' or _ == payments_for_invoice - 1:
                             amount_to_pay = remaining
                         elif payment_scenario == 'partial':
                             # Convert float from random.uniform to Decimal before multiplying
                             amount_to_pay = Decimal(random.uniform(0.1, 0.8)) * remaining
                         elif payment_scenario == 'over':
                             # Convert float from random.uniform to Decimal before multiplying
                             amount_to_pay = remaining * Decimal(random.uniform(1.01, 1.05))
                         # --- End Fix ---

                         # Round the calculated amount appropriately
                         amount_to_pay = round_decimal(amount_to_pay)

                         if amount_to_pay < Decimal('0.01') and amount_to_pay > 0: amount_to_pay = Decimal('0.01')
                         if amount_to_pay <= 0: continue

                         status = random.choices(payment_statuses, weights=[5, 88, 4, 3], k=1)[0]
                         trans_type = mock_pago_cliente_tt
                         if status == 'REFUNDED':
                             if total_paid_so_far <= 0: continue
                             trans_type = mock_reembolso_tt
                             # Refund calculation - ensure it's rounded
                             amount_to_pay = -abs(round_decimal(Decimal(random.uniform(0.1, 1.0)) * total_paid_so_far))
                             if amount_to_pay == 0: continue

                         try:
                             payment_datetime = datetime.datetime.combine(payment_date, datetime.time(12, 0, 0), tzinfo=datetime.timezone.utc)
                             payment = Payment.objects.create(invoice=invoice, method=random.choice(mock_payment_methods), transaction_type=trans_type,
                                 date=payment_datetime, amount=amount_to_pay, currency='EUR', status=status,
                                 transaction_id=fake.iban() if random.choice([True, False]) else None,
                                 notes=f"Mock payment ref: {fake.word()}" if random.choices([True, False], weights=[10, 90], k=1)[0] else '')
                             if status == 'COMPLETED': total_paid_so_far += amount_to_pay
                             elif status == 'REFUNDED': total_paid_so_far += amount_to_pay # amount is negative
                         except Exception as e: self.stderr.write(f"Error creating Payment for Invoice {invoice.id} ({invoice.invoice_number}): {e}")
                     try:
                        invoice.update_paid_amount_and_status(trigger_notifications=False)
                     except Invoice.DoesNotExist: pass
                     except Exception as e: self.stderr.write(f"Error updating Invoice {invoice.id} status after payment: {e}")

            # --- 11. Create Mock Deliverables ---
            self.stdout.write("Creating Mock Deliverables...")
            deliverable_statuses = [s[0] for s in Deliverable.STATUS_CHOICES]
            deliverables_created_count = 0
            if not active_mock_employees and not mock_providers: self.stdout.write("Warning: No active mock employees or providers available.")
            if not mock_orders: self.stdout.write("Warning: No mock orders exist.")
            else:
                for order in mock_orders:
                     if order.status in ['DRAFT', 'CANCELLED']: continue
                     num_deliverables = random.randint(0, NUM_DELIVERABLES_PER_ORDER_MAX)
                     for i in range(num_deliverables):
                         status = random.choice(deliverable_statuses)
                         assignee = None
                         possible_assignees = [None, None]
                         if active_mock_employees: possible_assignees.extend(active_mock_employees)
                         if mock_providers: possible_assignees.extend(mock_providers)
                         if len(possible_assignees) > 2: assignee = random.choice(possible_assignees)
                         assigned_employee = assignee if isinstance(assignee, Employee) else None
                         assigned_provider = assignee if isinstance(assignee, Provider) else None
                         due_date_base = order.date_received.date() + datetime.timedelta(days=random.randint(5, 40))
                         due_date = max(order.date_received.date() + datetime.timedelta(days=1), due_date_base)
                         try:
                             Deliverable.objects.create(order=order, description=f"Mock Deliverable {i+1} - {fake.bs()}", version=1, status=status,
                                 due_date=due_date if random.choices([True, False], weights=[85, 15], k=1)[0] else None,
                                 assigned_employee=assigned_employee, assigned_provider=assigned_provider,
                                 feedback_notes=fake.sentence(nb_words=10) if status in ['REVISION_REQUESTED', 'REJECTED', 'REQUIRES_INFO'] else '')
                             deliverables_created_count += 1
                         except Exception as e: self.stderr.write(f"Error creating Deliverable for Order {order.id}: {e}")
                self.stdout.write(f"Created {deliverables_created_count} mock deliverables.")

        # --- Finish ---
        self.stdout.write(self.style.SUCCESS('Successfully seeded operational mock data!'))