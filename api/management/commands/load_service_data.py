# api/management/commands/load_service_data.py

import pandas as pd
import io
import math
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import make_aware # Para convertir fechas de campaña

# Importa los modelos relevantes de tu app
from api.models import ServiceCategory, Campaign, Service, Price, ServiceFeature

# --- Contenido de tus tablas Markdown como strings ---
# (Es mejor leer desde archivos CSV si los tienes, pero esto funciona para el ejemplo)

service_data_md = """
| code   | service_   | name                                                                          |   is_active | ventulab   | campaign_code   | is_package   | SubService_   |
|--------|------------|-------------------------------------------------------------------------------|-------------|------------|-----------------|--------------|---------------|
| OD001  | MKT        | CAMPAÑA GOOGLE ADS                                                            |           1 | disable    | nan             | N            | nan           |
| OD002  | MKT        | CAMPAÑA MARKETING META BUSINESS                                               |           1 | disable    | nan             | N            | nan           |
| OD003  | MKT        | ADMINISTRACION DE CAMPAÑA META BUSSINESS (20%) SIN ARTE                       |           1 | disable    | nan             | N            | nan           |
| OD004  | DEV        | CATALOGO DIGITAL ONLINE (MAX 20 ITEMS)                                        |           1 | disable    | nan             | N            | nan           |
| OD005  | DEV        | LANDING PAGE PRODUCTO                                                         |           1 | disable    | nan             | N            | nan           |
| OD006  | DEV        | LANDING PAGE BASIC (1PAG)                                                     |           1 | disable    | nan             | N            | nan           |
| OD007  | DEV        | TIENDA VIRTUAL ( BASIC - ECOMM)                                               |           1 | disable    | nan             | N            | nan           |
| OD008  | DEV        | PAGINA WEB AUTOADMINISTRABLE                                                  |           1 | disable    | DSXM25          | N            | nan           |
| OD009  | DEV        | PAGINA WEB BUSINESS                                                           |           1 | disable    | nan             | N            | nan           |
| OD010  | DEV        | BLOG INFORMATIVO WORKPRESS                                                    |           1 | disable    | nan             | N            | nan           |
| OD011  | DEV        | MANTENIMIENTO /ACTUALIZACIONES                                                |           1 | disable    | nan             | N            | nan           |
| OD012  | DEV        | PAGINA WEB BASIC PLANTILLA                                                    |           1 | disable    | DSXM25          | N            | nan           |
| OD013  | DEV        | PROMO WEB BASIC+  HOSTING + DOMINIO HTML + CSS + JS                           |           1 | disable    | DSXM25          | N            | nan           |
| OD014  | DSGN       | HORA DE  DISEÑO                                                               |           1 | disable    | nan             | N            | nan           |
| OD015  | DSGN       | LOGO +                                                                        |           1 | disable    | nan             | N            | nan           |
| OD016  | DSGN       | LOGO FULL                                                                     |           1 | disable    | nan             | N            | nan           |
| OD017  | DSGN       | PACK PLANTILLA EDIT 5 HISTORIAS                                               |           1 | disable    | nan             | N            | nan           |
| OD018  | DSGN       | PACK PLANTILLA EDIT 6 POST                                                    |           1 | disable    | nan             | N            | nan           |
| OD019  | DSGN       | HISTORIAS  (ADICIONAL**)                                                      |           1 | disable    | nan             | N            | nan           |
| OD020  | DSGN       | POST (ADICIONAL**)                                                            |           1 | disable    | nan             | N            | nan           |
| OD021  | DSGN       | PACK HIGHLIGHTS                                                               |           1 | disable    | nan             | N            | nan           |
| OD022  | DSGN       | DISEÑO TARJETA 8X5                                                            |           1 | disable    | nan             | N            | nan           |
| OD023  | DSGN       | LOGO ESSENTIALS (LOGO BASIC  + EDITABLE)                                      |           1 | enable     | nan             | Y            | nan           |
| OD024  | DSGN       | CATALOGO PDF (MAX 4 PAG)                                                      |           1 | disable    | nan             | N            | nan           |
| OD025  | DSGN       | MANUAL / CATALOGO (MAX 20 PAG)                                                |           1 | disable    | nan             | N            | nan           |
| OD026  | DSGN       | DISEÑO EDITABLE CANVA                                                         |           1 | disable    | nan             | N            | nan           |
| OD027  | SMM        | CM PLAN SEMILLA                                                               |           1 | disable    | nan             | N            | nan           |
| OD028  | SMM        | CM PLAN SEMILLA +                                                             |           1 | disable    | nan             | N            | nan           |
| OD029  | SMM        | CM INICIA                                                                     |           1 | disable    | nan             | N            | nan           |
| OD030  | SMM        | CM IMPULSA                                                                    |           1 | disable    | nan             | N            | nan           |
| OD031  | SMM        | CM INNOVA                                                                     |           1 | disable    | nan             | N            | nan           |
| OD032  | BRND       | BRANDING IDENTITY FUSION                                                      |           1 | disable    | nan             | N            | nan           |
| OD033  | BRND       | BRANDING IDENTITY PRO                                                         |           1 | disable    | nan             | N            | nan           |
| OD034  | BRND       | BRAND STRATEGY (ESTRATEGIA DE MARCA)                                          |           1 | disable    | nan             | N            | nan           |
| OD035  | BRND       | REBRANDING Y REDISEÑO DE MARCA                                                |           1 | disable    | nan             | N            | nan           |
| OD036  | BRND       | NAMING                                                                        |           1 | disable    | nan             | N            | nan           |
| OD037  | AVP        | REELS & TIKTOK                                                                |           1 | disable    | DSXM25          | N            | nan           |
| OD038  | AVP        | PRODUCCION AUDIOVISUAL 5MIN (CAMARA + DRONE)                                  |           1 | disable    | DSXM25          | N            | nan           |
| OD039  | AVP        | MINUTO DE EDICIÓN | POSTPRODUCCIÓN DE VIDEO | BASIC                           |           1 | disable    | nan             | N            | nan           |
| OD040  | AVP        | SEGUNDO  DE ANIMACIÓN | MOTION GRAPHICS | LOGO 2D                             |           1 | disable    | nan             | N            | nan           |
| OD041  | AVP        | SEGUNDO DE ANIMACION | RENDER 3D | ARQUITECTONICO                             |           1 | disable    | nan             | N            | nan           |
| OD042  | AVP        | PACK 3 REELS & TIKTOK                                                         |           1 | disable    | DSXM25          | N            | nan           |
| OD043  | AVP        | FLYER MOTION+ (FLYER DIGITAL + FLYER ANIMADO MAX 20SEG)                       |           1 | disable    | nan             | N            | AVP22HD       | # Asumiendo que AVP22HD es un code de Service
| OD044  | AVP        | REEL BASICO (MAX 60S)                                                         |           1 | disable    | nan             | N            | nan           |
| OD045  | AVP        | MINUTO DE EDICIÓN | POSTPRODUCCIÓN DE VIDEO | PRO | VFX + SOUND + MULTI LAYER |           1 | disable    | nan             | N            | nan           |
| OD046  | DSGN       | LOGO SIGNATURE                                                                |           1 | disable    | nan             | N            | nan           |
| OD047  | BRND       | BRAND+                                                                        |           1 | enable     | nan             | Y            | nan           |
| OD048  | DEV        | DIGITAL STARTER WEB BASIC .CL                                                 |           1 | enable     | nan             | Y            | nan           |
| OD049  | DEV        | DIGITAL STARTER WEB BASIC .COM                                                |           1 | enable     | nan             | Y            | nan           |
| OD050  | BRND       | IMPULSO DIGITAL                                                               |           1 | enable     | nan             | Y            | nan           |
| OD051  | DSGN       | ESSENTIALS PRO                                                                |           1 | enable     | nan             | Y            | nan           |
| OD052  | DSGN       | FLYER DIGITAL                                                                 |           1 | disable    | nan             | N            | nan           |
| OD053  | AVP        | FLYER MOTION  MAX25SEG                                                        |           1 | disable    | nan             | N            | nan           |
| OD054  | DSGN       | FLYER 10X14 FULL COLOR DOS CARAS( PAQ 1000)                                   |           1 | disable    | DSXM25          | N            | nan           |
| OD055  | DSGN       | FLYER 10X14 FULL COLOR DOS CARAS( PAQ 500)                                    |           1 | disable    | DSXM25          | N            | nan           |
"""

serv_code_data_md = """
| nombre                                | code   |
|---------------------------------------|--------|
| MARKETING                             | MKT    |
| DEVELOPMENT                           | DEV    |
| DESIGN                                | DSGN   |
| SOCIAL MEDIA                          | SMM    |
| BRANDING                              | BRND   |
| AUDIOVISUAL PRODUCTION SERVICES (APS) | AVP    |
| IMPRENTA                              | PRNT   |
"""

