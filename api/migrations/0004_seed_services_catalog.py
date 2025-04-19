# api/migrations/0004_seed_services_catalog.py (o el número que sea)

from django.db import migrations
from django.utils import timezone
from decimal import Decimal
import datetime

# --- DATOS DEL CATÁLOGO INICIAL ---
# (Basado en tu lista final de servicios OD001-OD055)

SERVICES_DATA = [
    # Code, Cat_Code, Name, IsActive, Ventulab, Campaign_Code, IsPackage
    ("OD001", "MKT", "CAMPAÑA GOOGLE ADS", True, False, None, False),
    ("OD002", "MKT", "CAMPAÑA MARKETING META BUSINESS", True, False, None, False),
    ("OD003", "MKT", "ADMINISTRACION DE CAMPAÑA META BUSSINESS (20%) SIN ARTE", True, False, None, False),
    ("OD004", "DEV", "CATALOGO DIGITAL ONLINE (MAX 20 ITEMS)", True, False, None, False),
    ("OD005", "DEV", "LANDING PAGE PRODUCTO", True, False, None, False),
    ("OD006", "DEV", "LANDING PAGE BASIC (1PAG)", True, False, None, False),
    ("OD007", "DEV", "TIENDA VIRTUAL ( BASIC - ECOMM)", True, False, None, False),
    ("OD008", "DEV", "PAGINA WEB AUTOADMINISTRABLE", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD009", "DEV", "PAGINA WEB BUSINESS", True, False, None, False),
    ("OD010", "DEV", "BLOG INFORMATIVO WORKPRESS", True, False, None, False),
    ("OD011", "DEV", "MANTENIMIENTO /ACTUALIZACIONES", True, False, None, False),
    ("OD012", "DEV", "PAGINA WEB BASIC PLANTILLA", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD013", "DEV", "PROMO WEB BASIC+ HOSTING + DOMINIO HTML + CSS + JS", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD014", "DSGN", "HORA DE DISEÑO", True, False, None, False),
    ("OD015", "DSGN", "LOGO +", True, False, None, False),
    ("OD016", "DSGN", "LOGO FULL", True, False, None, False),
    ("OD017", "DSGN", "PACK PLANTILLA EDIT 5 HISTORIAS", True, False, None, False),
    ("OD018", "DSGN", "PACK PLANTILLA EDIT 6 POST", True, False, None, False),
    ("OD019", "DSGN", "HISTORIAS (ADICIONAL**)", True, False, None, False),
    ("OD020", "DSGN", "POST (ADICIONAL**)", True, False, None, False),
    ("OD021", "DSGN", "PACK HIGHLIGHTS", True, False, None, False),
    ("OD022", "DSGN", "DISEÑO TARJETA 8X5", True, False, None, False),
    ("OD023", "DSGN", "LOGO ESSENTIALS (LOGO BASIC + EDITABLE)", True, True, None, True), # ventulab=True, is_package=True
    ("OD024", "DSGN", "CATALOGO PDF (MAX 4 PAG)", True, False, None, False),
    ("OD025", "DSGN", "MANUAL / CATALOGO (MAX 20 PAG)", True, False, None, False),
    ("OD026", "DSGN", "DISEÑO EDITABLE CANVA", True, False, None, False),
    ("OD027", "SMM", "CM PLAN SEMILLA", True, False, None, False),
    ("OD028", "SMM", "CM PLAN SEMILLA +", True, False, None, False),
    ("OD029", "SMM", "CM INICIA", True, False, None, False),
    ("OD030", "SMM", "CM IMPULSA", True, False, None, False),
    ("OD031", "SMM", "CM INNOVA", True, False, None, False),
    ("OD032", "BRND", "BRANDING IDENTITY FUSION", True, False, None, False),
    ("OD033", "BRND", "BRANDING IDENTITY PRO", True, False, None, False),
    ("OD034", "BRND", "BRAND STRATEGY (ESTRATEGIA DE MARCA)", True, False, None, False),
    ("OD035", "BRND", "REBRANDING Y REDISEÑO DE MARCA", True, False, None, False),
    ("OD036", "BRND", "NAMING", True, False, None, False),
    ("OD037", "AVP", "REELS & TIKTOK", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD038", "AVP", "PRODUCCION AUDIOVISUAL 5MIN (CAMARA + DRONE)", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD039", "AVP", "MINUTO DE EDICIÓN | POSTPRODUCCIÓN DE VIDEO | BASIC", True, False, None, False),
    ("OD040", "AVP", "SEGUNDO DE ANIMACIÓN | MOTION GRAPHICS | LOGO 2D", True, False, None, False),
    ("OD041", "AVP", "SEGUNDO DE ANIMACION | RENDER 3D | ARQUITECTONICO", True, False, None, False),
    ("OD042", "AVP", "PACK 3 REELS & TIKTOK", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD043", "AVP", "FLYER MOTION+ (FLYER DIGITAL + FLYER ANIMADO MAX 20SEG)", True, False, None, False),
    ("OD044", "AVP", "REEL BASICO (MAX 60S)", True, False, None, False),
    ("OD045", "AVP", "MINUTO DE EDICIÓN | POSTPRODUCCIÓN DE VIDEO | PRO | VFX + SOUND + MULTI LAYER", True, False, None, False),
    ("OD046", "DSGN", "LOGO SIGNATURE", True, False, None, False),
    ("OD047", "BRND", "BRAND+", True, True, None, True), # ventulab=True, is_package=True
    ("OD048", "DEV", "DIGITAL STARTER WEB BASIC .CL", True, True, None, True), # ventulab=True, is_package=True
    ("OD049", "DEV", "DIGITAL STARTER WEB BASIC .COM", True, True, None, True), # ventulab=True, is_package=True
    ("OD050", "BRND", "IMPULSO DIGITAL", True, True, None, True), # ventulab=True, is_package=True
    ("OD051", "DSGN", "ESSENTIALS PRO", True, True, None, True), # ventulab=True, is_package=True
    ("OD052", "DSGN", "FLYER DIGITAL", True, False, None, False),
    ("OD053", "AVP", "FLYER MOTION MAX25SEG", True, False, None, False),
    ("OD054", "DSGN", "FLYER 10X14 FULL COLOR DOS CARAS( PAQ 1000)", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
    ("OD055", "DSGN", "FLYER 10X14 FULL COLOR DOS CARAS( PAQ 500)", True, False, "DSXM25", False), # Asume campaña DSXM25 existe
]

# Mantener los detalles solo para los códigos ODxxx que los tenían
SERVICE_DETAILS_DATA = {
    "OD004": {"audience": "Pequeñas y medianas empresas...", "description": "Creación de un catálogo digital online...", "resuelve": "Falta de una plataforma digital eficiente..."},
    "OD005": {"audience": "Empresas que desean destacar un producto...", "description": "Diseño y desarrollo de una landing page...", "resuelve": "Necesidad de una página de aterrizaje efectiva..."},
    "OD007": {"audience": "Empresas pequeñas y medianas que desean iniciar...", "description": "Desarrollo de una tienda virtual básica...", "resuelve": "Necesidad de una plataforma de comercio electrónico funcional..."},
    "OD008": {"audience": "Empresas que necesitan un sitio web que puedan actualizar...", "description": "Desarrollo de un sitio web autoadministrable...", "resuelve": "Falta de control sobre el contenido..."},
    "OD009": {"audience": "Empresas medianas y grandes...", "description": "Desarrollo de un sitio web empresarial...", "resuelve": "Necesidad de un sitio web avanzado..."},
    "OD012": {"audience": "Emprendedores y pequeñas empresas...", "description": "Desarrollo de una página web básica utilizando plantilla...", "resuelve": "Falta de una presencia digital básica..."},
    "OD015": {"audience": "Empresas en crecimiento que necesitan...", "description": "Un paquete de diseño de logo avanzado...", "resuelve": "La necesidad de un logo más versátil..."},
    "OD016": {"audience": "Empresas que requieren un logo altamente adaptable...", "description": "El paquete completo de diseño de logo...", "resuelve": "La necesidad de un logo completamente adaptable..."},
    "OD023": {"audience": "Startups, pequeños negocios...", "description": "Ideal para pequeñas empresas o startups que necesitan un logo funcional...", "resuelve": "La necesidad de un diseño de logo asequible..."},
    "OD027": {"audience": "Startups, pequeñas empresas...", "description": "Gestión básica de redes sociales...", "resuelve": "Falta de visibilidad en redes sociales..."},
    "OD028": {"audience": "Pequeñas y medianas empresas que buscan crecimiento...", "description": "Gestión avanzada de redes sociales...", "resuelve": "Necesidad de una estrategia más avanzada..."},
    "OD029": {"audience": "Pequeñas y medianas empresas que buscan manejo sólido...", "description": "Servicio de gestión de redes sociales diseñado...", "resuelve": "Falta de una estrategia coherente..."},
    "OD030": {"audience": "Empresas medianas y en crecimiento...", "description": "Gestión integral de redes sociales...", "resuelve": "Necesidad de una estrategia más robusta..."},
    "OD031": {"audience": "Empresas en sectores competitivos...", "description": "Servicio de gestión altamente personalizado...", "resuelve": "Necesidad de innovación constante..."},
    "OD032": {"audience": "Empresas medianas y grandes que buscan establecer...", "description": "Servicio integral de identidad de marca...", "resuelve": "Necesidad de una identidad coherente..."},
    "OD033": {"audience": "Corporaciones y marcas establecidas...", "description": "Solución de branding de alta gama...", "resuelve": "La necesidad de una identidad alineada..."},
    "OD046": {"audience": "Marcas de alto perfil...", "description": "Un servicio premium que ofrece diseño exclusivo...", "resuelve": "La necesidad de un logo altamente exclusivo..."},
    "OD047": {"audience": "Pequeñas y medianas empresas, emprendedores...", "description": "Un paquete completo para la construcción...", "resuelve": "Falta de una identidad visual clara..."},
    "OD048": {"audience": "Empresas y emprendedores en Chile...", "description": "Paquete de inicio digital que incluye...", "resuelve": "La falta de presencia en línea..."},
    "OD049": {"audience": "Empresas y emprendedores que buscan presencia global...", "description": "Este servicio está orientado a establecer presencia con .COM...", "resuelve": "Necesidad de presencia profesional con .COM..."},
    "OD050": {"audience": "Empresas y emprendedores que desean fortalecer...", "description": "Un paquete integral para potenciar presencia digital...", "resuelve": "Falta de coherencia y efectividad en redes..."},
    "OD051": {"audience": "Empresas que buscan actualizar o reforzar identidad visual...", "description": "Paquete de diseño gráfico avanzado...", "resuelve": "La necesidad de materiales promocionales de alta calidad..."},
}

# ¡¡¡ASEGÚRATE DE COPIAR AQUÍ TODAS LAS FEATURES DEL MARKDOWN PARA LOS CÓDIGOS ODxxx!!!
SERVICE_FEATURES_DATA = [
    # Service_Code, Feature_Type, Description
    ("OD027", "differentiator", "Servicio personalizado según las necesidades de la pequeña empresa."),
    ("OD027", "differentiator", "Uso de herramientas básicas pero efectivas para maximizar resultados."),
    ("OD028", "differentiator", "Estrategias más complejas y adaptadas a la evolución de la marca."),
    ("OD028", "differentiator", "Enfoque en el crecimiento y la optimización constante."),
    ("OD028", "differentiator", "Reportes más frecuentes y detallados."),
    ("OD029", "differentiator", "Estrategias de contenido altamente personalizadas."),
    ("OD029", "differentiator", "Monitoreo y optimización constante."),
    ("OD029", "differentiator", "Reportes detallados con recomendaciones accionables."),
    ("OD030", "differentiator", "Enfoque en estrategias escalables y de alto impacto."),
    ("OD030", "differentiator", "Monitoreo constante y ajuste dinámico de la estrategia."),
    ("OD030", "differentiator", "Integración con otras áreas de marketing digital para maximizar resultados."),
    ("OD031", "differentiator", "Enfoque en la innovación y la creatividad."),
    ("OD031", "differentiator", "Uso de tecnologías avanzadas y tendencias emergentes."),
    ("OD031", "differentiator", "Adaptación rápida y flexible a cambios en el mercado."),
    ("OD004", "differentiator", "Diseño personalizado según la identidad de la marca."),
    ("OD004", "differentiator", "Optimización para SEO que mejora la visibilidad online."),
    ("OD004", "differentiator", "Interfaz amigable y fácil de actualizar."),
    ("OD005", "differentiator", "Diseño personalizado que refleja la identidad de la marca."),
    ("OD005", "differentiator", "Enfoque en la optimización para la conversión."),
    ("OD005", "differentiator", "Integración con herramientas avanzadas de análisis."),
    ("OD006", "differentiator", "Proceso ágil y enfoque en resultados rápidos."),
    ("OD006", "differentiator", "Diseño simple pero efectivo."),
    ("OD006", "differentiator", "Optimización para SEO y dispositivos móviles."),
    ("OD007", "differentiator", "Enfoque en la simplicidad y la funcionalidad."),
    ("OD007", "differentiator", "Costo accesible para pequeños empresarios."),
    ("OD007", "differentiator", "Posibilidad de escalar la tienda a medida que crece el negocio."),
    ("OD008", "differentiator", "Interfaz fácil de usar para usuarios sin conocimientos técnicos."),
    ("OD008", "differentiator", "Capacitación y soporte continuo."),
    ("OD008", "differentiator", "Flexibilidad para agregar nuevas funcionalidades según el crecimiento del negocio."),
    ("OD009", "differentiator", "Personalización completa según las necesidades empresariales."),
    ("OD009", "differentiator", "Integración con sistemas existentes y futuras expansiones."),
    ("OD009", "differentiator", "Soporte técnico dedicado y mantenimiento continuo."),
    ("OD012", "differentiator", "Costo muy accesible."),
    ("OD012", "differentiator", "Diseño profesional y estandarizado."),
    ("OD012", "differentiator", "Proceso de desarrollo rápido."),
    ("OD023", "differentiator", "Diseño centrado en la simplicidad y funcionalidad."),
    ("OD023", "differentiator", "Flexibilidad para realizar cambios futuros sin incurrir en costos adicionales."),
    ("OD023", "differentiator", "Asesoría y soporte post-entrega para garantizar el uso correcto del logo."),
    ("OD032", "differentiator", "Enfoque integral que abarca todos los aspectos de la identidad de marca."),
    ("OD032", "differentiator", "Asesoría estratégica continua para asegurar la correcta implementación de la identidad."),
    ("OD032", "differentiator", "Entrega de herramientas y guías que permiten mantener la coherencia a largo plazo."),
    ("OD033", "differentiator", "Proceso colaborativo que garantiza que la identidad de marca refleje auténticamente los valores y objetivos de la empresa."),
    ("OD033", "differentiator", "Enfoque estratégico en la implementación para maximizar el impacto de la marca."),
    ("OD033", "differentiator", "Soporte continuo para ajustes y optimización a medida que la marca evoluciona."),
    # Duplicados OD023 differentiator, se omiten
    ("OD015", "differentiator", "Diseño de variantes para diferentes aplicaciones."),
    ("OD015", "differentiator", "Entrega completa de archivos y soporte para implementación."),
    ("OD015", "differentiator", "Adaptación del logo para diversos medios y usos."),
    ("OD016", "differentiator", "Paquete completo que cubre todas las necesidades de diseño del logo."),
    ("OD016", "differentiator", "Flexibilidad y adaptabilidad total para cualquier uso o plataforma."),
    ("OD016", "differentiator", "Soporte completo para asegurar una implementación efectiva."),
    ("OD046", "differentiator", "Diseño exclusivo y altamente personalizado."),
    ("OD046", "differentiator", "Enfoque en la creación de una identidad visual que realmente marque la diferencia."),
    ("OD046", "differentiator", "Proceso de diseño detallado y personalizado."),
    ("OD047", "differentiator", "Enfoque personalizado con atención al detalle."),
    ("OD047", "differentiator", "Entrega de un paquete completo de branding, todo en uno."),
    ("OD048", "differentiator", "Solución rápida y económica para la presencia en línea."),
    ("OD048", "differentiator", "Todo incluido: hosting, dominio, y seguridad web."),
    ("OD049", "differentiator", "Paquete económico para una presencia digital internacional."),
    ("OD049", "differentiator", "Todo incluido con foco en la expansión global."),
    ("OD050", "differentiator", "Enfoque integral en branding y estrategia en redes sociales."),
    ("OD050", "differentiator", "Personalización y adaptabilidad según la marca y el mercado."),
    ("OD051", "differentiator", "Foco en la calidad y detalle en el diseño."),
    ("OD051", "differentiator", "Paquete completo para renovación y fortalecimiento de la imagen de marca."),

    ("OD027", "benefit", "Gestión básica de redes sociales para pequeñas empresas que desean comenzar a construir su presencia en línea de manera efectiva y asequible."),
    ("OD027", "benefit", "Publicaciones regulares que mantienen activa la presencia de la marca en redes sociales."),
    ("OD027", "benefit", "Gestión económica y eficiente de la comunidad."),
    ("OD028", "benefit", "Gestión avanzada de redes sociales para pequeñas empresas, con un enfoque en el crecimiento y la interacción significativa con la audiencia, con opciones para agregar servicios adicionales según las necesidades."),
    ("OD028", "benefit", "Estrategias personalizadas que alinean con los objetivos de negocio."),
    ("OD028", "benefit", "Crecimiento continuo y sostenido en redes sociales."),
    ("OD029", "benefit", "Servicio de gestión de redes sociales diseñado para empresas que desean establecer una fuerte presencia online y aumentar la interacción con su audiencia, con la posibilidad de añadir servicios adicionales según necesidades específicas."),
    ("OD029", "benefit", "Aumento significativo en la participación y crecimiento de la comunidad."),
    ("OD029", "benefit", "Optimización constante para mejorar el rendimiento de las campañas."),
    ("OD030", "benefit", "Gestión integral de redes sociales para empresas que buscan maximizar su presencia online, alcanzar nuevos mercados y aumentar significativamente su base de seguidores y la interacción con su audiencia."),
    ("OD030", "benefit", "Estrategias avanzadas para captar y retener audiencia."),
    ("OD030", "benefit", "Reportes y análisis detallados que guían la toma de decisiones."),
    ("OD031", "benefit", "Servicio de gestión de redes sociales altamente personalizado y de vanguardia, diseñado para empresas que desean innovar y mantenerse a la vanguardia de las tendencias de marketing digital."),
    ("OD031", "benefit", "Adaptación rápida a nuevas tendencias y tecnologías."),
    ("OD031", "benefit", "Maximización del impacto y la resonancia de la marca."),
    ("OD004", "benefit", "Creación de un catálogo digital online que permite a las empresas mostrar hasta 20 productos, con opciones de personalización y optimización para SEO."),
    ("OD004", "benefit", "Optimización para motores de búsqueda (SEO)."),
    ("OD004", "benefit", "Interfaz fácil de usar y personalizable."),
    ("OD005", "benefit", "Diseño y desarrollo de una landing page optimizada para la conversión, enfocada en un solo producto o servicio."),
    ("OD005", "benefit", "Optimización para SEO y velocidad de carga."),
    ("OD005", "benefit", "Integración con herramientas de análisis y seguimiento."),
    ("OD006", "benefit", "Landing page básica de una sola página diseñada para captar leads y destacar información clave de un producto o servicio."),
    ("OD006", "benefit", "Diseño centrado en la captación de leads."),
    ("OD006", "benefit", "Optimización básica para SEO y dispositivos móviles."),
    ("OD007", "benefit", "Desarrollo de una tienda virtual básica, enfocada en la venta de productos físicos o digitales con características esenciales de comercio electrónico."),
    ("OD007", "benefit", "Interfaz amigable y fácil de gestionar."),
    ("OD007", "benefit", "Integración con pasarelas de pago populares."),
    ("OD008", "benefit", "Desarrollo de un sitio web autoadministrable, donde la empresa puede gestionar su contenido de manera independiente, ideal para empresas que requieren actualizaciones frecuentes."),
    ("OD008", "benefit", "Fácil de usar con una interfaz intuitiva."),
    ("OD008", "benefit", "Soporte técnico para formación y resolución de dudas."),
    ("OD009", "benefit", "Desarrollo de un sitio web empresarial de alto nivel con características avanzadas y personalización completa, ideal para empresas que buscan una presencia digital robusta y profesional."),
    ("OD009", "benefit", "Funcionalidades avanzadas para empresas."),
    ("OD009", "benefit", "Soporte continuo y mantenimiento a largo plazo."),
    ("OD012", "benefit", "Desarrollo de una página web básica utilizando una plantilla predefinida, ideal para pequeñas empresas o emprendedores que necesitan una presencia en línea asequible."),
    ("OD012", "benefit", "Diseño profesional basado en plantillas."),
    ("OD012", "benefit", "Fácil de mantener y actualizar."),
    ("OD023", "benefit", "Desarrollo de un logo básico, con la opción de obtener versiones editables para que la empresa pueda hacer ajustes menores en el futuro sin necesidad de recurrir a un diseñador."),
    ("OD023", "benefit", "Flexibilidad para realizar ajustes y personalizaciones en el futuro."),
    ("OD023", "benefit", "Ahorro en costos de diseño a largo plazo al poder editar el logo internamente."),
    ("OD032", "benefit", "Servicio integral de identidad de marca que combina elementos visuales, verbales y estratégicos para crear una identidad de marca cohesiva y poderosa."),
    ("OD032", "benefit", "Alineación de todos los elementos de la marca, desde el logo hasta el tono de voz, con los objetivos estratégicos de la empresa."),
    ("OD032", "benefit", "Incremento en el reconocimiento y la percepción positiva de la marca."),
    ("OD033", "benefit", "Solución de branding de alta gama que incluye el desarrollo completo de la identidad de marca y su implementación estratégica, diseñada para empresas que buscan posicionarse como líderes en su industria."),
    ("OD033", "benefit", "Implementación estratégica de la identidad en todos los puntos de contacto, asegurando coherencia y impacto."),
    ("OD033", "benefit", "Fortalecimiento del posicionamiento de la marca como líder en su industria."),
    # Duplicados OD023 benefit, se omiten
    ("OD015", "benefit", "Un paquete de diseño de logo avanzado que incluye más variantes y elementos adicionales para adaptar el logo a diferentes usos y plataformas."),
    ("OD015", "benefit", "Variantes del logo para diferentes aplicaciones, como redes sociales, impresión y web."),
    ("OD015", "benefit", "Archivos adicionales y soporte para implementar el logo en distintas situaciones."),
    ("OD016", "benefit", "El paquete completo de diseño de logo que incluye el diseño principal y todas las variantes necesarias para asegurar la máxima flexibilidad y aplicabilidad en cualquier contexto."),
    ("OD016", "benefit", "Incluye todas las variantes necesarias para aplicaciones específicas."),
    ("OD016", "benefit", "Acceso a todos los archivos y formatos necesarios para la implementación."),
    ("OD046", "benefit", "Un servicio premium que ofrece un diseño de logo exclusivo y personalizado, con una identidad de marca única y distintiva que marca la diferencia en el mercado."),
    ("OD046", "benefit", "Identidad visual que se diferencia claramente de la competencia."),
    ("OD046", "benefit", "Proceso de diseño personalizado que asegura una representación auténtica de la marca."),
    ("OD047", "benefit", "Establece una imagen de marca profesional y consistente."),
    ("OD047", "benefit", "Aumenta el reconocimiento y la credibilidad de la marca."),
    ("OD048", "benefit", "Establecimiento de una presencia digital profesional con una inversión mínima."),
    ("OD048", "benefit", "Seguridad y credibilidad mejoradas gracias al certificado SSL."),
    ("OD049", "benefit", "Dominio .COM, reconocido a nivel mundial."),
    ("OD049", "benefit", "Seguridad y profesionalismo mejorados."),
    ("OD050", "benefit", "Mejora de la presencia y reputación en redes sociales."),
    ("OD050", "benefit", "Estrategia de contenido optimizada para mayor alcance y engagement."),
    ("OD051", "benefit", "Mejora de la identidad visual y presentación de la marca."),
    ("OD051", "benefit", "Material promocional cohesivo y de alta calidad."),

    ("OD023", "caracteristicas", "Diseño de un logo básico, ideal para empresas que inician su trayectoria."),
    ("OD023", "caracteristicas", "Entrega del logo en formatos editables (como .AI o .PSD), permitiendo modificaciones internas."),
    ("OD023", "caracteristicas", "Instrucciones de uso incluidas para garantizar que las ediciones mantengan la coherencia visual."),
    ("OD032", "caracteristicas", "Desarrollo de un sistema de identidad visual completo, incluyendo logo, paleta de colores, tipografía, y más."),
    ("OD032", "caracteristicas", "Creación de guías de estilo para el uso correcto de la identidad en todos los medios y puntos de contacto."),
    ("OD032", "caracteristicas", "Definición de la estrategia de comunicación, incluyendo tono de voz y mensajes clave."),
    ("OD033", "caracteristicas", "Investigación exhaustiva del mercado, la competencia y la audiencia objetivo."),
    ("OD033", "caracteristicas", "Desarrollo de un sistema de identidad visual y verbal que incluye todos los aspectos de la marca."),
    ("OD033", "caracteristicas", "Creación de una estrategia de implementación detallada que garantiza el éxito en la comunicación de la identidad."),
    # Duplicados OD023 caracteristicas, se omiten
    ("OD015", "caracteristicas", "Diseño de varias versiones del logo para adaptarse a diferentes formatos y aplicaciones."),
    ("OD015", "caracteristicas", "Entrega de todos los archivos necesarios para implementar el logo en distintos medios."),
    ("OD015", "caracteristicas", "Asesoría sobre el uso y aplicación del logo en diferentes contextos."),
    ("OD016", "caracteristicas", "Diseño del logo principal junto con todas las variantes necesarias para diferentes aplicaciones."),
    ("OD016", "caracteristicas", "Entrega de todos los archivos y formatos, incluyendo versiones para web, impresión y redes sociales."),
    ("OD016", "caracteristicas", "Asesoría sobre cómo utilizar y adaptar el logo para distintas plataformas y necesidades."),
    ("OD046", "caracteristicas", "Diseño completamente personalizado y exclusivo para la marca."),
    ("OD046", "caracteristicas", "Proceso de desarrollo detallado, incluyendo investigaciones y pruebas para garantizar la eficacia del diseño."),
    ("OD046", "caracteristicas", "Entrega de un paquete completo con todos los archivos y formatos necesarios."),
    ("OD047", "caracteristicas", "Diseño personalizado de logotipo y material de marketing."),
    ("OD047", "caracteristicas", "Plantillas adaptables para redes sociales."),
    ("OD047", "caracteristicas", "Elementos visuales integrados que refuerzan la identidad de la marca."),
    ("OD048", "caracteristicas", "Landing page personalizada."),
    ("OD048", "caracteristicas", "Correo corporativo para una comunicación más profesional."),
    ("OD048", "caracteristicas", "Hosting y dominio asegurados por un año."),
    ("OD049", "caracteristicas", "Diseño y desarrollo de landing page."),
    ("OD049", "caracteristicas", "Correo corporativo."),
    ("OD049", "caracteristicas", "Hosting y dominio .COM por un año."),
    ("OD049", "caracteristicas", "Certificado SSL para seguridad."),
    ("OD050", "caracteristicas", "Configuración profesional de Meta Business y perfiles en redes sociales."),
    ("OD050", "caracteristicas", "Análisis y optimización de contenido clave."),
    ("OD050", "caracteristicas", "Diseño personalizado para branding en redes sociales."),
    ("OD051", "caracteristicas", "Rebranding de logotipo y diseño de catálogo digital."),
    ("OD051", "caracteristicas", "Flyers y fichas técnicas personalizadas."),
    ("OD051", "caracteristicas", "Integración de QR para facilitar la interacción digital."),

    ("OD027", "process", "Definición de objetivos y público objetivo."),
    ("OD027", "process", "Creación de un calendario de contenidos básico."),
    ("OD027", "process", "Publicación y monitoreo diario de las redes."),
    ("OD027", "process", "Revisión mensual de resultados y ajustes."),
    ("OD028", "process", "Análisis de la situación actual y establecimiento de objetivos."),
    ("OD028", "process", "Desarrollo de estrategias de contenido y de crecimiento."),
    ("OD028", "process", "Publicación, monitoreo y ajuste en tiempo real."),
    ("OD028", "process", "Reportes y reuniones quincenales para optimización."),
    ("OD029", "process", "Auditoría inicial de redes sociales y definición de objetivos."),
    ("OD029", "process", "Creación de un plan de contenidos personalizado."),
    ("OD029", "process", "Implementación, monitoreo y ajuste de estrategias."),
    ("OD029", "process", "Análisis mensual de resultados y recomendaciones."),
    ("OD030", "process", "Evaluación exhaustiva y definición de metas a corto y largo plazo."),
    ("OD030", "process", "Desarrollo de una estrategia de contenido avanzada y dinámica."),
    ("OD030", "process", "Gestión diaria con ajustes en tiempo real."),
    ("OD030", "process", "Análisis quincenal y optimización de estrategias."),
    ("OD031", "process", "Análisis de tendencias y benchmarking competitivo."),
    ("OD031", "process", "Desarrollo de estrategias innovadoras y creativas."),
    ("OD031", "process", "Implementación con pruebas y ajustes continuos."),
    ("OD031", "process", "Revisión trimestral de resultados y ajuste estratégico."),
    ("OD004", "process", "Reunión inicial para definir la estructura del catálogo."),
    ("OD004", "process", "Diseño y personalización de plantillas."),
    ("OD004", "process", "Subida y optimización de productos."),
    ("OD004", "process", "Revisión y ajustes finales antes del lanzamiento."),
    ("OD005", "process", "Reunión para definir objetivos y enfoque de la landing page."),
    ("OD005", "process", "Diseño y desarrollo basado en principios de UX/UI."),
    ("OD005", "process", "Optimización de la página para velocidad y SEO."),
    ("OD005", "process", "Pruebas y ajustes antes del lanzamiento."),
    ("OD006", "process", "Reunión para entender los objetivos y el mensaje clave."),
    ("OD006", "process", "Diseño y desarrollo de la landing page."),
    ("OD006", "process", "Optimización para SEO y pruebas de usabilidad."),
    ("OD006", "process", "Lanzamiento y análisis de rendimiento."),
    ("OD007", "process", "Reunión inicial para definir los productos y las características esenciales."),
    ("OD007", "process", "Desarrollo y personalización de la tienda virtual."),
    ("OD007", "process", "Integración con sistemas de pago y logística."),
    ("OD007", "process", "Pruebas y lanzamiento."),
    ("OD008", "process", "Reunión para definir las necesidades y funcionalidades del sitio."),
    ("OD008", "process", "Desarrollo y personalización del sitio web."),
    ("OD008", "process", "Formación en la gestión del sitio para el equipo de la empresa."),
    ("OD008", "process", "Soporte post-lanzamiento para asegurar una transición suave."),
    ("OD009", "process", "Análisis detallado de las necesidades de la empresa."),
    ("OD009", "process", "Diseño y desarrollo personalizado."),
    ("OD009", "process", "Integración con sistemas empresariales existentes."),
    ("OD009", "process", "Pruebas exhaustivas y optimización para el lanzamiento."),
    ("OD012", "process", "Selección de una plantilla predefinida."),
    ("OD012", "process", "Personalización básica según la identidad de la marca."),
    ("OD012", "process", "Carga de contenido y optimización para SEO."),
    ("OD012", "process", "Lanzamiento rápido y sencillo."),
    ("OD023", "process", "Briefing Inicial: Recopilación de información sobre la marca y sus necesidades."),
    ("OD023", "process", "Diseño del Logo Básico: Creación de un logo que refleje la esencia de la marca."),
    ("OD023", "process", "Entrega de Archivos: Suministro de archivos editables y guía de uso."),
    ("OD023", "process", "Capacitación Opcional: Orientación sobre cómo realizar ediciones sin comprometer la calidad del logo."),
    ("OD032", "process", "Consultoría Estratégica: Sesiones para entender la visión, misión y objetivos de la empresa."),
    ("OD032", "process", "Desarrollo de la Identidad Visual: Creación de todos los elementos gráficos que representarán a la marca."),
    ("OD032", "process", "Definición de la Estrategia de Comunicación: Establecimiento del tono y estilo de comunicación de la marca."),
    ("OD032", "process", "Entrega de Guías de Uso: Documentos detallados que aseguran la coherencia en la implementación de la identidad."),
    ("OD033", "process", "Análisis y Estrategia: Estudio profundo del mercado y la marca para definir una estrategia de branding efectiva."),
    ("OD033", "process", "Desarrollo Integral de la Identidad: Creación de todos los elementos visuales, verbales y estratégicos de la marca."),
    ("OD033", "process", "Implementación Estratégica: Aplicación de la identidad en todos los medios, asegurando coherencia y eficacia."),
    ("OD033", "process", "Monitoreo y Optimización: Seguimiento continuo para ajustar y mejorar la implementación según los resultados."),
    # Duplicados OD023 process, se omiten
    ("OD015", "process", "Entrevista Inicial: Recopilación de información para entender las necesidades específicas del cliente."),
    ("OD015", "process", "Diseño y Variantes: Creación de un logo principal y sus variantes para diferentes usos."),
    ("OD015", "process", "Entrega y Soporte: Provisión de todos los archivos necesarios y soporte para la implementación."),
    ("OD016", "process", "Consulta Inicial: Reunión para definir las necesidades específicas del cliente."),
    ("OD016", "process", "Diseño Integral: Creación del logo principal y sus variantes."),
    ("OD016", "process", "Entrega Completa: Suministro de todos los archivos necesarios y asesoría para su uso."),
    ("OD046", "process", "Consulta Exclusiva: Entrevista profunda para entender los valores y objetivos de la marca."),
    ("OD046", "process", "Diseño Personalizado: Creación de un logo único basado en la identidad de la marca."),
    ("OD046", "process", "Entrega Completa: Provisión de todos los archivos necesarios y guía para el uso del logo."),
    ("OD047", "process", "Análisis de la marca y el mercado."),
    ("OD047", "process", "Diseño de logotipo y materiales gráficos."),
    ("OD047", "process", "Revisión y ajustes según retroalimentación del cliente."),
    ("OD047", "process", "Entrega de los archivos finales en diferentes formatos."),
    ("OD048", "process", "Recopilación de requerimientos del cliente."),
    ("OD048", "process", "Configuración del dominio y hosting."),
    ("OD048", "process", "Diseño y desarrollo de la landing page."),
    ("OD048", "process", "Configuración del correo corporativo y certificado SSL."),
    ("OD048", "process", "Revisión final y lanzamiento."),
    ("OD049", "process", "Recopilación de requerimientos del cliente."),
    ("OD049", "process", "Configuración del dominio y hosting."),
    ("OD049", "process", "Diseño y desarrollo de la landing page."),
    ("OD049", "process", "Configuración del correo corporativo y certificado SSL."),
    ("OD049", "process", "Revisión final y lanzamiento."),
    ("OD050", "process", "Evaluación de la presencia actual en redes sociales."),
    ("OD050", "process", "Configuración y optimización de perfiles."),
    ("OD050", "process", "Creación y diseño de contenido."),
    ("OD050", "process", "Implementación y seguimiento de la estrategia."),
    ("OD051", "process", "Análisis de la marca y sus necesidades visuales."),
    ("OD051", "process", "Diseño y desarrollo de logotipos y materiales promocionales."),
    ("OD051", "process", "Implementación de elementos interactivos como QR."),
    ("OD051", "process", "Revisión y entrega de materiales."),

    ("OD027", "result", "Aumento en la cantidad de seguidores y en la interacción con la audiencia."),
    ("OD027", "result", "Presencia digital establecida y activa en redes sociales."),
    ("OD027", "result", "Base sólida para futuras estrategias de marketing digital."),
    ("OD028", "result", "Crecimiento más rápido y sostenido en redes sociales."),
    ("OD028", "result", "Aumento en las interacciones y en la lealtad de la comunidad."),
    ("OD028", "result", "Mejor alineación de la estrategia de redes sociales con los objetivos del negocio."),
    ("OD029", "result", "Incremento en seguidores, interacciones y visibilidad de la marca."),
    ("OD029", "result", "Establecimiento de una estrategia de contenido a largo plazo."),
    ("OD029", "result", "Mejora continua en el rendimiento de las redes sociales."),
    ("OD030", "result", "Crecimiento exponencial en seguidores y engagement."),
    ("OD030", "result", "Expansión de la presencia de la marca en nuevas plataformas."),
    ("OD030", "result", "Mejora significativa en la conversión de leads a clientes."),
    ("OD031", "result", "Liderazgo en la industria a través de la innovación en redes sociales."),
    ("OD031", "result", "Mayor resonancia y conexión emocional con la audiencia."),
    ("OD031", "result", "Crecimiento sostenido y relevante en seguidores e interacción."),
    ("OD004", "result", "Catálogo digital atractivo y funcional."),
    ("OD004", "result", "Mayor visibilidad de los productos en línea."),
    ("OD004", "result", "Mejora en la conversión de visitantes a clientes."),
    ("OD005", "result", "Aumento significativo en la tasa de conversión."),
    ("OD005", "result", "Mayor visibilidad y tráfico hacia el producto o servicio destacado."),
    ("OD005", "result", "Mejora en la retención de visitantes y en la generación de leads."),
    ("OD006", "result", "Captación efectiva de leads."),
    ("OD006", "result", "Mayor visibilidad online con una inversión mínima."),
    ("OD006", "result", "Facilidad para actualizar y mantener la página."),
    ("OD007", "result", "Tienda virtual operativa y lista para vender."),
    ("OD007", "result", "Facilidad de gestión de productos y pedidos."),
    ("OD007", "result", "Incremento en las ventas y la visibilidad online."),
    ("OD008", "result", "Control total sobre el contenido y actualizaciones del sitio."),
    ("OD008", "result", "Ahorro en costos de mantenimiento a largo plazo."),
    ("OD008", "result", "Mayor agilidad en la gestión del sitio web."),
    ("OD009", "result", "Presencia digital fuerte y profesional."),
    ("OD009", "result", "Sitio web que soporta y mejora las operaciones empresariales."),
    ("OD009", "result", "Aumento en la confianza y percepción de la marca."),
    ("OD012", "result", "Sitio web funcional y listo para usar."),
    ("OD012", "result", "Mayor visibilidad online con una inversión mínima."),
    ("OD012", "result", "Facilidad para actualizar y mantener el sitio."),
    ("OD023", "result", "Un logo que sirve como base sólida para la identidad visual de la marca."),
    ("OD023", "result", "Capacidad de la empresa para mantener la coherencia visual sin depender completamente de servicios externos."),
    ("OD023", "result", "Mayor control sobre la identidad de marca."),
    ("OD032", "result", "Identidad de marca robusta que comunica claramente los valores y promesas de la empresa."),
    ("OD032", "result", "Consistencia en la presentación de la marca en todos los medios y plataformas."),
    ("OD032", "result", "Aumento en la fidelidad de los clientes y reconocimiento de la marca en el mercado."),
    ("OD033", "result", "Una identidad de marca que eleva el perfil de la empresa y la posiciona como líder en su industria."),
    ("OD033", "result", "Consistencia en la presentación de la marca que refuerza la confianza y lealtad de los clientes."),
    ("OD033", "result", "Mayor reconocimiento y preferencia de marca en un mercado competitivo."),
    # Duplicados OD023 result, se omiten
    ("OD015", "result", "Un logo versátil que se adapta a diferentes aplicaciones y plataformas."),
    ("OD015", "result", "Capacidad de implementar el logo en una variedad de contextos sin pérdida de calidad."),
    ("OD015", "result", "Soporte adicional para garantizar el uso efectivo del logo en todas las situaciones."),
    ("OD016", "result", "Un logo que se adapta completamente a todas las necesidades y plataformas."),
    ("OD016", "result", "Consistencia en la identidad de marca a través de todas las aplicaciones."),
    ("OD016", "result", "Soporte para garantizar que el logo se utilice de manera efectiva en todos los contextos."),
    ("OD046", "result", "Una identidad de marca distintiva que destaca en el mercado."),
    ("OD046", "result", "Logo exclusivo que refleja los valores y la visión de la marca."),
    ("OD046", "result", "Impacto significativo y positivo en la percepción de la marca."),
    ("OD047", "result", "Una identidad visual cohesiva que aumente el reconocimiento de la marca y facilite su promoción en diversas plataformas."),
    ("OD048", "result", "Presencia en línea funcional y segura que mejore la visibilidad y profesionalismo del negocio."),
    ("OD049", "result", "Presencia en línea con dominio .COM que aumenta la credibilidad y alcance global del negocio."),
    ("OD050", "result", "Aumento del engagement y visibilidad en redes sociales, con una identidad de marca más fuerte y coherente."),
    ("OD051", "result", "Materiales de marketing de alta calidad que refuercen la presencia de la marca y aumenten su atractivo visual."),
]


# Mantener solo los precios para los códigos ODxxx
PRICES_DATA = {
    "OD027": {"USD": 60, "CLP": 58990, "COP": 0},
    "OD028": {"USD": 140, "CLP": 136990, "COP": 0},
    "OD029": {"USD": 230, "CLP": 218990, "COP": 0},
    "OD030": {"USD": 500, "CLP": 475990, "COP": 0},
    "OD031": {"USD": 1200, "CLP": 1199990, "COP": 0},
    "OD004": {"USD": 160, "CLP": 151990, "COP": 0},
    "OD005": {"USD": 150, "CLP": 141990, "COP": 0},
    "OD006": {"USD": 100, "CLP": 94990, "COP": 0},
    "OD007": {"USD": 3000, "CLP": 2849990, "COP": 0},
    "OD008": {"USD": 300, "CLP": 284990, "COP": 0},
    "OD009": {"USD": 1200, "CLP": 1139990, "COP": 0},
    "OD012": {"USD": 80, "CLP": 75990, "COP": 0},
    "OD032": {"USD": 1200, "CLP": 1139990, "COP": 0},
    "OD033": {"USD": 1800, "CLP": 1709990, "COP": 0},
    "OD023": {"USD": 35, "CLP": 32990, "COP": 0},
    "OD015": {"USD": 160, "CLP": 151990, "COP": 0},
    "OD016": {"USD": 230, "CLP": 217990, "COP": 0},
    "OD046": {"USD": 2290, "CLP": 2199990, "COP": 0},
    "OD047": {"USD": 120, "CLP": 114990, "COP": 0},
    "OD048": {"USD": 145, "CLP": 137990, "COP": 0},
    "OD049": {"USD": 125, "CLP": 118990, "COP": 0},
    "OD050": {"USD": 140, "CLP": 134990, "COP": 0},
    "OD051": {"USD": 210, "CLP": 199990, "COP": 0},
    "OD052": {"USD": 15, "CLP": 14990, "COP": 0},
    "OD053": {"USD": 35, "CLP": 34990, "COP": 0},
    "OD054": {"USD": 75, "CLP": 69990, "COP": 0},
    "OD055": {"USD": 45, "CLP": 45990, "COP": 0},
}
# --- FIN DATOS DEL MARKDOWN ---


def seed_services_catalog(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    print("\n   [INFO] Creando catálogo de Servicios, Precios y Features...")
    Service = apps.get_model('api', 'Service'); Price = apps.get_model('api', 'Price')
    ServiceFeature = apps.get_model('api', 'ServiceFeature'); ServiceCategory = apps.get_model('api', 'ServiceCategory')
    Campaign = apps.get_model('api', 'Campaign')

    campaign_codes_used = {s[5] for s in SERVICES_DATA if s[5]}; campaigns_map = {}
    for code in campaign_codes_used: campaign, _ = Campaign.objects.using(db_alias).get_or_create(campaign_code=code, defaults={'campaign_name': f"Campaña {code}", 'start_date': timezone.now(), 'is_active': True}); campaigns_map[code] = campaign

    service_instances = {}; created_services = 0
    print("     - Creando/Actualizando Servicios (OD001-OD055)...")
    for svc_data in SERVICES_DATA: # Solo los ODxxx
        code, cat_code, name, is_active, ventulab, camp_code, is_package = svc_data; category = None
        try: category = ServiceCategory.objects.using(db_alias).get(code=cat_code)
        except ServiceCategory.DoesNotExist: print(f"       [WARN] Cat '{cat_code}' no encontrada para srv '{code}'. Omitido."); continue
        campaign = campaigns_map.get(camp_code) if camp_code else None; details = SERVICE_DETAILS_DATA.get(code, {})
        # Determinar is_subscription basado en categoría SMM o código específico si es necesario
        is_subscription = (cat_code == 'SMM') or code in ['OD011', 'DEV002'] # Ejemplo
        try:
            service, created = Service.objects.using(db_alias).update_or_create(
                code=code,
                defaults={'category': category, 'name': name, 'is_active': is_active, 'ventulab': ventulab,
                          'campaign': campaign, 'is_package': is_package, 'is_subscription': is_subscription, # Añadido is_subscription
                          'audience': details.get('audience'),'detailed_description': details.get('description'), 'problem_solved': details.get('resuelve')})
            service_instances[code] = service
            if created: created_services += 1
        except Exception as e: print(f"       [ERROR] Creando/Actualizando srv '{code}': {e}")
    print(f"       -> {created_services} Servicios creados/actualizados.")

    created_prices = 0; print("     - Creando Precios...")
    today = datetime.date.today()
    for service_code, prices in PRICES_DATA.items(): # Solo los ODxxx
        service = service_instances.get(service_code);
        if not service: continue
        for currency, amount in prices.items():
            if amount > 0:
                try:
                    _, created = Price.objects.using(db_alias).get_or_create(service=service, currency=currency.upper(), effective_date=today, defaults={'amount': Decimal(str(amount))})
                    if created:
                        created_prices += 1
                except Exception as e:
                    print(f"       [ERROR] Creando precio {currency} para '{service_code}': {e}")
                except Exception as e: print(f"       [ERROR] Creando precio {currency} para '{service_code}': {e}")
    print(f"       -> {created_prices} Precios creados.")

    created_features = 0; print("     - Creando Features...")
    service_codes_with_features = {f[0] for f in SERVICE_FEATURES_DATA} # Solo ODxxx
    ServiceFeature.objects.using(db_alias).filter(service__code__in=service_codes_with_features).delete()
    features_to_bulk_create = []
    for feat_data in SERVICE_FEATURES_DATA: # Solo ODxxx
        service_code, feature_type, description = feat_data; service = service_instances.get(service_code);
        if not service: continue
        features_to_bulk_create.append(ServiceFeature(service=service, feature_type=feature_type.lower(), description=description))
    try:
        if features_to_bulk_create:
            created_objs = ServiceFeature.objects.using(db_alias).bulk_create(features_to_bulk_create)
            created_features = len(created_objs)
    except Exception as e: print(f"       [ERROR] Creando features en bloque: {e}")
    print(f"       -> {created_features} Features creadas.")
    print("   [INFO] Finalizada creación del catálogo.")

def remove_services_catalog(apps, schema_editor):
    db_alias = schema_editor.connection.alias; print("\n   [REVERT] Eliminando catálogo de servicios...")
    # Asegurarse de borrar solo los códigos ODxxx
    service_codes_to_delete = [s[0] for s in SERVICES_DATA]
    models_to_clear = [
         ('api', 'Price', 'service__code__in', service_codes_to_delete),
         ('api', 'ServiceFeature', 'service__code__in', service_codes_to_delete),
         ('api', 'Service', 'code__in', service_codes_to_delete), ]
    for app_label, model_name, filter_lookup, filter_values in models_to_clear:
         if not filter_values: continue; Model = apps.get_model(app_label, model_name);
         count, _ = Model.objects.using(db_alias).filter(**{filter_lookup: filter_values}).delete(); print(f"     - {count} {model_name}(s) eliminados.")
    print("   [REVERT] Finalizada eliminación del catálogo.")


class Migration(migrations.Migration):
    dependencies = [
        # ¡¡¡ASEGÚRATE QUE ESTOS NOMBRES SEAN CORRECTOS!!!
        ('api', '0001_initial'),             # Migración de esquema
        ('api', '0002_seed_initial_data'),    # Migración de datos base
        ('api', '0003_seed_superuser_dorantejds'), # Migración del superusuario
    ]
    operations = [ migrations.RunPython(seed_services_catalog, remove_services_catalog), ]