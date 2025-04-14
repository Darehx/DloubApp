# api/management/commands/load_services_from_excel.py

import pandas as pd
import os
import math
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import make_aware

# Importa los modelos relevantes de tu app
from api.models import ServiceCategory, Campaign, Service, Price, ServiceFeature
# Si implementas Packages: from api.models import PackageComponent

# --- Funciones auxiliares de limpieza (sin cambios) ---
def clean_bool(value, true_values=['1', 'enable', 'y', 1, True], false_values=['0', 'disable', 'n', 0, False]):
    if value in true_values: return True
    if value in false_values: return False
    if isinstance(value, str):
        value = value.strip().lower()
        if value in true_values: return True
        if value in false_values: return False
    if pd.isna(value): return False
    return False

def clean_decimal(value, default=Decimal('0.00')):
    if pd.isna(value): return default
    if isinstance(value, str):
         value = value.strip()
         if not value: return default
    try:
        if isinstance(value, float): value = str(value)
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError): return default

def clean_string(value, default=None):
     if pd.isna(value): return default
     val_str = str(value).strip()
     if val_str.endswith('.0'):
         try: return str(int(float(val_str)))
         except ValueError: pass
     return val_str if val_str.lower() != 'nan' else default

def clean_datetime(value):
    if pd.isna(value): return None
    if isinstance(value, datetime):
        if timezone.is_naive(value): return make_aware(value)
        return value
    if isinstance(value, str):
        value = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%d-%m-%Y %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y'): # Añadir más formatos comunes de Excel
            try:
                dt = datetime.strptime(value, fmt)
                if fmt in ('%Y-%m-%d', '%d-%m-%Y'):
                     dt = datetime.combine(dt.date(), datetime.min.time())
                return make_aware(dt)
            except ValueError: pass
    return None


