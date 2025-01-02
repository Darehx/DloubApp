from rest_framework import serializers
from .models import FormQuestion, FormResponse, Form



class FormQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormQuestion
        fields = '__all__'


class FormResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormResponse
        fields = ['customer', 'form', 'question', 'text']

class FormResponseBulkCreateSerializer(serializers.Serializer):
    customer = serializers.IntegerField()
    form = serializers.IntegerField()
    responses = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(max_length=1000)
        )
    )

    def validate(self, data):
        # Validar si el formulario existe
        try:
            form = Form.objects.get(pk=data['form'])
            data['form_instance'] = form
        except Form.DoesNotExist:
            raise serializers.ValidationError({"form": "Formulario no encontrado."})

        # Validar preguntas
        question_ids = [response["question"] for response in data["responses"]]
        valid_questions = FormQuestion.objects.filter(id__in=question_ids, form=data['form'])
        if len(valid_questions) != len(question_ids):
            raise serializers.ValidationError({"responses": "Algunas preguntas no son válidas para este formulario."})

        return data

    def create(self, validated_data):
        customer_id = validated_data['customer']
        form_instance = validated_data['form_instance']
        responses_data = validated_data['responses']

        # Crear objetos para insertar en la BD
        responses = [
            FormResponse(
                customer_id=customer_id,
                form=form_instance,
                question_id=response['question'],
                text=response['text']
            )
            for response in responses_data
        ]
        FormResponse.objects.bulk_create(responses)
        return responses
