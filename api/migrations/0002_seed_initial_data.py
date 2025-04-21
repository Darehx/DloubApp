# api/migrations/0002_seed_initial_data.py (o el número que sea)

from django.db import migrations
from decimal import Decimal
import datetime

# Importa tus constantes de roles
try:
    from api.roles import Roles
except ImportError:
    # Define placeholders si falla la importación
    class Roles:
        DRAGON='dragon'; ADMIN='admin'; MARKETING='mktg'; FINANCE='fin'; SALES='sales'
        DEVELOPMENT='dev'; AUDIOVISUAL='avps'; DESIGN='dsgn'; SUPPORT='support'
        OPERATIONS='ops'; HR='hr' # Asegúrate que coincidan con los de abajo
    print("ADVERTENCIA: No se pudo importar api.roles en seed_initial_data. Usando placeholders.")

# --- DATOS INICIALES A CREAR ---
# ¡¡¡MODIFICA ESTAS LISTAS CON TUS DATOS REALES!!!

INITIAL_ROLES = [
    {"name": Roles.DRAGON, "display_name": "Dragon Core", "description": "Acceso total y permisos especiales de aplicación."},
    {"name": Roles.ADMIN, "display_name": "Administración App", "description": "Gestiona usuarios y configuraciones generales de la app."},
    {"name": Roles.MARKETING, "display_name": "Marketing", "description": "Acceso a herramientas y datos de marketing."},
    {"name": Roles.FINANCE, "display_name": "Finanzas", "description": "Acceso a facturación y reportes financieros."},
    {"name": Roles.SALES, "display_name": "Ventas", "description": "Gestiona leads, clientes y procesos de venta."},
    {"name": Roles.DEVELOPMENT, "display_name": "Desarrollo", "description": "Acceso a herramientas de desarrollo y logs."},
    {"name": Roles.AUDIOVISUAL, "display_name": "Audiovisual", "description": "Gestiona contenido multimedia."},
    {"name": Roles.DESIGN, "display_name": "Diseño", "description": "Gestiona assets y guías de estilo."},
    {"name": Roles.SUPPORT, "display_name": "Soporte", "description": "Gestiona tickets de soporte y atención al cliente."},
    {"name": Roles.OPERATIONS, "display_name": "Operaciones", "description": "Gestiona procesos internos y logística."},
    {"name": Roles.HR, "display_name": "Recursos Humanos", "description": "Gestión de personal."},
]

INITIAL_JOB_POSITIONS = [
    {"name": "CEO", "description": "Dirección Ejecutiva"},
    {"name": "CTO", "description": "Dirección de Tecnología"},
    {"name": "Desarrollador Backend", "description": "Desarrollo de lógica de servidor y API"},
    {"name": "Desarrollador Frontend", "description": "Desarrollo de interfaz de usuario"},
    {"name": "Diseñador UI/UX", "description": "Diseño de Experiencia e Interfaz"},
    {"name": "Diseñador Gráfico", "description": "Creación de material visual"},
    {"name": "Editor de Video", "description": "Postproducción audiovisual"},
    {"name": "Estratega de Marketing", "description": "Planificación de campañas"},
    {"name": "Community Manager", "description": "Gestión de redes sociales"},
    {"name": "Ejecutivo de Ventas", "description": "Gestión comercial"},
    {"name": "Contable", "description": "Gestión financiera"},
    {"name": "Agente de Soporte", "description": "Atención y resolución de incidencias"},
    {"name": "Jefe de Operaciones", "description": "Coordinación de operaciones"},
    {"name": "Especialista en RRHH", "description": "Gestión de talento y personal"},
]

INITIAL_SERVICE_CATEGORIES = [
    {"code": "MKT", "name": "MARKETING"},
    {"code": "DEV", "name": "DEVELOPMENT"},
    {"code": "DSGN", "name": "DESIGN"},
    {"code": "SMM", "name": "SOCIAL MEDIA"},
    {"code": "BRND", "name": "BRANDING"},
    {"code": "AVP", "name": "AUDIOVISUAL PRODUCTION SERVICES (APS)"},
    {"code": "PRNT", "name": "IMPRENTA"},
    {"code": "CONS", "name": "CONSULTORIA"},
]

