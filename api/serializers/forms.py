# api/serializers/forms.py
"""
Serializers relacionados con Formularios, Preguntas y Respuestas.
"""
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

# Importar modelos necesarios
from ..models import Form, FormQuestion, FormResponse

class FormQuestionSerializer(serializers.ModelSerializer):
    """ Serializer para Preguntas de Formulario. """
    class Meta:
        model = FormQuestion
        # Excluir 'form' si siempre se anida dentro de FormSerializer
        fields = ['id', 'question_text', 'order', 'required']
        # read_only_fields = ['id'] # ID es read_only por defecto

class FormSerializer(serializers.ModelSerializer):
    """ Serializer para Formularios, incluyendo sus preguntas anidadas. """
    questions = FormQuestionSerializer(many=True, read_only=True) # Anidar preguntas
    class Meta:
        model = Form
        fields = ['id', 'name', 'description', 'created_at', 'questions']
        read_only_fields = ['id', 'created_at', 'questions'] # Questions se gestionan por separado o al crear el Form

class FormResponseSerializer(serializers.ModelSerializer):
    """ Serializer para ver/crear respuestas individuales a formularios. """
    # Campos legibles para mostrar información relacionada
    customer_name = serializers.CharField(source='customer.__str__', read_only=True)
    form_name = serializers.CharField(source='form.name', read_only=True)
    question_text = serializers.CharField(source='question.question_text', read_only=True)

    class Meta:
        model = FormResponse
        fields = [
            'id', 'customer', 'customer_name', 'form', 'form_name',
            'question', 'question_text', 'text', 'created_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'customer_name', 'form_name', 'question_text'
        ]
        # Configuración para escritura (creación)
        extra_kwargs = {
            # Customer se asigna en la vista, no se envía en el payload
            'customer': {'write_only': True, 'required': False, 'allow_null': True},
            'form': {'write_only': True, 'required': True, 'queryset': Form.objects.all()},
            'question': {'write_only': True, 'required': True, 'queryset': FormQuestion.objects.all()}
        }

class FormResponseBulkItemSerializer(serializers.Serializer):
    """ Serializer para un item individual dentro de una creación masiva de respuestas. """
    question = serializers.PrimaryKeyRelatedField(queryset=FormQuestion.objects.all(), required=True)
    text = serializers.CharField(max_length=5000, allow_blank=True)

class FormResponseBulkCreateSerializer(serializers.Serializer):
    """ Serializer para la creación masiva de respuestas a un formulario. """
    form = serializers.PrimaryKeyRelatedField(queryset=Form.objects.all(), required=True)
    responses = FormResponseBulkItemSerializer(many=True, required=True, min_length=1) # Debe haber al menos una respuesta

    def validate(self, data):
        """ Valida que todas las preguntas pertenezcan al formulario especificado. """
        form = data['form']
        responses_data = data['responses']
        form_question_ids = set(form.questions.values_list('id', flat=True))
        submitted_question_ids = set()

        for idx, response_item in enumerate(responses_data):
            question = response_item['question']
            # Verificar pertenencia al formulario
            if question.id not in form_question_ids:
                raise ValidationError({
                    f"responses[{idx}].question": f"La pregunta ID {question.id} no pertenece al formulario '{form.name}'."
                })
            # Verificar preguntas duplicadas en el mismo envío
            if question.id in submitted_question_ids:
                 raise ValidationError({
                    f"responses[{idx}].question": f"La pregunta ID {question.id} se ha enviado más de una vez en esta solicitud."
                 })
            submitted_question_ids.add(question.id)

            # Opcional: Validar requeridos aquí si no se hace en otro lugar
            # if question.required and not response_item.get('text', '').strip():
            #    raise ValidationError({f"responses[{idx}].text": "Esta pregunta es requerida y no puede estar vacía."})

        return data