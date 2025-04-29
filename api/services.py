# api/services.py
import logging
from django.utils.translation import gettext_lazy as _
from .models import FormResponse, Customer, Form, FormQuestion # Asegúrate que los modelos existan y se importen

logger = logging.getLogger(__name__)

class FormResponseService:
    """
    Contiene lógica de negocio relacionada con las respuestas de formularios.
    """
    @staticmethod
    def bulk_create_responses(validated_data, customer: Customer):
        """
        Crea múltiples respuestas de formulario para un cliente dado.
        Espera 'validated_data' de FormResponseBulkCreateSerializer.
        """
        if not isinstance(customer, Customer):
             logger.error(f"[FormResponseService] Se esperaba una instancia de Customer, se recibió {type(customer)}")
             raise TypeError(_("Se requiere un perfil de cliente válido."))

        form = validated_data.get('form')
        responses_data = validated_data.get('responses', [])

        if not form or not responses_data:
            logger.warning(f"[FormResponseService] Datos insuficientes para bulk_create. Form: {form}, Responses Count: {len(responses_data)}")
            return [] # O lanzar ValidationError si es mandatorio

        responses_to_create = []
        # Validar que las preguntas pertenezcan al formulario podría ser una buena adición aquí
        form_question_ids = set(FormQuestion.objects.filter(form=form).values_list('id', flat=True))

        for item in responses_data:
            question = item.get('question')
            text = item.get('text', '') # Asegurar que text siempre tenga un valor

            if not question:
                 logger.warning(f"[FormResponseService] Item sin pregunta en bulk_create para cliente {customer.id}")
                 continue # O lanzar error si la pregunta es obligatoria

            if question.id not in form_question_ids:
                logger.error(f"[FormResponseService] Intento de respuesta a pregunta ({question.id}) que no pertenece al formulario ({form.id}) por cliente {customer.id}")
                raise ValueError(_("La pregunta proporcionada no pertenece al formulario especificado.")) # O simplemente omitir

            responses_to_create.append(
                FormResponse(
                    customer=customer,
                    form=form,
                    question=question,
                    text=text
                )
            )

        if responses_to_create:
            try:
                created_responses = FormResponse.objects.bulk_create(responses_to_create)
                logger.info(f"[FormResponseService] {len(created_responses)} respuestas creadas masivamente para cliente {customer.id}, formulario {form.id}.")
                return created_responses
            except Exception as e:
                logger.error(f"[FormResponseService] Error durante bulk_create para cliente {customer.id}: {e}", exc_info=True)
                # Podrías relanzar una excepción personalizada o manejarla
                raise # Relanza la excepción original para que la vista la maneje
        else:
            logger.info(f"[FormResponseService] No se crearon respuestas (lista vacía) para cliente {customer.id}, formulario {form.id}.")
            return []

# Puedes añadir más clases de servicio aquí para otras áreas (OrderService, InvoiceService, etc.)