prices_data_md = """
| dloub_id   |   USD |     CLP |   COP |
|------------|-------|---------|-------|
| OD027      |    60 |   58990 |     0 |
| OD028      |   140 |  136990 |     0 |
| OD029      |   230 |  218990 |     0 |
| OD030      |   500 |  475990 |     0 |
| OD031      |  1200 | 1199990 |     0 |
| OD004      |   160 |  151990 |     0 |
| OD005      |   150 |  141990 |     0 |
| OD006      |   100 |   94990 |     0 |
| OD007      |  3000 | 2849990 |     0 |
| OD008      |   300 |  284990 |     0 |
| OD009      |  1200 | 1139990 |     0 |
| OD012      |    80 |   75990 |     0 |
| OD032      |  1200 | 1139990 |     0 |
| OD033      |  1800 | 1709990 |     0 |
| OD023      |    35 |   32990 |     0 |
| OD015      |   160 |  151990 |     0 |
| OD016      |   230 |  217990 |     0 |
| OD046      |  2290 | 2199990 |     0 |
| OD047      |   120 |  114990 |     0 |
| OD048      |   145 |  137990 |     0 |
| OD049      |   125 |  118990 |     0 |
| OD050      |   140 |  134990 |     0 |
| OD051      |   210 |  199990 |     0 |
| OD052      |    15 |   14990 |     0 |
| OD053      |    35 |   34990 |     0 |
| OD054      |    75 |   69990 |     0 |
| OD055      |    45 |   45990 |     0 |
"""

