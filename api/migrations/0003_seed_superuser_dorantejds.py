# api/migrations/0003_seed_superuser_dorantejds.py (o el número que sea)

from django.db import migrations
from django.conf import settings
from django.contrib.auth.hashers import make_password
import logging

# Importa tus constantes de roles
try:
    from api.roles import Roles
except ImportError:
    class Roles: DRAGON = 'dragon'; ADMIN = 'admin'; # Placeholders
    print("ADVERTENCIA: No se pudo importar api.roles en seed_superuser.")

logger = logging.getLogger(__name__)

# --- DATOS DEL SUPERUSUARIO ---
SUPERUSER_USERNAME = 'dorantejds'
SUPERUSER_EMAIL = 'dorantejds@doruain.com'
SUPERUSER_PASSWORD = '1234' # ¡¡¡CAMBIAR ESTO DESPUÉS!!!
SUPERUSER_FIRST_NAME = 'Jesus F.'
SUPERUSER_LAST_NAME = 'Dorante'
SUPERUSER_PRIMARY_ROLE_NAME = Roles.DRAGON # Rol primario deseado
SUPERUSER_JOB_POSITION_NAME = 'CEO'      # Puesto deseado

def create_superuser(apps, schema_editor):
    """Crea el superusuario inicial dorantejds con rol DRAGON y puesto CEO."""
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    UserProfile = apps.get_model('api', 'UserProfile')
    UserRole = apps.get_model('api', 'UserRole')
    Employee = apps.get_model('api', 'Employee')
    JobPosition = apps.get_model('api', 'JobPosition')
    db_alias = schema_editor.connection.alias

    print(f"\n   [INFO] Intentando crear superusuario '{SUPERUSER_USERNAME}'...")

    if User.objects.using(db_alias).filter(username=SUPERUSER_USERNAME).exists():
        print(f"   [WARN] El superusuario '{SUPERUSER_USERNAME}' ya existe. Omitiendo creación.")
        return

    dragon_role = None
    try: dragon_role = UserRole.objects.using(db_alias).get(name=SUPERUSER_PRIMARY_ROLE_NAME)
    except UserRole.DoesNotExist: print(f"   [ERROR] Rol '{SUPERUSER_PRIMARY_ROLE_NAME}' no existe. Ejecuta seed_initial_data."); return

    ceo_position = None
    try: ceo_position = JobPosition.objects.using(db_alias).get(name=SUPERUSER_JOB_POSITION_NAME)
    except JobPosition.DoesNotExist: print(f"   [ERROR] Puesto '{SUPERUSER_JOB_POSITION_NAME}' no existe. Ejecuta seed_initial_data."); return

    try:
        user = User( username=SUPERUSER_USERNAME, email=SUPERUSER_EMAIL, first_name=SUPERUSER_FIRST_NAME, last_name=SUPERUSER_LAST_NAME, is_staff=True, is_superuser=True, is_active=True)
        user.password = make_password(SUPERUSER_PASSWORD)
        user.save(using=db_alias)
        print(f"     - Superusuario '{SUPERUSER_USERNAME}' creado.")

        try: # Asignar rol primario al perfil (creado por señal)
            # Asegurarse que la señal haya corrido - get_or_create es más seguro
            profile, created_prof = UserProfile.objects.using(db_alias).get_or_create(user=user)
            if profile.primary_role != dragon_role:
                profile.primary_role = dragon_role
                profile.save(using=db_alias, update_fields=['primary_role'])
                print(f"     - Rol primario '{SUPERUSER_PRIMARY_ROLE_NAME}' asignado al perfil.")
            elif created_prof: # Si el perfil se acaba de crear, asignar rol
                profile.primary_role = dragon_role
                profile.save(using=db_alias, update_fields=['primary_role'])
                print(f"     - Rol primario '{SUPERUSER_PRIMARY_ROLE_NAME}' asignado a perfil nuevo.")
        except Exception as e_prof: logger.error(f"Error asignando rol primario a {SUPERUSER_USERNAME}: {e_prof}")

        try: # Crear/Actualizar perfil de empleado
            employee, created_emp = Employee.objects.using(db_alias).get_or_create(user=user, defaults={'position': ceo_position})
            if not created_emp and employee.position != ceo_position: employee.position = ceo_position; employee.save(using=db_alias, update_fields=['position'])
            status_empleado = "creado" if created_emp else "actualizado"
            print(f"     - Perfil de Empleado {status_empleado} con puesto '{SUPERUSER_JOB_POSITION_NAME}'.")
        except Exception as e_emp: logger.error(f"Error creando/actualizando perfil empleado para {SUPERUSER_USERNAME}: {e_emp}")

        print(f"   [SUCCESS] Superusuario '{SUPERUSER_USERNAME}' configurado exitosamente.")

    except Exception as e:
        logger.error(f"Error creando superusuario '{SUPERUSER_USERNAME}': {e}")
        print(f"\n   [ERROR] Creando superusuario '{SUPERUSER_USERNAME}': {e}")


def remove_superuser(apps, schema_editor):
    """Elimina el superusuario creado por esta migración."""
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    db_alias = schema_editor.connection.alias
    print(f"\n   [REVERT] Intentando eliminar superusuario '{SUPERUSER_USERNAME}'...")
    deleted, _ = User.objects.using(db_alias).filter(username=SUPERUSER_USERNAME).delete()
    print(f"   [REVERT] Superusuario '{SUPERUSER_USERNAME}' {'eliminado' if deleted else 'no encontrado'}.")


class Migration(migrations.Migration):

    dependencies = [
        # ¡¡¡ASEGÚRATE QUE ESTOS NOMBRES SEAN CORRECTOS!!!
        ('api', '0001_initial'), # Depende de la creación de modelos
        ('api', '0002_seed_initial_data'), # Depende de la creación de roles/puestos
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_superuser, remove_superuser),
    ]