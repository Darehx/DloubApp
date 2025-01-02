from rest_framework import viewsets
from .models import FormQuestion, FormResponse
from .serializers import FormQuestionSerializer, FormResponseSerializer

class FormQuestionViewSet(viewsets.ModelViewSet):
    queryset = FormQuestion.objects.all()
    serializer_class = FormQuestionSerializer
    
class FormResponseViewSet(viewsets.ModelViewSet):
    queryset = FormResponse.objects.all()
    serializer_class = FormResponseSerializer