services_features_data_md = """ 

| serviceid   | featuretype     | description                                                                                                                                                                                                                                  |
|-------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| OD027       | differentiator  | Servicio personalizado según las necesidades de la pequeña empresa.                                                                                                                                                                          |
| OD027       | differentiator  | Uso de herramientas básicas pero efectivas para maximizar resultados.                                                                                                                                                                        |
| OD028       | differentiator  | Estrategias más complejas y adaptadas a la evolución de la marca.                                                                                                                                                                            |
| OD028       | differentiator  | Enfoque en el crecimiento y la optimización constante.                                                                                                                                                                                       |
| OD028       | differentiator  | Reportes más frecuentes y detallados.                                                                                                                                                                                                        |
| OD029       | differentiator  | Estrategias de contenido altamente personalizadas.                                                                                                                                                                                           |
| OD029       | differentiator  | Monitoreo y optimización constante.                                                                                                                                                                                                          |
| OD029       | differentiator  | Reportes detallados con recomendaciones accionables.                                                                                                                                                                                         |
| OD030       | differentiator  | Enfoque en estrategias escalables y de alto impacto.                                                                                                                                                                                         |
| OD030       | differentiator  | Monitoreo constante y ajuste dinámico de la estrategia.                                                                                                                                                                                      |
| OD030       | differentiator  | Integración con otras áreas de marketing digital para maximizar resultados.                                                                                                                                                                  |
| OD031       | differentiator  | Enfoque en la innovación y la creatividad.                                                                                                                                                                                                   |
| OD031       | differentiator  | Uso de tecnologías avanzadas y tendencias emergentes.                                                                                                                                                                                        |
| OD031       | differentiator  | Adaptación rápida y flexible a cambios en el mercado.                                                                                                                                                                                        |
| OD004       | differentiator  | Diseño personalizado según la identidad de la marca.                                                                                                                                                                                         |
| OD004       | differentiator  | Optimización para SEO que mejora la visibilidad online.                                                                                                                                                                                      |
| OD004       | differentiator  | Interfaz amigable y fácil de actualizar.                                                                                                                                                                                                     |
| OD005       | differentiator  | Diseño personalizado que refleja la identidad de la marca.                                                                                                                                                                                   |
| OD005       | differentiator  | Enfoque en la optimización para la conversión.                                                                                                                                                                                               |
| OD005       | differentiator  | Integración con herramientas avanzadas de análisis.                                                                                                                                                                                          |
| OD006       | differentiator  | Proceso ágil y enfoque en resultados rápidos.                                                                                                                                                                                                |
| OD006       | differentiator  | Diseño simple pero efectivo.                                                                                                                                                                                                                 |
| OD006       | differentiator  | Optimización para SEO y dispositivos móviles.                                                                                                                                                                                                |
| OD007       | differentiator  | Enfoque en la simplicidad y la funcionalidad.                                                                                                                                                                                                |
| OD007       | differentiator  | Costo accesible para pequeños empresarios.                                                                                                                                                                                                   |
| OD007       | differentiator  | Posibilidad de escalar la tienda a medida que crece el negocio.                                                                                                                                                                              |
| OD008       | differentiator  | Interfaz fácil de usar para usuarios sin conocimientos técnicos.                                                                                                                                                                             |
| OD008       | differentiator  | Capacitación y soporte continuo.                                                                                                                                                                                                             |
| OD008       | differentiator  | Flexibilidad para agregar nuevas funcionalidades según el crecimiento del negocio.                                                                                                                                                           |
| OD009       | differentiator  | Personalización completa según las necesidades empresariales.                                                                                                                                                                                |
| OD009       | differentiator  | Integración con sistemas existentes y futuras expansiones.                                                                                                                                                                                   |
| OD009       | differentiator  | Soporte técnico dedicado y mantenimiento continuo.                                                                                                                                                                                           |
| OD012       | differentiator  | Costo muy accesible.                                                                                                                                                                                                                         |
| OD012       | differentiator  | Diseño profesional y estandarizado.                                                                                                                                                                                                          |
| OD012       | differentiator  | Proceso de desarrollo rápido.                                                                                                                                                                                                                |
| OD023       | differentiator  | Diseño centrado en la simplicidad y funcionalidad.                                                                                                                                                                                           |
| OD023       | differentiator  | Flexibilidad para realizar cambios futuros sin incurrir en costos adicionales.                                                                                                                                                               |
| OD023       | differentiator  | Asesoría y soporte post-entrega para garantizar el uso correcto del logo.                                                                                                                                                                    |
| OD032       | differentiator  | Enfoque integral que abarca todos los aspectos de la identidad de marca.                                                                                                                                                                     |
| OD032       | differentiator  | Asesoría estratégica continua para asegurar la correcta implementación de la identidad.                                                                                                                                                      |
| OD032       | differentiator  | Entrega de herramientas y guías que permiten mantener la coherencia a largo plazo.                                                                                                                                                           |
| OD033       | differentiator  | Proceso colaborativo que garantiza que la identidad de marca refleje auténticamente los valores y objetivos de la empresa.                                                                                                                   |
| OD033       | differentiator  | Enfoque estratégico en la implementación para maximizar el impacto de la marca.                                                                                                                                                              |
| OD033       | differentiator  | Soporte continuo para ajustes y optimización a medida que la marca evoluciona.                                                                                                                                                               |
| OD023       | differentiator  | Diseño accesible y funcional para pequeñas empresas.                                                                                                                                                                                         |
| OD023       | differentiator  | Flexibilidad para ediciones futuras.                                                                                                                                                                                                         |
| OD023       | differentiator  | Asesoría básica incluida para un uso efectivo del logo.                                                                                                                                                                                      |
| OD015       | differentiator  | Diseño de variantes para diferentes aplicaciones.                                                                                                                                                                                            |
| OD015       | differentiator  | Entrega completa de archivos y soporte para implementación.                                                                                                                                                                                  |
| OD015       | differentiator  | Adaptación del logo para diversos medios y usos.                                                                                                                                                                                             |
| OD016       | differentiator  | Paquete completo que cubre todas las necesidades de diseño del logo.                                                                                                                                                                         |
| OD016       | differentiator  | Flexibilidad y adaptabilidad total para cualquier uso o plataforma.                                                                                                                                                                          |
| OD016       | differentiator  | Soporte completo para asegurar una implementación efectiva.                                                                                                                                                                                  |
| OD046       | differentiator  | Diseño exclusivo y altamente personalizado.                                                                                                                                                                                                  |
| OD046       | differentiator  | Enfoque en la creación de una identidad visual que realmente marque la diferencia.                                                                                                                                                           |
| OD046       | differentiator  | Proceso de diseño detallado y personalizado.                                                                                                                                                                                                 |
| OD047       | differentiator  | Enfoque personalizado con atención al detalle.                                                                                                                                                                                               |
| OD047       | differentiator  | Entrega de un paquete completo de branding, todo en uno.                                                                                                                                                                                     |
| OD048       | differentiator  | Solución rápida y económica para la presencia en línea.                                                                                                                                                                                      |
| OD048       | differentiator  | Todo incluido: hosting, dominio, y seguridad web.                                                                                                                                                                                            |
| OD049       | differentiator  | Paquete económico para una presencia digital internacional.                                                                                                                                                                                  |
| OD049       | differentiator  | Todo incluido con foco en la expansión global.                                                                                                                                                                                               |
| OD050       | differentiator  | Enfoque integral en branding y estrategia en redes sociales.                                                                                                                                                                                 |
| OD050       | differentiator  | Personalización y adaptabilidad según la marca y el mercado.                                                                                                                                                                                 |
| OD051       | differentiator  | Foco en la calidad y detalle en el diseño.                                                                                                                                                                                                   |
| OD051       | differentiator  | Paquete completo para renovación y fortalecimiento de la imagen de marca.                                                                                                                                                                    |
| OD027       | benefit         | Gestión básica de redes sociales para pequeñas empresas que desean comenzar a construir su presencia en línea de manera efectiva y asequible.                                                                                                |
| OD027       | benefit         | Publicaciones regulares que mantienen activa la presencia de la marca en redes sociales.                                                                                                                                                     |
| OD027       | benefit         | Gestión económica y eficiente de la comunidad.                                                                                                                                                                                               |
| OD028       | benefit         | Gestión avanzada de redes sociales para pequeñas empresas, con un enfoque en el crecimiento y la interacción significativa con la audiencia, con opciones para agregar servicios adicionales según las necesidades.                          |
| OD028       | benefit         | Estrategias personalizadas que alinean con los objetivos de negocio.                                                                                                                                                                         |
| OD028       | benefit         | Crecimiento continuo y sostenido en redes sociales.                                                                                                                                                                                          |
| OD029       | benefit         | Servicio de gestión de redes sociales diseñado para empresas que desean establecer una fuerte presencia online y aumentar la interacción con su audiencia, con la posibilidad de añadir servicios adicionales según necesidades específicas. |
| OD029       | benefit         | Aumento significativo en la participación y crecimiento de la comunidad.                                                                                                                                                                     |
| OD029       | benefit         | Optimización constante para mejorar el rendimiento de las campañas.                                                                                                                                                                          |
| OD030       | benefit         | Gestión integral de redes sociales para empresas que buscan maximizar su presencia online, alcanzar nuevos mercados y aumentar significativamente su base de seguidores y la interacción con su audiencia.                                   |
| OD030       | benefit         | Estrategias avanzadas para captar y retener audiencia.                                                                                                                                                                                       |
| OD030       | benefit         | Reportes y análisis detallados que guían la toma de decisiones.                                                                                                                                                                              |
| OD031       | benefit         | Servicio de gestión de redes sociales altamente personalizado y de vanguardia, diseñado para empresas que desean innovar y mantenerse a la vanguardia de las tendencias de marketing digital.                                                |
| OD031       | benefit         | Adaptación rápida a nuevas tendencias y tecnologías.                                                                                                                                                                                         |
| OD031       | benefit         | Maximización del impacto y la resonancia de la marca.                                                                                                                                                                                        |
| OD004       | benefit         | Creación de un catálogo digital online que permite a las empresas mostrar hasta 20 productos, con opciones de personalización y optimización para SEO.                                                                                       |
| OD004       | benefit         | Optimización para motores de búsqueda (SEO).                                                                                                                                                                                                 |
| OD004       | benefit         | Interfaz fácil de usar y personalizable.                                                                                                                                                                                                     |
| OD005       | benefit         | Diseño y desarrollo de una landing page optimizada para la conversión, enfocada en un solo producto o servicio.                                                                                                                              |
| OD005       | benefit         | Optimización para SEO y velocidad de carga.                                                                                                                                                                                                  |
| OD005       | benefit         | Integración con herramientas de análisis y seguimiento.                                                                                                                                                                                      |
| OD006       | benefit         | Landing page básica de una sola página diseñada para captar leads y destacar información clave de un producto o servicio.                                                                                                                    |
| OD006       | benefit         | Diseño centrado en la captación de leads.                                                                                                                                                                                                    |
| OD006       | benefit         | Optimización básica para SEO y dispositivos móviles.                                                                                                                                                                                         |
| OD007       | benefit         | Desarrollo de una tienda virtual básica, enfocada en la venta de productos físicos o digitales con características esenciales de comercio electrónico.                                                                                       |
| OD007       | benefit         | Interfaz amigable y fácil de gestionar.                                                                                                                                                                                                      |
| OD007       | benefit         | Integración con pasarelas de pago populares.                                                                                                                                                                                                 |
| OD008       | benefit         | Desarrollo de un sitio web autoadministrable, donde la empresa puede gestionar su contenido de manera independiente, ideal para empresas que requieren actualizaciones frecuentes.                                                           |
| OD008       | benefit         | Fácil de usar con una interfaz intuitiva.                                                                                                                                                                                                    |
| OD008       | benefit         | Soporte técnico para formación y resolución de dudas.                                                                                                                                                                                        |
| OD009       | benefit         | Desarrollo de un sitio web empresarial de alto nivel con características avanzadas y personalización completa, ideal para empresas que buscan una presencia digital robusta y profesional.                                                   |
| OD009       | benefit         | Funcionalidades avanzadas para empresas.                                                                                                                                                                                                     |
| OD009       | benefit         | Soporte continuo y mantenimiento a largo plazo.                                                                                                                                                                                              |
| OD012       | benefit         | Desarrollo de una página web básica utilizando una plantilla predefinida, ideal para pequeñas empresas o emprendedores que necesitan una presencia en línea asequible.                                                                       |
| OD012       | benefit         | Diseño profesional basado en plantillas.                                                                                                                                                                                                     |
| OD012       | benefit         | Fácil de mantener y actualizar.                                                                                                                                                                                                              |
| OD023       | benefit         | Desarrollo de un logo básico, con la opción de obtener versiones editables para que la empresa pueda hacer ajustes menores en el futuro sin necesidad de recurrir a un diseñador.                                                            |
| OD023       | benefit         | Flexibilidad para realizar ajustes y personalizaciones en el futuro.                                                                                                                                                                         |
| OD023       | benefit         | Ahorro en costos de diseño a largo plazo al poder editar el logo internamente.                                                                                                                                                               |
| OD032       | benefit         | Servicio integral de identidad de marca que combina elementos visuales, verbales y estratégicos para crear una identidad de marca cohesiva y poderosa.                                                                                       |
| OD032       | benefit         | Alineación de todos los elementos de la marca, desde el logo hasta el tono de voz, con los objetivos estratégicos de la empresa.                                                                                                             |
| OD032       | benefit         | Incremento en el reconocimiento y la percepción positiva de la marca.                                                                                                                                                                        |
| OD033       | benefit         | Solución de branding de alta gama que incluye el desarrollo completo de la identidad de marca y su implementación estratégica, diseñada para empresas que buscan posicionarse como líderes en su industria.                                  |
| OD033       | benefit         | Implementación estratégica de la identidad en todos los puntos de contacto, asegurando coherencia y impacto.                                                                                                                                 |
| OD033       | benefit         | Fortalecimiento del posicionamiento de la marca como líder en su industria.                                                                                                                                                                  |
| OD023       | benefit         | Ideal para pequeñas empresas o startups que necesitan un logo funcional y de calidad, con elementos básicos que permiten un uso versátil.                                                                                                    |
| OD023       | benefit         | Acceso a archivos editables para facilitar futuras modificaciones.                                                                                                                                                                           |
| OD023       | benefit         | Costo accesible para startups y negocios en crecimiento.                                                                                                                                                                                     |
| OD015       | benefit         | Un paquete de diseño de logo avanzado que incluye más variantes y elementos adicionales para adaptar el logo a diferentes usos y plataformas.                                                                                                |
| OD015       | benefit         | Variantes del logo para diferentes aplicaciones, como redes sociales, impresión y web.                                                                                                                                                       |
| OD015       | benefit         | Archivos adicionales y soporte para implementar el logo en distintas situaciones.                                                                                                                                                            |
| OD016       | benefit         | El paquete completo de diseño de logo que incluye el diseño principal y todas las variantes necesarias para asegurar la máxima flexibilidad y aplicabilidad en cualquier contexto.                                                           |
| OD016       | benefit         | Incluye todas las variantes necesarias para aplicaciones específicas.                                                                                                                                                                        |
| OD016       | benefit         | Acceso a todos los archivos y formatos necesarios para la implementación.                                                                                                                                                                    |
| OD046       | benefit         | Un servicio premium que ofrece un diseño de logo exclusivo y personalizado, con una identidad de marca única y distintiva que marca la diferencia en el mercado.                                                                             |
| OD046       | benefit         | Identidad visual que se diferencia claramente de la competencia.                                                                                                                                                                             |
| OD046       | benefit         | Proceso de diseño personalizado que asegura una representación auténtica de la marca.                                                                                                                                                        |
| OD047       | benefit         | Establece una imagen de marca profesional y consistente.                                                                                                                                                                                     |
| OD047       | benefit         | Aumenta el reconocimiento y la credibilidad de la marca.                                                                                                                                                                                     |
| OD048       | benefit         | Establecimiento de una presencia digital profesional con una inversión mínima.                                                                                                                                                               |
| OD048       | benefit         | Seguridad y credibilidad mejoradas gracias al certificado SSL.                                                                                                                                                                               |
| OD049       | benefit         | Dominio .COM, reconocido a nivel mundial.                                                                                                                                                                                                    |
| OD049       | benefit         | Seguridad y profesionalismo mejorados.                                                                                                                                                                                                       |
| OD050       | benefit         | Mejora de la presencia y reputación en redes sociales.                                                                                                                                                                                       |
| OD050       | benefit         | Estrategia de contenido optimizada para mayor alcance y engagement.                                                                                                                                                                          |
| OD051       | benefit         | Mejora de la identidad visual y presentación de la marca.                                                                                                                                                                                    |
| OD051       | benefit         | Material promocional cohesivo y de alta calidad.                                                                                                                                                                                             |
| OD023       | caracteristicas | Diseño de un logo básico, ideal para empresas que inician su trayectoria.                                                                                                                                                                    |
| OD023       | caracteristicas | Entrega del logo en formatos editables (como .AI o .PSD), permitiendo modificaciones internas.                                                                                                                                               |
| OD023       | caracteristicas | Instrucciones de uso incluidas para garantizar que las ediciones mantengan la coherencia visual.                                                                                                                                             |
| OD032       | caracteristicas | Desarrollo de un sistema de identidad visual completo, incluyendo logo, paleta de colores, tipografía, y más.                                                                                                                                |
| OD032       | caracteristicas | Creación de guías de estilo para el uso correcto de la identidad en todos los medios y puntos de contacto.                                                                                                                                   |
| OD032       | caracteristicas | Definición de la estrategia de comunicación, incluyendo tono de voz y mensajes clave.                                                                                                                                                        |
| OD033       | caracteristicas | Investigación exhaustiva del mercado, la competencia y la audiencia objetivo.                                                                                                                                                                |
| OD033       | caracteristicas | Desarrollo de un sistema de identidad visual y verbal que incluye todos los aspectos de la marca.                                                                                                                                            |
| OD033       | caracteristicas | Creación de una estrategia de implementación detallada que garantiza el éxito en la comunicación de la identidad.                                                                                                                            |
| OD023       | caracteristicas | Diseño de un logo básico con elementos clave para representar la marca.                                                                                                                                                                      |
| OD023       | caracteristicas | Entrega en formatos editables para facilitar cambios futuros.                                                                                                                                                                                |
| OD023       | caracteristicas | Asesoría básica para el uso efectivo del logo.                                                                                                                                                                                               |
| OD015       | caracteristicas | Diseño de varias versiones del logo para adaptarse a diferentes formatos y aplicaciones.                                                                                                                                                     |
| OD015       | caracteristicas | Entrega de todos los archivos necesarios para implementar el logo en distintos medios.                                                                                                                                                       |
| OD015       | caracteristicas | Asesoría sobre el uso y aplicación del logo en diferentes contextos.                                                                                                                                                                         |
| OD016       | caracteristicas | Diseño del logo principal junto con todas las variantes necesarias para diferentes aplicaciones.                                                                                                                                             |
| OD016       | caracteristicas | Entrega de todos los archivos y formatos, incluyendo versiones para web, impresión y redes sociales.                                                                                                                                         |
| OD016       | caracteristicas | Asesoría sobre cómo utilizar y adaptar el logo para distintas plataformas y necesidades.                                                                                                                                                     |
| OD046       | caracteristicas | Diseño completamente personalizado y exclusivo para la marca.                                                                                                                                                                                |
| OD046       | caracteristicas | Proceso de desarrollo detallado, incluyendo investigaciones y pruebas para garantizar la eficacia del diseño.                                                                                                                                |
| OD046       | caracteristicas | Entrega de un paquete completo con todos los archivos y formatos necesarios.                                                                                                                                                                 |
| OD047       | caracteristicas | Diseño personalizado de logotipo y material de marketing.                                                                                                                                                                                    |
| OD047       | caracteristicas | Plantillas adaptables para redes sociales.                                                                                                                                                                                                   |
| OD047       | caracteristicas | Elementos visuales integrados que refuerzan la identidad de la marca.                                                                                                                                                                        |
| OD048       | caracteristicas | Landing page personalizada.                                                                                                                                                                                                                  |
| OD048       | caracteristicas | Correo corporativo para una comunicación más profesional.                                                                                                                                                                                    |
| OD048       | caracteristicas | Hosting y dominio asegurados por un año.                                                                                                                                                                                                     |
| OD049       | caracteristicas | Diseño y desarrollo de landing page.                                                                                                                                                                                                         |
| OD049       | caracteristicas | Correo corporativo.                                                                                                                                                                                                                          |
| OD049       | caracteristicas | Hosting y dominio .COM por un año.                                                                                                                                                                                                           |
| OD049       | caracteristicas | Certificado SSL para seguridad.                                                                                                                                                                                                              |
| OD050       | caracteristicas | Configuración profesional de Meta Business y perfiles en redes sociales.                                                                                                                                                                     |
| OD050       | caracteristicas | Análisis y optimización de contenido clave.                                                                                                                                                                                                  |
| OD050       | caracteristicas | Diseño personalizado para branding en redes sociales.                                                                                                                                                                                        |
| OD051       | caracteristicas | Rebranding de logotipo y diseño de catálogo digital.                                                                                                                                                                                         |
| OD051       | caracteristicas | Flyers y fichas técnicas personalizadas.                                                                                                                                                                                                     |
| OD051       | caracteristicas | Integración de QR para facilitar la interacción digital.                                                                                                                                                                                     |
| OD027       | process         | Definición de objetivos y público objetivo.                                                                                                                                                                                                  |
| OD027       | process         | Creación de un calendario de contenidos básico.                                                                                                                                                                                              |
| OD027       | process         | Publicación y monitoreo diario de las redes.                                                                                                                                                                                                 |
| OD027       | process         | Revisión mensual de resultados y ajustes.                                                                                                                                                                                                    |
| OD028       | process         | Análisis de la situación actual y establecimiento de objetivos.                                                                                                                                                                              |
| OD028       | process         | Desarrollo de estrategias de contenido y de crecimiento.                                                                                                                                                                                     |
| OD028       | process         | Publicación, monitoreo y ajuste en tiempo real.                                                                                                                                                                                              |
| OD028       | process         | Reportes y reuniones quincenales para optimización.                                                                                                                                                                                          |
| OD029       | process         | Auditoría inicial de redes sociales y definición de objetivos.                                                                                                                                                                               |
| OD029       | process         | Creación de un plan de contenidos personalizado.                                                                                                                                                                                             |
| OD029       | process         | Implementación, monitoreo y ajuste de estrategias.                                                                                                                                                                                           |
| OD029       | process         | Análisis mensual de resultados y recomendaciones.                                                                                                                                                                                            |
| OD030       | process         | Evaluación exhaustiva y definición de metas a corto y largo plazo.                                                                                                                                                                           |
| OD030       | process         | Desarrollo de una estrategia de contenido avanzada y dinámica.                                                                                                                                                                               |
| OD030       | process         | Gestión diaria con ajustes en tiempo real.                                                                                                                                                                                                   |
| OD030       | process         | Análisis quincenal y optimización de estrategias.                                                                                                                                                                                            |
| OD031       | process         | Análisis de tendencias y benchmarking competitivo.                                                                                                                                                                                           |
| OD031       | process         | Desarrollo de estrategias innovadoras y creativas.                                                                                                                                                                                           |
| OD031       | process         | Implementación con pruebas y ajustes continuos.                                                                                                                                                                                              |
| OD031       | process         | Revisión trimestral de resultados y ajuste estratégico.                                                                                                                                                                                      |
| OD004       | process         | Reunión inicial para definir la estructura del catálogo.                                                                                                                                                                                     |
| OD004       | process         | Diseño y personalización de plantillas.                                                                                                                                                                                                      |
| OD004       | process         | Subida y optimización de productos.                                                                                                                                                                                                          |
| OD004       | process         | Revisión y ajustes finales antes del lanzamiento.                                                                                                                                                                                            |
| OD005       | process         | Reunión para definir objetivos y enfoque de la landing page.                                                                                                                                                                                 |
| OD005       | process         | Diseño y desarrollo basado en principios de UX/UI.                                                                                                                                                                                           |
| OD005       | process         | Optimización de la página para velocidad y SEO.                                                                                                                                                                                              |
| OD005       | process         | Pruebas y ajustes antes del lanzamiento.                                                                                                                                                                                                     |
| OD006       | process         | Reunión para entender los objetivos y el mensaje clave.                                                                                                                                                                                      |
| OD006       | process         | Diseño y desarrollo de la landing page.                                                                                                                                                                                                      |
| OD006       | process         | Optimización para SEO y pruebas de usabilidad.                                                                                                                                                                                               |
| OD006       | process         | Lanzamiento y análisis de rendimiento.                                                                                                                                                                                                       |
| OD007       | process         | Reunión inicial para definir los productos y las características esenciales.                                                                                                                                                                 |
| OD007       | process         | Desarrollo y personalización de la tienda virtual.                                                                                                                                                                                           |
| OD007       | process         | Integración con sistemas de pago y logística.                                                                                                                                                                                                |
| OD007       | process         | Pruebas y lanzamiento.                                                                                                                                                                                                                       |
| OD008       | process         | Reunión para definir las necesidades y funcionalidades del sitio.                                                                                                                                                                            |
| OD008       | process         | Desarrollo y personalización del sitio web.                                                                                                                                                                                                  |
| OD008       | process         | Formación en la gestión del sitio para el equipo de la empresa.                                                                                                                                                                              |
| OD008       | process         | Soporte post-lanzamiento para asegurar una transición suave.                                                                                                                                                                                 |
| OD009       | process         | Análisis detallado de las necesidades de la empresa.                                                                                                                                                                                         |
| OD009       | process         | Diseño y desarrollo personalizado.                                                                                                                                                                                                           |
| OD009       | process         | Integración con sistemas empresariales existentes.                                                                                                                                                                                           |
| OD009       | process         | Pruebas exhaustivas y optimización para el lanzamiento.                                                                                                                                                                                      |
| OD012       | process         | Selección de una plantilla predefinida.                                                                                                                                                                                                      |
| OD012       | process         | Personalización básica según la identidad de la marca.                                                                                                                                                                                       |
| OD012       | process         | Carga de contenido y optimización para SEO.                                                                                                                                                                                                  |
| OD012       | process         | Lanzamiento rápido y sencillo.                                                                                                                                                                                                               |
| OD023       | process         | Briefing Inicial: Recopilación de información sobre la marca y sus necesidades.                                                                                                                                                              |
| OD023       | process         | Diseño del Logo Básico: Creación de un logo que refleje la esencia de la marca.                                                                                                                                                              |
| OD023       | process         | Entrega de Archivos: Suministro de archivos editables y guía de uso.                                                                                                                                                                         |
| OD023       | process         | Capacitación Opcional: Orientación sobre cómo realizar ediciones sin comprometer la calidad del logo.                                                                                                                                        |
| OD032       | process         | Consultoría Estratégica: Sesiones para entender la visión, misión y objetivos de la empresa.                                                                                                                                                 |
| OD032       | process         | Desarrollo de la Identidad Visual: Creación de todos los elementos gráficos que representarán a la marca.                                                                                                                                    |
| OD032       | process         | Definición de la Estrategia de Comunicación: Establecimiento del tono y estilo de comunicación de la marca.                                                                                                                                  |
| OD032       | process         | Entrega de Guías de Uso: Documentos detallados que aseguran la coherencia en la implementación de la identidad.                                                                                                                              |
| OD033       | process         | Análisis y Estrategia: Estudio profundo del mercado y la marca para definir una estrategia de branding efectiva.                                                                                                                             |
| OD033       | process         | Desarrollo Integral de la Identidad: Creación de todos los elementos visuales, verbales y estratégicos de la marca.                                                                                                                          |
| OD033       | process         | Implementación Estratégica: Aplicación de la identidad en todos los medios, asegurando coherencia y eficacia.                                                                                                                                |
| OD033       | process         | Monitoreo y Optimización: Seguimiento continuo para ajustar y mejorar la implementación según los resultados.                                                                                                                                |
| OD023       | process         | Recolección de Información: Entrevista para entender la visión de la marca.                                                                                                                                                                  |
| OD023       | process         | Diseño Inicial: Creación de un logo básico basado en la información proporcionada.                                                                                                                                                           |
| OD023       | process         | Entrega de Archivos: Provisión de archivos editables y guía de uso.                                                                                                                                                                          |
| OD023       | process         | Revisión Final: Ajustes menores según el feedback del cliente.                                                                                                                                                                               |
| OD015       | process         | Entrevista Inicial: Recopilación de información para entender las necesidades específicas del cliente.                                                                                                                                       |
| OD015       | process         | Diseño y Variantes: Creación de un logo principal y sus variantes para diferentes usos.                                                                                                                                                      |
| OD015       | process         | Entrega y Soporte: Provisión de todos los archivos necesarios y soporte para la implementación.                                                                                                                                              |
| OD016       | process         | Consulta Inicial: Reunión para definir las necesidades específicas del cliente.                                                                                                                                                              |
| OD016       | process         | Diseño Integral: Creación del logo principal y sus variantes.                                                                                                                                                                                |
| OD016       | process         | Entrega Completa: Suministro de todos los archivos necesarios y asesoría para su uso.                                                                                                                                                        |
| OD046       | process         | Consulta Exclusiva: Entrevista profunda para entender los valores y objetivos de la marca.                                                                                                                                                   |
| OD046       | process         | Diseño Personalizado: Creación de un logo único basado en la identidad de la marca.                                                                                                                                                          |
| OD046       | process         | Entrega Completa: Provisión de todos los archivos necesarios y guía para el uso del logo.                                                                                                                                                    |
| OD047       | process         | Análisis de la marca y el mercado.                                                                                                                                                                                                           |
| OD047       | process         | Diseño de logotipo y materiales gráficos.                                                                                                                                                                                                    |
| OD047       | process         | Revisión y ajustes según retroalimentación del cliente.                                                                                                                                                                                      |
| OD047       | process         | Entrega de los archivos finales en diferentes formatos.                                                                                                                                                                                      |
| OD047       | process         | Resultados Esperados: Una identidad visual cohesiva que aumente el reconocimiento de la marca y facilite su promoción en diversas plataformas.                                                                                               |
| OD048       | process         | Recopilación de requerimientos del cliente.                                                                                                                                                                                                  |
| OD048       | process         | Configuración del dominio y hosting.                                                                                                                                                                                                         |
| OD048       | process         | Diseño y desarrollo de la landing page.                                                                                                                                                                                                      |
| OD048       | process         | Configuración del correo corporativo y certificado SSL.                                                                                                                                                                                      |
| OD048       | process         | Revisión final y lanzamiento.                                                                                                                                                                                                                |
| OD049       | process         | Recopilación de requerimientos del cliente.                                                                                                                                                                                                  |
| OD049       | process         | Configuración del dominio y hosting.                                                                                                                                                                                                         |
| OD049       | process         | Diseño y desarrollo de la landing page.                                                                                                                                                                                                      |
| OD049       | process         | Configuración del correo corporativo y certificado SSL.                                                                                                                                                                                      |
| OD049       | process         | Revisión final y lanzamiento.                                                                                                                                                                                                                |
| OD050       | process         | Evaluación de la presencia actual en redes sociales.                                                                                                                                                                                         |
| OD050       | process         | Configuración y optimización de perfiles.                                                                                                                                                                                                    |
| OD050       | process         | Creación y diseño de contenido.                                                                                                                                                                                                              |
| OD050       | process         | Implementación y seguimiento de la estrategia.                                                                                                                                                                                               |
| OD051       | process         | Análisis de la marca y sus necesidades visuales.                                                                                                                                                                                             |
| OD051       | process         | Diseño y desarrollo de logotipos y materiales promocionales.                                                                                                                                                                                 |
| OD051       | process         | Implementación de elementos interactivos como QR.                                                                                                                                                                                            |
| OD051       | process         | Revisión y entrega de materiales.                                                                                                                                                                                                            |
| OD027       | result          | Aumento en la cantidad de seguidores y en la interacción con la audiencia.                                                                                                                                                                   |
| OD027       | result          | Presencia digital establecida y activa en redes sociales.                                                                                                                                                                                    |
| OD027       | result          | Base sólida para futuras estrategias de marketing digital.                                                                                                                                                                                   |
| OD028       | result          | Crecimiento más rápido y sostenido en redes sociales.                                                                                                                                                                                        |
| OD028       | result          | Aumento en las interacciones y en la lealtad de la comunidad.                                                                                                                                                                                |
| OD028       | result          | Mejor alineación de la estrategia de redes sociales con los objetivos del negocio.                                                                                                                                                           |
| OD029       | result          | Incremento en seguidores, interacciones y visibilidad de la marca.                                                                                                                                                                           |
| OD029       | result          | Establecimiento de una estrategia de contenido a largo plazo.                                                                                                                                                                                |
| OD029       | result          | Mejora continua en el rendimiento de las redes sociales.                                                                                                                                                                                     |
| OD030       | result          | Crecimiento exponencial en seguidores y engagement.                                                                                                                                                                                          |
| OD030       | result          | Expansión de la presencia de la marca en nuevas plataformas.                                                                                                                                                                                 |
| OD030       | result          | Mejora significativa en la conversión de leads a clientes.                                                                                                                                                                                   |
| OD031       | result          | Liderazgo en la industria a través de la innovación en redes sociales.                                                                                                                                                                       |
| OD031       | result          | Mayor resonancia y conexión emocional con la audiencia.                                                                                                                                                                                      |
| OD031       | result          | Crecimiento sostenido y relevante en seguidores e interacción.                                                                                                                                                                               |
| OD004       | result          | Catálogo digital atractivo y funcional.                                                                                                                                                                                                      |
| OD004       | result          | Mayor visibilidad de los productos en línea.                                                                                                                                                                                                 |
| OD004       | result          | Mejora en la conversión de visitantes a clientes.                                                                                                                                                                                            |
| OD005       | result          | Aumento significativo en la tasa de conversión.                                                                                                                                                                                              |
| OD005       | result          | Mayor visibilidad y tráfico hacia el producto o servicio destacado.                                                                                                                                                                          |
| OD005       | result          | Mejora en la retención de visitantes y en la generación de leads.                                                                                                                                                                            |
| OD006       | result          | Captación efectiva de leads.                                                                                                                                                                                                                 |
| OD006       | result          | Mayor visibilidad online con una inversión mínima.                                                                                                                                                                                           |
| OD006       | result          | Facilidad para actualizar y mantener la página.                                                                                                                                                                                              |
| OD007       | result          | Tienda virtual operativa y lista para vender.                                                                                                                                                                                                |
| OD007       | result          | Facilidad de gestión de productos y pedidos.                                                                                                                                                                                                 |
| OD007       | result          | Incremento en las ventas y la visibilidad online.                                                                                                                                                                                            |
| OD008       | result          | Control total sobre el contenido y actualizaciones del sitio.                                                                                                                                                                                |
| OD008       | result          | Ahorro en costos de mantenimiento a largo plazo.                                                                                                                                                                                             |
| OD008       | result          | Mayor agilidad en la gestión del sitio web.                                                                                                                                                                                                  |
| OD009       | result          | Presencia digital fuerte y profesional.                                                                                                                                                                                                      |
| OD009       | result          | Sitio web que soporta y mejora las operaciones empresariales.                                                                                                                                                                                |
| OD009       | result          | Aumento en la confianza y percepción de la marca.                                                                                                                                                                                            |
| OD012       | result          | Sitio web funcional y listo para usar.                                                                                                                                                                                                       |
| OD012       | result          | Mayor visibilidad online con una inversión mínima.                                                                                                                                                                                           |
| OD012       | result          | Facilidad para actualizar y mantener el sitio.                                                                                                                                                                                               |
| OD023       | result          | Un logo que sirve como base sólida para la identidad visual de la marca.                                                                                                                                                                     |
| OD023       | result          | Capacidad de la empresa para mantener la coherencia visual sin depender completamente de servicios externos.                                                                                                                                 |
| OD023       | result          | Mayor control sobre la identidad de marca.                                                                                                                                                                                                   |
| OD032       | result          | Identidad de marca robusta que comunica claramente los valores y promesas de la empresa.                                                                                                                                                     |
| OD032       | result          | Consistencia en la presentación de la marca en todos los medios y plataformas.                                                                                                                                                               |
| OD032       | result          | Aumento en la fidelidad de los clientes y reconocimiento de la marca en el mercado.                                                                                                                                                          |
| OD033       | result          | Una identidad de marca que eleva el perfil de la empresa y la posiciona como líder en su industria.                                                                                                                                          |
| OD033       | result          | Consistencia en la presentación de la marca que refuerza la confianza y lealtad de los clientes.                                                                                                                                             |
| OD033       | result          | Mayor reconocimiento y preferencia de marca en un mercado competitivo.                                                                                                                                                                       |
| OD023       | result          | Un logo funcional y versátil para representar a la empresa.                                                                                                                                                                                  |
| OD023       | result          | Capacidad de realizar modificaciones internas sin depender de un diseñador.                                                                                                                                                                  |
| OD023       | result          | Establecimiento de una presencia visual sólida a un costo razonable.                                                                                                                                                                         |
| OD015       | result          | Un logo versátil que se adapta a diferentes aplicaciones y plataformas.                                                                                                                                                                      |
| OD015       | result          | Capacidad de implementar el logo en una variedad de contextos sin pérdida de calidad.                                                                                                                                                        |
| OD015       | result          | Soporte adicional para garantizar el uso efectivo del logo en todas las situaciones.                                                                                                                                                         |
| OD016       | result          | Un logo que se adapta completamente a todas las necesidades y plataformas.                                                                                                                                                                   |
| OD016       | result          | Consistencia en la identidad de marca a través de todas las aplicaciones.                                                                                                                                                                    |
| OD016       | result          | Soporte para garantizar que el logo se utilice de manera efectiva en todos los contextos.                                                                                                                                                    |
| OD046       | result          | Una identidad de marca distintiva que destaca en el mercado.                                                                                                                                                                                 |
| OD046       | result          | Logo exclusivo que refleja los valores y la visión de la marca.                                                                                                                                                                              |
| OD046       | result          | Impacto significativo y positivo en la percepción de la marca.                                                                                                                                                                               |
| OD047       | result          | Una identidad visual cohesiva que aumente el reconocimiento de la marca y facilite su promoción en diversas plataformas.                                                                                                                     |
| OD048       | result          | Presencia en línea funcional y segura que mejore la visibilidad y profesionalismo del negocio.                                                                                                                                               |
| OD049       | result          | Presencia en línea con dominio .COM que aumenta la credibilidad y alcance global del negocio.                                                                                                                                                |
| OD050       | result          | Aumento del engagement y visibilidad en redes sociales, con una identidad de marca más fuerte y coherente.                                                                                                                                   |
| OD051       | result          | Materiales de marketing de alta calidad que refuercen la presencia de la marca y aumenten su atractivo visual.                                                                                                                               |


"""
service_details_data_md = """
| code   | audience                                                                                                                                               | description                                                                                                                                                                                                                                                   | resuelve                                                                                                                                                                                                                        |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| OD004  | Pequeñas y medianas empresas que desean presentar su oferta de productos en un formato digital atractivo y funcional.                                  | Creación de un catálogo digital online que permite a las empresas mostrar hasta 20 productos, con opciones de personalización y optimización para SEO.                                                                                                        | Falta de una plataforma digital eficiente para mostrar productos de manera atractiva y fácil de navegar.                                                                                                                        |
| OD005  | Empresas que desean destacar un producto o servicio específico y maximizar las conversiones a través de una página de aterrizaje altamente optimizada. | Diseño y desarrollo de una landing page optimizada para la conversión, enfocada en un solo producto o servicio.                                                                                                                                               | Necesidad de una página de aterrizaje efectiva que impulse las conversiones para un producto o servicio clave.                                                                                                                  |
| OD006  | Empresas que buscan una solución rápida y económica para captar leads a través de una landing page sencilla.                                           | Landing page básica de una sola página diseñada para captar leads y destacar información clave de un producto o servicio.                                                                                                                                     | Necesidad de una presencia digital rápida y efectiva para captar leads sin necesidad de un sitio web completo.                                                                                                                  |
| OD007  | Empresas pequeñas y medianas que desean iniciar su presencia en el comercio electrónico sin una inversión significativa.                               | Desarrollo de una tienda virtual básica, enfocada en la venta de productos físicos o digitales con características esenciales de comercio electrónico.                                                                                                        | Necesidad de una plataforma de comercio electrónico funcional y económica para comenzar a vender en línea.                                                                                                                      |
| OD008  | Empresas que necesitan un sitio web que puedan actualizar regularmente sin depender de un desarrollador.                                               | Desarrollo de un sitio web autoadministrable, donde la empresa puede gestionar su contenido de manera independiente, ideal para empresas que requieren actualizaciones frecuentes.                                                                            | Falta de control sobre el contenido del sitio web y la necesidad de realizar actualizaciones rápidas y frecuentes.                                                                                                              |
| OD009  | Empresas medianas y grandes que necesitan un sitio web complejo y altamente personalizado para representar su marca en línea.                          | Desarrollo de un sitio web empresarial de alto nivel con características avanzadas y personalización completa, ideal para empresas que buscan una presencia digital robusta y profesional.                                                                    | Necesidad de un sitio web avanzado que refleje la identidad de la empresa y soporte funcionalidades empresariales complejas.                                                                                                    |
| OD012  | Emprendedores y pequeñas empresas que necesitan un sitio web funcional y económico.                                                                    | Desarrollo de una página web básica utilizando una plantilla predefinida, ideal para pequeñas empresas o emprendedores que necesitan una presencia en línea asequible.                                                                                        | Falta de una presencia digital básica para la empresa a un costo accesible.                                                                                                                                                     |
| OD015  | Empresas en crecimiento que necesitan un logo más versátil y personalizado para una amplia gama de aplicaciones.                                       | Un paquete de diseño de logo avanzado que incluye más variantes y elementos adicionales para adaptar el logo a diferentes usos y plataformas.                                                                                                                 | La necesidad de un logo que no solo sea efectivo, sino que también ofrezca flexibilidad para múltiples aplicaciones y adaptaciones.                                                                                             |
| OD016  | Empresas que requieren un logo altamente adaptable para diversas aplicaciones y plataformas, con un conjunto completo de variantes y archivos.         | El paquete completo de diseño de logo que incluye el diseño principal y todas las variantes necesarias para asegurar la máxima flexibilidad y aplicabilidad en cualquier contexto.                                                                            | La necesidad de un logo completamente adaptable a todas las aplicaciones y plataformas, asegurando una identidad de marca coherente y flexible.                                                                                 |
| OD023  | Startups, pequeños negocios y emprendedores que buscan un logo básico, accesible y editable.                                                           | Ideal para pequeñas empresas o startups que necesitan un logo funcional y de calidad, con elementos básicos que permiten un uso versátil.                                                                                                                     | La necesidad de un diseño de logo asequible y funcional que establezca una presencia visual sólida en el mercado.                                                                                                               |
| OD027  | Startups, pequeñas empresas, y negocios locales que buscan establecer su marca en redes sociales con un presupuesto limitado.                          | Gestión básica de redes sociales para pequeñas empresas que desean comenzar a construir su presencia en línea de manera efectiva y asequible.                                                                                                                 | Falta de visibilidad en redes sociales y necesidad de una gestión básica para comenzar a atraer a la audiencia objetivo.                                                                                                        |
| OD028  | Pequeñas y medianas empresas que buscan un crecimiento sostenido en redes sociales con estrategias más complejas y efectivas.                          | Gestión avanzada de redes sociales para pequeñas empresas, con un enfoque en el crecimiento y la interacción significativa con la audiencia, con opciones para agregar servicios adicionales según las necesidades.                                           | Necesidad de una estrategia más avanzada para aumentar el alcance y la participación en redes sociales.                                                                                                                         |
| OD029  | Pequeñas y medianas empresas que buscan un manejo más sólido y estratégico de sus redes sociales.                                                      | Servicio de gestión de redes sociales diseñado para empresas que desean establecer una fuerte presencia online y aumentar la interacción con su audiencia, con la posibilidad de añadir servicios adicionales según necesidades específicas.                  | Falta de una estrategia coherente y efectiva para atraer y retener a la audiencia en redes sociales.                                                                                                                            |
| OD030  | Empresas medianas y en crecimiento que desean escalar su estrategia de redes sociales para alcanzar un impacto más amplio.                             | Gestión integral de redes sociales para empresas que buscan maximizar su presencia online, alcanzar nuevos mercados y aumentar significativamente su base de seguidores y la interacción con su audiencia.                                                    | Necesidad de una estrategia de redes sociales más robusta y efectiva para escalar la marca y expandir su alcance.                                                                                                               |
| OD031  | Empresas en sectores altamente competitivos y disruptivos que buscan destacar y liderar en su mercado.                                                 | Servicio de gestión de redes sociales altamente personalizado y de vanguardia, diseñado para empresas que desean innovar y mantenerse a la vanguardia de las tendencias de marketing digital.                                                                 | Necesidad de innovación constante y estrategias disruptivas para mantener y ampliar la relevancia de la marca.                                                                                                                  |
| OD032  | Empresas medianas y grandes que buscan establecer o renovar su identidad de marca de manera integral y estratégica.                                    | Servicio integral de identidad de marca que combina elementos visuales, verbales y estratégicos para crear una identidad de marca cohesiva y poderosa.                                                                                                        | Necesidad de una identidad de marca coherente que alinee todos los elementos visuales y verbales con la estrategia de negocio, garantizando un impacto fuerte y duradero en el mercado.                                         |
| OD033  | Corporaciones y marcas establecidas que desean reforzar o redefinir su identidad para mantenerse competitivas y relevantes en un mercado exigente.     | Solución de branding de alta gama que incluye el desarrollo completo de la identidad de marca y su implementación estratégica, diseñada para empresas que buscan posicionarse como líderes en su industria.                                                   | La necesidad de una identidad de marca que no solo sea visualmente atractiva, sino que esté profundamente alineada con los objetivos estratégicos y de negocio, permitiendo a la empresa diferenciarse y destacar en su sector. |
| OD043  | nan                                                                                                                                                    | nan                                                                                                                                                                                                                                                           | nan                                                                                                                                                                                                                             |
| OD046  | Marcas de alto perfil que buscan una identidad visual única y diferenciada, con un enfoque en la exclusividad y el impacto.                            | Un servicio premium que ofrece un diseño de logo exclusivo y personalizado, con una identidad de marca única y distintiva que marca la diferencia en el mercado.                                                                                              | La necesidad de un logo altamente exclusivo y distintivo que permita a la marca destacarse significativamente en el mercado y crear una fuerte impresión en la audiencia.                                                       |
| OD047  | Pequeñas y medianas empresas, emprendedores, y negocios en etapa inicial que buscan establecer una presencia de marca fuerte y coherente.              | Un paquete completo para la construcción y fortalecimiento de la identidad visual de una marca. Incluye diseño de logotipo, perfiles de cliente, plantillas para historias en redes sociales, portada para WhatsApp, flyer digital y stickers personalizados. | Falta de una identidad visual clara y profesional que comunique efectivamente los valores de la marca y atraiga al público objetivo.                                                                                            |
| OD048  | Empresas y emprendedores en Chile que buscan establecer su presencia en línea de manera rápida y efectiva.                                             | Paquete de inicio digital que incluye la creación de una landing page básica, correo corporativo, hosting y dominio .CL por un año, y certificado SSL.                                                                                                        | La falta de presencia en línea, que limita la capacidad de las empresas para llegar a clientes potenciales y competir en el mercado digital.                                                                                    |
| OD049  | Empresas y emprendedores que buscan una presencia en línea más global.                                                                                 | Este servicio está orientado a empresas y emprendedores que buscan establecer una presencia en línea con un dominio .COM, que es más universal y reconocido.                                                                                                  | Necesidad de una presencia en línea profesional y creíble con un dominio .COM, ideal para mercados internacionales.                                                                                                             |
| OD050  | Empresas y emprendedores que desean fortalecer su presencia en redes sociales y mejorar su estrategia de contenido digital.                            | Un paquete integral para potenciar la presencia digital de marcas en redes sociales, incluye configuración de Meta Business, análisis de contenido, y diseño de branding social.                                                                              | Falta de coherencia y efectividad en la presencia y estrategia digital en redes sociales.                                                                                                                                       |
| OD051  | Empresas que buscan actualizar o reforzar su identidad visual con un enfoque profesional y moderno.                                                    | Paquete de diseño gráfico avanzado que incluye la creación o actualización de logotipos, catálogo digital, flyers, y material promocional adicional.                                                                                                          | La necesidad de materiales promocionales de alta calidad que comuniquen efectivamente la propuesta de valor de la marca.                                                                                                        |
| OD052  | nan                                                                                                                                                    | nan                                                                                                                                                                                                                                                           | nan                                                                                                                                                                                                                             |
| OD053  | nan                                                                                                                                                    | nan                                                                                                                                                                                                                                                           | nan                                                                                                                                                                                                                             |
| OD054  | nan                                                                                                                                                    | nan                                                                                                                                                                                                                                                           | nan                                                                                                                                                                                                                             |
| OD055  | nan                                                                                                                                                    | nan                                                                                                                                                                                                                                                           | nan                                                                                                                                                                                                                             |
"""

