# Análisis, Documentación y Mejora de la API DloubApp

Este documento describe la estructura actual de la API, documenta sus componentes clave y propone áreas de mejora.

**1. Documentación de la Estructura Actual**

*   **Arquitectura General:**
    *   Proyecto Django con una app principal (`DloubApp`) para la configuración y dos apps adicionales: `api` (contiene toda la lógica de la API REST) y `Dloub_Dragon_App` (actualmente sin uso específico definido).
    *   Utiliza Django REST Framework (DRF) para construir la API.
    *   Base de datos: Microsoft SQL Server (`mssql-django`).
    *   Autenticación: Basada en tokens JWT (`djangorestframework-simplejwt`), con tokens enviados vía cookies HTTPOnly.
    *   Manejo de CORS configurado para permitir solicitudes desde `localhost:3000` y `localhost:4000`.
    *   Uso de `django-filters` para capacidades de filtrado en los endpoints.
    *   Paginación estándar de DRF habilitada.

*   **Modelos de Datos (`api/models.py`):**
    *   Se definen modelos bien estructurados para gestionar diferentes aspectos del negocio:
        *   **Usuarios:** `Customer`, `Employee` (vinculados al `User` de Django), `JobPosition`.
        *   **Formularios:** `Form`, `FormQuestion`, `FormResponse`.
        *   **Proyectos:** `CustomerProject`, `EmployeeAssignment`.
        *   **Pedidos:** `Order`, `OrderService`, `Deliverable`.
        *   **Pagos:** `Invoice`, `Payment`, `PaymentMethod`, `TransactionType`.
        *   **Catálogo:** `Service`, `SubService`, `Price`.
        *   **Marketing:** `Campaign`, `CampaignService`.
        *   **Otros:** `Provider`, `Notification`, `AuditLog`.
    *   Se utilizan relaciones ForeignKey, OneToOneField y ManyToManyField para conectar los modelos.
    *   Se usan señales (`post_save`) para automatizar la creación de perfiles (`Customer`/`Employee`) y precios iniciales (`Price`).

    ```mermaid
    erDiagram
        USER ||--o{ CUSTOMER : "profile"
        USER ||--o{ EMPLOYEE : "profile"
        USER ||--o{ NOTIFICATION : "receives"
        USER ||--o{ AUDITLOG : "performs"

        CUSTOMER ||--o{ CUSTOMERPROJECT : "has"
        CUSTOMER ||--o{ ORDER : "places"
        CUSTOMER ||--o{ FORMRESPONSE : "submits"

        EMPLOYEE ||--o{ EMPLOYEEASSIGNMENT : "assigned_to"
        EMPLOYEE ||--o{ ORDER : "manages"
        EMPLOYEE }o--|| JOBPOSITION : "holds"

        CUSTOMERPROJECT ||--o{ EMPLOYEEASSIGNMENT : "involves"
        CUSTOMERPROJECT }o--|| FORM : "uses"

        ORDER ||--o{ ORDERSERVICE : "includes"
        ORDER ||--o{ DELIVERABLE : "has"
        ORDER ||--o{ INVOICE : "generates"

        ORDERSERVICE }o--|| SERVICE : "details"

        INVOICE ||--o{ PAYMENT : "receives"

        PAYMENT }o--|| PAYMENTMETHOD : "uses"
        PAYMENT }o--|| TRANSACTIONTYPE : "is_type_of"

        SERVICE ||--o{ SUBSERVICE : "can_have"
        SERVICE ||--o{ PRICE : "has_history"
        SERVICE ||--o{ CAMPAIGNSERVICE : "part_of"
        SERVICE ||--o{ PROVIDER : "provided_by"

        CAMPAIGN ||--o{ CAMPAIGNSERVICE : "includes"
        CAMPAIGN ||--o{ SERVICE : "promotes"

        FORM ||--o{ FORMQUESTION : "contains"
        FORM ||--o{ FORMRESPONSE : "collects_for"

        FORMQUESTION ||--o{ FORMRESPONSE : "answers"
    ```

*   **Endpoints de la API (`api/urls.py`, `api/views.py`):**
    *   Se utiliza `DefaultRouter` para generar endpoints CRUD estándar para: `customers`, `employees`, `orders`, `services`, `campaigns`, `form_responses`, `deliverables`, `invoices`, `payments`, `job_positions`.
    *   Endpoints de autenticación JWT: `/api/token/`, `/api/token/refresh/`.
    *   Endpoint de verificación de autenticación: `/api/auth/check/`.
    *   Endpoint personalizado para creación masiva: `/api/form_responses/bulk_create/`.
    *   Permisos: Generalmente `IsAuthenticated`, con `IsAdminUser` para empleados y `AllowAny` para la creación de clientes. `IsAuthenticatedOrReadOnly` para servicios.
    *   Filtros habilitados en varios ViewSets (ej. `CustomerViewSet`, `OrderViewSet`, `ServiceViewSet`).

