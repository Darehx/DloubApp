# api/roles.py
"""
Define constantes para los nombres internos de los roles de usuario.
Esto evita errores tipográficos y hace el código más legible.
"""

class Roles:
    # Core / Admin Roles
    DRAGON = 'dragon'        # Superusuario específico de la app con acceso total
    ADMIN = 'admin'          # Administrador general de la aplicación

    # Department / Function Roles (Primarios Típicos)
    MARKETING = 'mktg'       # Equipo de Marketing
    FINANCE = 'fin'          # Equipo de Finanzas
    SALES = 'sales'          # Equipo de Ventas
    DEVELOPMENT = 'dev'      # Equipo de Desarrollo
    AUDIOVISUAL = 'avps'     # Equipo de Producción Audiovisual
    DESIGN = 'dsgn'          # Equipo de Diseño
    SUPPORT = 'support'      # Equipo de Soporte al Cliente
    OPERATIONS = 'ops'       # Equipo de Operaciones Internas
    HR = 'hr'                # Recursos Humanos (Ejemplo adicional)

    # Podrías añadir roles secundarios/permisos aquí si los necesitas muy definidos
    # REPORT_VIEWER = 'report_viewer'
    # CONTENT_PUBLISHER = 'content_publisher'

    # Puedes añadir un método para obtener una lista o diccionario si es útil
    @classmethod
    def get_all_roles(cls):
        return [getattr(cls, attr) for attr in dir(cls) if not callable(getattr(cls, attr)) and not attr.startswith("__")]