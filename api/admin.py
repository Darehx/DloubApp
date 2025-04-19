# api/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

# Importa tus modelos actualizados
from .models import UserRole, UserProfile, UserRoleAssignment, JobPosition

# --- Admin para UserRole ---
@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    # ... (definición sin cambios) ...
    list_display = ('display_name', 'name', 'is_active', 'description')
    list_filter = ('is_active',)
    search_fields = ('name', 'display_name', 'description')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'display_name', 'description', 'is_active')}),
        (_('Metadata'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

# --- Inlines para UserAdmin ---
class UserProfileInline(admin.StackedInline):
    # ... (definición sin cambios) ...
    model = UserProfile
    can_delete = False
    verbose_name_plural = _('Profile and Primary Role')
    fields = ('primary_role',)
    autocomplete_fields = ['primary_role']

class SecondaryRoleAssignmentInline(admin.TabularInline):
    # ... (definición sin cambios) ...
    model = UserRoleAssignment
    extra = 1
    autocomplete_fields = ['role']
    fields = ('role', 'is_active')
    verbose_name = _("Secondary Role / Access")
    verbose_name_plural = _("Secondary Roles / Accesses")
    fk_name = "user"


# --- UserAdmin Personalizado ---
UserModel = get_user_model()

# --- CORRECCIÓN AQUÍ: Desregistrar el UserAdmin por defecto ANTES de registrar el nuevo ---
# Es buena práctica envolverlo en un try/except por si acaso no estuviera registrado
try:
    admin.site.unregister(UserModel)
except admin.sites.NotRegistered:
    pass
# --- FIN CORRECCIÓN ---

@admin.register(UserModel) # Ahora esto debería funcionar
class UserAdminWithRoles(BaseUserAdmin):
    inlines = [UserProfileInline, SecondaryRoleAssignmentInline] + list(BaseUserAdmin.inlines)
    # ... (opcional: list_display, list_filter personalizados) ...


# --- Admin para Asignaciones Secundarias ---
@admin.register(UserRoleAssignment)
class SecondaryRoleAssignmentAdmin(admin.ModelAdmin):
    # ... (definición sin cambios) ...
    list_display = ('user', 'role', 'is_active', 'assigned_at')
    list_filter = ('role', 'is_active', 'assigned_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'role__name', 'role__display_name')
    autocomplete_fields = ['user', 'role']
    list_editable = ('is_active',)
    readonly_fields = ('assigned_at', 'updated_at')
    date_hierarchy = 'assigned_at'


# --- Registra otros modelos ---
# Ejemplo:
# admin.site.register(JobPosition) # Asegúrate que no esté ya registrado también
# ...