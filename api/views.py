from rest_framework.decorators import action
from rest_framework import viewsets
from .models import FormQuestion, FormResponse
from rest_framework.response import Response
from rest_framework import status
from .serializers import FormResponseSerializer, FormResponseBulkCreateSerializer

class FormResponseViewSet(viewsets.ModelViewSet):
    queryset = FormResponse.objects.all()
    serializer_class = FormResponseSerializer

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Endpoint para crear múltiples respuestas en una sola solicitud.
        """
        serializer = FormResponseBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Respuestas creadas exitosamente."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