campaigns_data_md = """
| campaign_code   | campaign_name                         | start_date          | end_date            | description                                                                    |
|-----------------|---------------------------------------|---------------------|---------------------|--------------------------------------------------------------------------------|
| DSXM25          | Campaña Promoción de Lanzamiento 2024 | 2024-01-01 00:00:00 | 2024-01-30 00:00:00 | Promoción de lanzamiento con descuentos especiales para los primeros clientes. |
"""

# --- Función auxiliar para limpiar y convertir booleanos ---
def clean_bool(value, true_values=['1', 'enable', 'y'], false_values=['0', 'disable', 'n']):
    if isinstance(value, str):
        value = value.strip().lower()
        if value in true_values:
            return True
        if value in false_values:
            return False
    if isinstance(value, (int, float)) and not math.isnan(value):
        return bool(value)
    return False # Default a False si es nan o no reconocido

# --- Función auxiliar para limpiar y convertir Decimal ---
def clean_decimal(value, default=Decimal('0.00')):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    if isinstance(value, str):
         value = value.strip()
         if not value:
             return default
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return default

# --- Función auxiliar para limpiar strings y manejar 'nan' ---
def clean_string(value):
     if value is None or (isinstance(value, float) and math.isnan(value)) or (isinstance(value, str) and value.strip().lower() == 'nan'):
         return None
     return str(value).strip()


