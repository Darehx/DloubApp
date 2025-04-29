# api/permissions.py
from rest_framework.permissions import BasePermission, IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions # <--- ¡IMPORTACIÓN AÑADIDA!

# Importar constantes de roles
try:
    from .roles import Roles
except ImportError:
    class Roles:
        DRAGON = 'dragon'; ADMIN = 'admin'; MARKETING = 'mktg'; FINANCE = 'fin';
        SALES = 'sales'; DEVELOPMENT = 'dev'; SUPPORT = 'support'; OPERATIONS = 'ops';
        DESIGN = 'design'; AUDIOVISUAL = 'av';
    print("ADVERTENCIA: api/roles.py no encontrado. Usando roles placeholder.")

# Importar modelos si son necesarios
# from .models import Order, Customer

# ==============================================================================
# ------------------------- PERMISOS PERSONALIZADOS --------------------------
# ==============================================================================

class HasRolePermission(BasePermission):
    required_roles = []
    message = _("No tienes permiso para realizar esta acción debido a tu rol.")

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_has_required_role = False
        if hasattr(request.user, 'has_role'):
            user_has_required_role = any(request.user.has_role(role) for role in self.required_roles)
        elif hasattr(request.user, 'get_all_active_role_names'):
             try:
                 user_roles = set(request.user.get_all_active_role_names)
                 user_has_required_role = any(role in user_roles for role in self.required_roles)
             except Exception:
                 pass
        return request.user.is_staff or user_has_required_role

# --- Subclases específicas ---
class CanAccessDashboard(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.FINANCE, Roles.MARKETING, Roles.SALES, Roles.OPERATIONS]
    message = _("No tienes permiso para acceder al dashboard.")

class IsAdminOrDragon(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON]
    message = _("Necesitas ser Administrador o Dragón para esta acción.")

class CanManageEmployees(IsAdminOrDragon):
    message = _("No tienes permiso para gestionar empleados.")

class CanManageJobPositions(IsAdminOrDragon):
     message = _("No tienes permiso para gestionar puestos de trabajo.")

class CanManageCampaigns(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.MARKETING]
    message = _("No tienes permiso para gestionar campañas.")

class CanManageServices(IsAdminOrDragon):
    message = _("No tienes permiso para gestionar servicios.")

class CanManageFinances(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.FINANCE]
    message = _("No tienes permiso para realizar operaciones financieras.")

class CanViewAllOrders(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES, Roles.SUPPORT, Roles.OPERATIONS]
    message = _("No tienes permiso para ver todos los pedidos.")

class CanCreateOrders(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES]
    message = _("No tienes permiso para crear pedidos.")

class CanViewAllDeliverables(IsAdminOrDragon):
     message = _("No tienes permiso para ver todos los entregables.")

class CanCreateDeliverables(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.DEVELOPMENT, Roles.DESIGN, Roles.AUDIOVISUAL, Roles.OPERATIONS]
    message = _("No tienes permiso para crear entregables.")

class CanViewFormResponses(HasRolePermission):
    required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SALES, Roles.SUPPORT]
    message = _("No tienes permiso para ver las respuestas de formularios.")

class CanViewAuditLogs(IsAdminOrDragon):
    message = _("No tienes permiso para ver los registros de auditoría.")

# --- Permisos adicionales ---

class IsOwnerOrReadOnly(BasePermission):
    """
    Permiso a nivel de objeto para permitir solo a los propietarios de un objeto editarlo.
    Asume que el objeto tiene un atributo 'user' o 'customer.user'.
    """
    def has_object_permission(self, request, view, obj):
        # La corrección está aquí: se usa 'permissions.SAFE_METHODS' importado arriba
        if request.method in permissions.SAFE_METHODS: # GET, HEAD, OPTIONS
            return True
        owner = getattr(obj, 'user', None) or getattr(getattr(obj, 'customer', None), 'user', None)
        return owner == request.user

class IsCustomerOwnerOrAdminOrSupport(BasePermission):
    message = _("No tienes permiso para acceder a este cliente.")

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'customer_profile') and obj == request.user.customer_profile:
            return True
        if hasattr(request.user, 'employee_profile'):
            required_roles = [Roles.ADMIN, Roles.DRAGON, Roles.SUPPORT, Roles.SALES]
            if hasattr(request.user, 'has_role'):
                 if any(request.user.has_role(role) for role in required_roles):
                     return True
            elif request.user.is_staff:
                 return True
        return False