class Command(BaseCommand):
    help = 'Carga datos de servicios, categorías, precios, etc., desde un archivo Excel.'

    def add_arguments(self, parser):
        parser.add_argument(
            'excel_file', type=str, help='Ruta al archivo Excel (.xlsx).'
        )
        parser.add_argument('--sheet-categories', default='serv_code', help='Nombre de la hoja para Categorías (serv_code)')
        parser.add_argument('--sheet-campaigns', default='campaigns', help='Nombre de la hoja para Campañas')
        parser.add_argument('--sheet-services', default='service', help='Nombre de la hoja para Servicios (service)')
        parser.add_argument('--sheet-details', default='serviceDetails', help='Nombre de la hoja para Detalles de Servicio')
        parser.add_argument('--sheet-prices', default='prices', help='Nombre de la hoja para Precios')
        parser.add_argument('--sheet-features', default='servicesFeatures', help='Nombre de la hoja para Características')

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options['excel_file']
        sheet_names = {
            'categories': options['sheet_categories'],
            'campaigns': options['sheet_campaigns'],
            'services': options['sheet_services'],
            'details': options['sheet_details'],
            'prices': options['sheet_prices'],
            'features': options['sheet_features'],
        }

        if not os.path.exists(file_path):
            raise CommandError(f"Archivo Excel no encontrado en: {file_path}")

        self.stdout.write(self.style.SUCCESS(f"Iniciando carga desde: {file_path}"))

        dfs = {}
        try:
            for key, sheet_name in sheet_names.items():
                self.stdout.write(f"  Leyendo hoja: '{sheet_name}'...")
                dfs[key] = pd.read_excel(file_path, sheet_name=sheet_name, dtype=str)
                dfs[key] = dfs[key].replace(['nan', 'NaN', 'None', '', pd.NA], None)
                self.stdout.write(f"    Leídas {len(dfs[key])} filas.")
        except FileNotFoundError: raise CommandError(f"Archivo Excel no encontrado en: {file_path}")
        except ValueError as e: raise CommandError(f"Error leyendo archivo Excel: {e}. Hoja no encontrada o nombre incorrecto ({', '.join(sheet_names.values())}).")
        except Exception as e: raise CommandError(f"Error inesperado leyendo el archivo Excel: {e}")

        # --- 1. Cargar Categorías ---
        self.stdout.write("Cargando Categorías (desde hoja 'serv_code')...")
        created_count, updated_count = 0, 0
        try:
            for index, row in dfs['categories'].iterrows():
                code = clean_string(row.get('code'))
                name = clean_string(row.get('nombre'))
                if not code or not name: continue
                _, created = ServiceCategory.objects.update_or_create(code=code, defaults={'name': name})
                # --- CORRECCIÓN AQUÍ ---
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                # -----------------------
            self.stdout.write(self.style.SUCCESS(f"  Categorías creadas: {created_count}, actualizadas: {updated_count}."))
        except Exception as e:
             raise CommandError(f"Error cargando categorías: {e}")

        # --- 2. Cargar Campañas ---
        self.stdout.write("Cargando Campañas (desde hoja 'campaigns')...")
        created_count, updated_count = 0, 0
        try:
            for index, row in dfs['campaigns'].iterrows():
                code = clean_string(row.get('campaign_code'))
                name = clean_string(row.get('campaign_name'))
                if not code or not name: continue
                start_date = clean_datetime(row.get('start_date'))
                end_date = clean_datetime(row.get('end_date'))
                if not start_date: self.stdout.write(self.style.ERROR(f" Campaña Fila {index+2}: Fecha inicio inválida para {code}. Saltando.")); continue

                _, created = Campaign.objects.update_or_create(
                    campaign_code=code,
                    defaults={
                        'campaign_name': name, 'start_date': start_date, 'end_date': end_date,
                        'description': clean_string(row.get('description')),
                        'budget': clean_decimal(row.get('budget')),
                        'is_active': clean_bool(row.get('is_active'), true_values=['1', 'TRUE', 'True', True]),
                    }
                )
                # --- CORRECCIÓN AQUÍ ---
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                # -----------------------
            self.stdout.write(self.style.SUCCESS(f"  Campañas creadas: {created_count}, actualizadas: {updated_count}."))
        except Exception as e:
             raise CommandError(f"Error cargando campañas: {e}")

        # --- 3. Cargar Servicios ---
        self.stdout.write("Cargando Servicios (desde hojas 'service' y 'serviceDetails')...")
        service_objects = {}
        created_count, updated_count = 0, 0
        try:
            df_details = dfs['details'].drop_duplicates(subset=['code'], keep='first')
            details_map = df_details.set_index('code').to_dict('index')

            for index, row in dfs['services'].iterrows():
                code = clean_string(row.get('code'))
                cat_code = clean_string(row.get('service_'))
                camp_code = clean_string(row.get('campaign_code'))
                name = clean_string(row.get('name'))

                if not code or not cat_code or not name: continue
                try: category = ServiceCategory.objects.get(code=cat_code)
                except ServiceCategory.DoesNotExist: self.stdout.write(self.style.ERROR(f" Serv Fila {index+2}: Cat '{cat_code}' no encontrada para {code}. Saltando.")); continue
                campaign = None
                if camp_code:
                    try: campaign = Campaign.objects.get(campaign_code=camp_code)
                    except Campaign.DoesNotExist: self.stdout.write(self.style.WARNING(f" Serv Fila {index+2}: Campaña '{camp_code}' no encontrada para {code}."))

                details_data = details_map.get(code, {})
                service, created = Service.objects.update_or_create(
                    code=code,
                    defaults={
                        'category': category, 'name': name,
                        'is_active': clean_bool(row.get('is_active'), true_values=['1']),
                        'ventulab': clean_bool(row.get('ventulab'), true_values=['enable']),
                        'campaign': campaign,
                        'is_package': clean_bool(row.get('is_package'), true_values=['Y', 'y']),
                        'is_subscription': clean_bool(row.get('is_subscription')),
                        'audience': clean_string(details_data.get('audience')),
                        'detailed_description': clean_string(details_data.get('description')),
                        'problem_solved': clean_string(details_data.get('resuelve')),
                    }
                )
                service_objects[code] = service
                # --- CORRECCIÓN AQUÍ ---
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                # -----------------------
            self.stdout.write(self.style.SUCCESS(f"  Servicios creados: {created_count}, actualizados: {updated_count}."))
        except Exception as e:
            raise CommandError(f"Error cargando servicios: {e}")

        # --- 4. Cargar Precios ---
        self.stdout.write("Cargando Precios (desde hoja 'prices')...")
        created_count, updated_count, skipped_count = 0, 0, 0 # Reiniciar contadores para precios
        try:
            default_date = datetime.now().date()
            service_codes_in_prices = dfs['prices']['dloub_id'].dropna().unique()
            Price.objects.filter(service__code__in=service_codes_in_prices, effective_date=default_date).delete()
            self.stdout.write(f"  Precios anteriores borrados para {len(service_codes_in_prices)} servicios en fecha {default_date}.")

            for index, row in dfs['prices'].iterrows():
                service_code = clean_string(row.get('dloub_id'))
                if not service_code: skipped_count += 1; continue
                service = service_objects[service_code] # Usar corchetes, fallará si no existe (más directo)

                currencies = ['USD', 'CLP', 'COP']
                for currency in currencies:
                    price_val = clean_decimal(row.get(currency))
                    if price_val > 0:
                        price_obj, created = Price.objects.update_or_create( # Usar update_or_create aquí también por si acaso
                            service=service, currency=currency, effective_date=default_date,
                            defaults={'amount': price_val}
                        )
                        # --- CORRECCIÓN AQUÍ ---
                        if created:
                             created_count += 1
                        else:
                             updated_count += 1 # Contar actualizaciones también
                        # -----------------------
                    else:
                         skipped_count += 1 # Contar precios cero u omitidos

            self.stdout.write(self.style.SUCCESS(f"  Precios creados: {created_count}, actualizados: {updated_count}, omitidos/cero: {skipped_count}."))
        except KeyError as e:
             raise CommandError(f"Error cargando precios: Servicio con código '{e}' no encontrado en la carga anterior. Verifica la hoja 'service'.")
        except Exception as e:
             raise CommandError(f"Error cargando precios: {e}")


        # --- 5. Cargar Características ---
        self.stdout.write("Cargando Características (desde hoja 'servicesFeatures')...")
        created_count, skipped_count = 0, 0
        try:
            df_features = dfs['features']
            service_codes_in_features = df_features['serviceid'].dropna().unique()
            ServiceFeature.objects.filter(service__code__in=service_codes_in_features).delete()
            self.stdout.write(f"  Características anteriores borradas para {len(service_codes_in_features)} servicios.")

            for index, row in df_features.iterrows():
                service_code = clean_string(row.get('serviceid'))
                feature_type = clean_string(row.get('featuretype'))
                description = clean_string(row.get('description'))

                if not service_code or not feature_type or not description: skipped_count += 1; continue
                service = service_objects[service_code] # Usar corchetes

                valid_types = [choice[0] for choice in ServiceFeature.FEATURE_TYPES]
                if feature_type not in valid_types: self.stdout.write(self.style.WARNING(f" Feat Fila {index+2}: Tipo '{feature_type}' inválido para {service_code}. Saltando.")); skipped_count += 1; continue

                ServiceFeature.objects.create(service=service, feature_type=feature_type, description=description)
                created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Características creadas: {created_count}, omitidas: {skipped_count}."))
        except KeyError as e:
             raise CommandError(f"Error cargando características: Servicio con código '{e}' no encontrado en la carga anterior. Verifica la hoja 'service'.")
        except Exception as e:
             raise CommandError(f"Error cargando características: {e}")


        # --- 6. Cargar Paquetes (Opcional) ---
        # ...

        self.stdout.write(self.style.SUCCESS(f"¡Carga de datos desde '{file_path}' completada exitosamente!"))