INITIAL_TRANSACTION_TYPES = [
    {"name": "Pago Cliente", "requires_approval": False},
    {"name": "Reembolso Cliente", "requires_approval": True},
    {"name": "Pago Proveedor", "requires_approval": True},
    {"name": "Gasto Interno", "requires_approval": True},
    {"name": "Ajuste Saldo", "requires_approval": True},
]

INITIAL_PAYMENT_METHODS = [
    {"name": "Transferencia Bancaria", "is_active": True},
    {"name": "Tarjeta de Crédito/Débito", "is_active": True},
    {"name": "PayPal", "is_active": True},
    {"name": "Stripe", "is_active": True},
    {"name": "Efectivo", "is_active": False},
]


def seed_data(apps, schema_editor):
    """Función principal para poblar todos los datos iniciales."""
    db_alias = schema_editor.connection.alias
    print("\n   [INFO] Iniciando creación de datos iniciales...")

    model_map = {
        'UserRole': ('api', INITIAL_ROLES, 'name'),
        'JobPosition': ('api', INITIAL_JOB_POSITIONS, 'name'),
        'ServiceCategory': ('api', INITIAL_SERVICE_CATEGORIES, 'code'),
        'TransactionType': ('api', INITIAL_TRANSACTION_TYPES, 'name'),
        'PaymentMethod': ('api', INITIAL_PAYMENT_METHODS, 'name'),
    }

    for model_name, (app_label, data_list, unique_key) in model_map.items():
        Model = apps.get_model(app_label, model_name)
        created_count = 0
        print(f"     - Creando {model_name}s...")
        for data in data_list:
            try:
                _, created = Model.objects.using(db_alias).get_or_create(
                    **{unique_key: data[unique_key]}, defaults=data
                )
                if created: created_count += 1
            except Exception as e:
                print(f"       [ERROR] Creando {model_name} '{data[unique_key]}': {e}")
        print(f"       -> {created_count} {model_name}s creados.")


    print("   [INFO] Finalizada creación de datos iniciales.")


def remove_initial_data(apps, schema_editor):
    """Elimina los datos creados por esta migración (para revertir)."""
    db_alias = schema_editor.connection.alias
    print("\n   [REVERT] Eliminando datos iniciales...")
    models_to_clear_by_name = [ # Lista de modelos, clave única y lista de valores
         ('api', 'PaymentMethod', 'name', [pm['name'] for pm in INITIAL_PAYMENT_METHODS]),
         ('api', 'TransactionType', 'name', [tt['name'] for tt in INITIAL_TRANSACTION_TYPES]),
         ('api', 'ServiceCategory', 'code', [sc['code'] for sc in INITIAL_SERVICE_CATEGORIES]),
         ('api', 'JobPosition', 'name', [jp['name'] for jp in INITIAL_JOB_POSITIONS]),
         ('api', 'UserRole', 'name', [r['name'] for r in INITIAL_ROLES]), ]
    for app_label, model_name, filter_key, filter_values in models_to_clear_by_name:
         Model = apps.get_model(app_label, model_name)
         count, _ = Model.objects.using(db_alias).filter(**{f"{filter_key}__in": filter_values}).delete()
         print(f"     - {count} {model_name}(s) eliminados.")
    print("   [REVERT] Finalizada eliminación de datos iniciales.")


class Migration(migrations.Migration):

    dependencies = [
        # Depende de la migración de esquema
        ('api', '0001_initial'), # ¡¡¡ASEGÚRATE QUE ESTE NOMBRE SEA CORRECTO!!!
    ]

    operations = [
        migrations.RunPython(seed_data, remove_initial_data),
    ]