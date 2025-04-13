from pathlib import Path
import os

# Configuración básica del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
import os

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-7le8=td$=jvc%icgqp0in0)iy3f-1*up&h6u2c+%rzq^$-_63r')
DEBUG = False
ALLOWED_HOSTS = ['localhost']

# Aplicaciones instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # Django REST Framework
    'corsheaders',  # Manejo de CORS
    'Dloub_Dragon_App',  # Tu aplicación principal
    'api',  # Tu aplicación de API
    'django_filters', # Filtros avanzados para DRF
    'django_countries',  # Manejo de países 
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Debe estar al inicio
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Rutas principales
ROOT_URLCONF = 'DloubApp.urls'

# Configuración de plantillas
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # No necesitas servir archivos estáticos del frontend
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = 'DloubApp.wsgi.application'

# Base de datos
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'Testing',
        'HOST': r'DORUAIN-SDO\DORUAIN',  # Usa una cadena cruda (r"")
        'PORT': '1433',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'Trusted_Connection': 'yes',
        },
    }
}

# Validadores de contraseña
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internacionalización
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Archivos estáticos
STATIC_URL = '/static/'
# STATICFILES_DIRS = [os.path.join(BASE_DIR, 'frontend/_astro')]  # Comentar o eliminar si no usas archivos estáticos del frontend

# Archivos multimedia (opcional)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configuración de REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000", 
    "http://localhost:4000", # Origen de tu frontend
]
CORS_ALLOW_CREDENTIALS = True  # Permite el envío de cookies

APPEND_SLASH = False

# settings.py
SIMPLE_JWT = {
    'AUTH_COOKIE': 'access_token',  # Nombre de la cookie
    'AUTH_COOKIE_SECURE': False,  # True en producción (HTTPS)
    'AUTH_COOKIE_SAMESITE': 'Lax',  # o 'None' si usas HTTPS
}
# Configuración de sesiones
SESSION_COOKIE_SECURE = False  # Desactiva en desarrollo
SESSION_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 1209600  # 2 semanas en segundos

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'