*   **Flujo de Datos (Ejemplo: Crear un Pedido):**
    1.  **Frontend:** Usuario autenticado envía una solicitud POST a `/api/orders/` con datos del pedido (cliente, servicios, etc.) en formato JSON. El token JWT se envía automáticamente en la cookie `access_token`.
    2.  **Django/DRF:**
        *   `urls.py` dirige la solicitud a `OrderViewSet`.
        *   `JWTAuthentication` verifica el token JWT de la cookie.
        *   `IsAuthenticated` verifica que el usuario esté autenticado.
        *   `OrderViewSet.create()`:
            *   Instancia `OrderSerializer` con los datos recibidos.
            *   Valida los datos usando el serializer.
            *   Extrae los datos de `services`.
            *   Llama a `serializer.save()`, que a su vez llama a `perform_create`.
            *   `perform_create` asigna el `customer` o `employee` basado en el perfil del usuario (`request.user`).
            *   Se crea el objeto `Order` en la base de datos.
            *   Itera sobre `services_data` y crea los objetos `OrderService` asociados.
        *   Se devuelve una respuesta JSON con los datos del pedido creado (serializados por `OrderSerializer`) y estado 201 Created.
    3.  **Frontend:** Recibe la respuesta y actualiza la interfaz.

    ```mermaid
    sequenceDiagram
        participant Frontend
        participant Django/DRF
        participant Database

        Frontend->>+Django/DRF: POST /api/orders/ (con datos y cookie JWT)
        Django/DRF->>Django/DRF: Autenticación JWT (verifica cookie)
        Django/DRF->>Django/DRF: Permisos (IsAuthenticated)
        Django/DRF->>Django/DRF: OrderViewSet.create()
        Django/DRF->>Django/DRF: OrderSerializer.validate(data)
        Django/DRF->>Django/DRF: serializer.save() -> perform_create()
        Django/DRF->>Database: INSERT INTO Order (...)
        Database-->>Django/DRF: Order ID
        loop Para cada servicio
            Django/DRF->>Database: INSERT INTO OrderService (...)
        end
        Django/DRF->>Django/DRF: Serializar Order creado
        Django/DRF-->>-Frontend: 201 Created (datos del pedido en JSON)
    ```

**2. Propuestas de Mejora**

*   **Seguridad:**
    *   **Configuración de Producción:** Establecer `DEBUG = False`, configurar `ALLOWED_HOSTS` con los dominios permitidos, y generar una `SECRET_KEY` segura (idealmente desde variables de entorno).
    *   **HTTPS:** Configurar HTTPS en producción y establecer `AUTH_COOKIE_SECURE = True` y `SESSION_COOKIE_SECURE = True`.
    *   **Permisos:** Revisar si los permisos actuales son suficientes o si se necesita una lógica de permisos más granular (ej. permisos a nivel de objeto para que un empleado solo modifique pedidos asignados a él).
    *   **Validación de Entradas:** Asegurar validaciones robustas en serializers y vistas para prevenir datos maliciosos o inesperados.
    *   **Variables de Entorno:** Mover datos sensibles (SECRET_KEY, configuración de BBDD) a variables de entorno en lugar de tenerlos hardcodeados en `settings.py`.

*   **Organización del Código:**
    *   **Clases de Servicio:** Continuar extrayendo lógica de negocio compleja de las vistas a clases de servicio dedicadas (como se hizo con `FormResponseService`). Esto mejora la legibilidad, mantenibilidad y facilita las pruebas.
    *   **Modularidad:** Si la app `api` sigue creciendo, considerar dividirla en apps más pequeñas por dominio (ej. `apps.users`, `apps.orders`, `apps.catalog`).
    *   **Serializers:** Evaluar si algunos serializers se pueden simplificar o reutilizar.

*   **Pruebas:**
    *   **Implementar Pruebas:** Crear pruebas unitarias (para modelos, serializers, funciones de servicio) y pruebas de integración (para vistas/endpoints) usando el framework de pruebas de Django y DRF. Esto es crucial para asegurar la estabilidad y prevenir regresiones. Cubrir casos de éxito, errores y casos límite.

*   **Rendimiento:**
    *   **Optimización de Consultas:** Revisar consultas complejas. Usar `select_related` y `prefetch_related` de forma proactiva en los `get_queryset` de los ViewSets para evitar el problema N+1. Analizar consultas lentas si es necesario.
    *   **Caché:** Considerar implementar caché (ej. Redis) para endpoints de solo lectura que se consultan frecuentemente y cuyos datos no cambian a menudo (ej. lista de servicios).

*   **Documentación de API:**
    *   **Generación Automática:** Integrar una herramienta como `drf-spectacular` para generar automáticamente documentación OpenAPI (Swagger UI / Redoc) a partir del código (modelos, serializers, vistas). Esto facilita el consumo de la API por parte de los desarrolladores de frontend u otros clientes.

*   **Manejo de Errores:**
    *   **Estandarización:** Definir un formato estándar para las respuestas de error de la API para que el frontend pueda manejarlas de manera consistente. DRF ya proporciona una base, pero se puede personalizar.

*   **App `Dloub_Dragon_App`:**
    *   Definir el propósito de esta app o eliminarla si no se va a utilizar para evitar confusión.

**3. Próximos Pasos (Plan de Implementación Sugerido)**

1.  **Priorizar Mejoras:** Enfocarse primero en las mejoras de seguridad críticas para producción.
2.  **Implementar Pruebas:** Empezar a escribir pruebas para los componentes más críticos.
3.  **Generar Documentación:** Configurar `drf-spectacular`.
4.  **Refactorizar:** Aplicar mejoras de organización (servicios, modularidad) gradualmente.
5.  **Optimizar:** Abordar optimizaciones de rendimiento según sea necesario.