class Command(BaseCommand):
    help = 'Carga datos iniciales de servicios, categorías, precios y características desde datos definidos.'

    def parse_markdown_table(self, md_string):
        """Parsea una tabla Markdown simple a un DataFrame de Pandas."""
        # Usa StringIO para tratar el string como un archivo
        data_io = io.StringIO(md_string)
        # Lee saltando las primeras 2 líneas (título y separador) y la última fila si es vacía
        df = pd.read_csv(data_io, sep='|', skiprows=[0, 2], skipinitialspace=True)
        # Eliminar la primera y última columna que están vacías por los pipes
        df = df.iloc[:, 1:-1]
        # Limpiar nombres de columnas
        df.columns = [col.strip() for col in df.columns]
        # Eliminar filas que sean completamente NaN (podrían ser líneas vacías)
        df.dropna(how='all', inplace=True)
        return df

    @transaction.atomic # Envuelve toda la operación en una transacción
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando carga de datos de servicios..."))

        # --- 1. Cargar Categorías de Servicio (serv_code) ---
        self.stdout.write("Cargando Categorías de Servicio...")
        df_cat = self.parse_markdown_table(serv_code_data_md)
        created_count = 0
        updated_count = 0
        for index, row in df_cat.iterrows():
            code = clean_string(row.get('code'))
            name = clean_string(row.get('nombre'))
            if not code or not name:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Saltando categoría inválida (código o nombre vacío)."))
                continue

            category, created = ServiceCategory.objects.update_or_create(
                code=code,
                defaults={'name': name}
            )
            if created: created_count += 1
            else: updated_count += 1
        self.stdout.write(self.style.SUCCESS(f"  Categorías creadas: {created_count}, actualizadas: {updated_count}."))

        # --- 2. Cargar Campañas (campaigns) ---
        self.stdout.write("Cargando Campañas...")
        df_camp = self.parse_markdown_table(campaigns_data_md)
        created_count = 0
        updated_count = 0
        for index, row in df_camp.iterrows():
            code = clean_string(row.get('campaign_code'))
            name = clean_string(row.get('campaign_name'))
            if not code or not name:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Saltando campaña inválida."))
                continue

            try:
                start_date = make_aware(datetime.strptime(clean_string(row.get('start_date')), '%Y-%m-%d %H:%M:%S'))
            except (ValueError, TypeError):
                 self.stdout.write(self.style.ERROR(f"  Fila {index+3}: Fecha de inicio inválida para campaña {code}. Saltando."))
                 continue

            end_date_str = clean_string(row.get('end_date'))
            end_date = None
            if end_date_str:
                 try:
                     end_date = make_aware(datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S'))
                 except (ValueError, TypeError):
                     self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Fecha de fin inválida para campaña {code}. Se establecerá a None."))


            campaign, created = Campaign.objects.update_or_create(
                campaign_code=code,
                defaults={
                    'campaign_name': name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'description': clean_string(row.get('description')),
                    # Añadir otros campos si los tuvieras en la tabla (budget, is_active, etc.)
                }
            )
            if created: created_count += 1
            else: updated_count += 1
        self.stdout.write(self.style.SUCCESS(f"  Campañas creadas: {created_count}, actualizadas: {updated_count}."))

        # --- 3. Cargar Servicios (service y serviceDetails) ---
        self.stdout.write("Cargando Servicios...")
        df_serv = self.parse_markdown_table(service_data_md)
        df_details = self.parse_markdown_table(service_details_data_md)
        # Asegurar que los códigos en details sean únicos para mapeo fácil
        df_details = df_details.drop_duplicates(subset=['code'], keep='first')
        details_map = df_details.set_index('code').to_dict('index')

        service_objects = {} # Guardar objetos creados para referencias futuras (si es necesario)
        created_count = 0
        updated_count = 0

        for index, row in df_serv.iterrows():
            code = clean_string(row.get('code'))
            cat_code = clean_string(row.get('service_'))
            camp_code = clean_string(row.get('campaign_code'))
            name = clean_string(row.get('name'))

            if not code or not cat_code or not name:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Saltando servicio inválido (código, categoría o nombre vacío)."))
                continue

            # Buscar FKs
            try:
                category = ServiceCategory.objects.get(code=cat_code)
            except ServiceCategory.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"  Fila {index+3}: Categoría '{cat_code}' no encontrada para servicio {code}. Saltando."))
                continue

            campaign = None
            if camp_code:
                try:
                    campaign = Campaign.objects.get(campaign_code=camp_code)
                except Campaign.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Campaña '{camp_code}' no encontrada para servicio {code}. Se asignará None."))

            # Obtener datos de detalles
            details_data = details_map.get(code, {})

            # Crear o actualizar servicio
            service, created = Service.objects.update_or_create(
                code=code,
                defaults={
                    'category': category,
                    'name': name,
                    'is_active': clean_bool(row.get('is_active'), true_values=['1']),
                    'ventulab': clean_bool(row.get('ventulab'), true_values=['enable']),
                    'campaign': campaign,
                    'is_package': clean_bool(row.get('is_package'), true_values=['y']),
                    'audience': clean_string(details_data.get('audience')),
                    'detailed_description': clean_string(details_data.get('description')), # 'description' de df_details
                    'problem_solved': clean_string(details_data.get('resuelve')),
                    # Añadir is_subscription si lo tuvieras en la tabla service
                }
            )
            service_objects[code] = service # Guardar referencia
            if created: created_count += 1
            else: updated_count += 1
        self.stdout.write(self.style.SUCCESS(f"  Servicios creados: {created_count}, actualizados: {updated_count}."))

        # --- 4. Cargar Precios (prices) ---
        self.stdout.write("Cargando Precios...")
        df_prices = self.parse_markdown_table(prices_data_md)
        created_count = 0
        updated_count = 0
        skipped_count = 0
        default_date = datetime.now().date() # Fecha efectiva por defecto

        for index, row in df_prices.iterrows():
            service_code = clean_string(row.get('dloub_id'))
            if not service_code:
                 skipped_count += 1
                 continue

            service = service_objects.get(service_code)
            if not service:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Servicio '{service_code}' no encontrado en la carga anterior. Saltando precios."))
                skipped_count += 1
                continue

            currencies = ['USD', 'CLP', 'COP'] # Monedas en tu tabla
            for currency in currencies:
                price_val = clean_decimal(row.get(currency))
                if price_val > 0: # Solo cargar precios mayores a 0
                    price, created = Price.objects.update_or_create(
                        service=service,
                        currency=currency,
                        effective_date=default_date, # Usar fecha por defecto
                        defaults={'amount': price_val}
                    )
                    if created: created_count += 1
                    else: updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Precios creados: {created_count}, actualizados: {updated_count}, omitidos: {skipped_count}."))

        # --- 5. Cargar Características (servicesFeatures) ---
        self.stdout.write("Cargando Características de Servicios...")
        df_features = self.parse_markdown_table(services_features_data_md)
        created_count = 0
        # Borrar características existentes para este conjunto de servicios para evitar duplicados si se re-ejecuta
        # Es más seguro borrar y recrear que intentar update_or_create sin un identificador único por característica
        service_codes_in_features = df_features['serviceid'].unique()
        ServiceFeature.objects.filter(service__code__in=service_codes_in_features).delete()

        for index, row in df_features.iterrows():
            service_code = clean_string(row.get('serviceid'))
            feature_type = clean_string(row.get('featuretype'))
            description = clean_string(row.get('description'))

            if not service_code or not feature_type or not description:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Saltando característica inválida."))
                continue

            service = service_objects.get(service_code)
            if not service:
                self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Servicio '{service_code}' no encontrado. Saltando característica."))
                continue

            # Validar feature_type contra los choices del modelo
            valid_types = [choice[0] for choice in ServiceFeature.FEATURE_TYPES]
            if feature_type not in valid_types:
                 self.stdout.write(self.style.WARNING(f"  Fila {index+3}: Tipo de característica '{feature_type}' no válido para servicio {service_code}. Saltando."))
                 continue

            ServiceFeature.objects.create(
                service=service,
                feature_type=feature_type,
                description=description
            )
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f"  Características creadas: {created_count}."))


        self.stdout.write(self.style.SUCCESS("¡Carga de datos de servicios completada exitosamente!"))