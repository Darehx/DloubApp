# api/views/forms.py
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import FormResponse, Form, FormQuestion, Customer
from ..permissions import IsAuthenticated, CanViewFormResponses, IsAdminOrDragon
from ..services import FormResponseService

# --- Importaciones de Serializers Corregidas ---
from ..serializers.forms import (
    FormResponseSerializer, FormResponseBulkCreateSerializer
    # Añadir Form/Question si hay ViewSet para ellos
    # FormSerializer, FormQuestionSerializer
)
# ----------------------------------------------

logger = logging.getLogger(__name__)
User = get_user_model()

# ... (Posibles ViewSets para Form y FormQuestion) ...

class FormResponseViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Respuestas a Formularios (Form Responses).
    """
    # Usa el serializer importado correctamente
    serializer_class = FormResponseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'form': ['exact'], 'form__title': ['icontains'],
        'question': ['exact'], 'question__text': ['icontains'],
        'customer__user__username': ['exact', 'icontains'],
        'customer__company_name': ['icontains'],
        'created_at': ['date', 'date__gte', 'date__lte'],
        'text': ['icontains']
    }

    def get_queryset(self):
        # ... (lógica sin cambios) ...
        user = self.request.user
        base_qs = FormResponse.objects.select_related(
            'customer', 'customer__user', 'form', 'question'
        )

        if hasattr(user, 'customer_profile') and user.customer_profile:
            return base_qs.filter(customer=user.customer_profile)
        elif hasattr(user, 'employee_profile'):
            checker = CanViewFormResponses()
            if checker.has_permission(request=self.request, view=self):
                return base_qs.all()
            else:
                return FormResponse.objects.none()
        else:
            return FormResponse.objects.none()

    def perform_create(self, serializer):
        # ... (lógica sin cambios) ...
        user = self.request.user
        if hasattr(user, 'customer_profile') and user.customer_profile:
            # El serializer ya tiene customer como write_only=True, required=False
            serializer.save(customer=user.customer_profile)
        else:
            raise PermissionDenied(_("Solo los clientes autenticados pueden enviar respuestas de formulario."))

    def perform_update(self, serializer):
        # ... (lógica sin cambios) ...
        raise PermissionDenied(_("Las respuestas de formulario no pueden ser modificadas una vez enviadas."))

    def perform_destroy(self, instance):
        # ... (lógica sin cambios) ...
        user = self.request.user
        checker = IsAdminOrDragon()
        if not checker.has_permission(request=self.request, view=self):
            raise PermissionDenied(_("No tienes permiso para eliminar esta respuesta."))
        instance.delete()


    @action(detail=False, methods=['post'],
            serializer_class=FormResponseBulkCreateSerializer, # Usa el serializer importado
            permission_classes=[IsAuthenticated])
    def bulk_create(self, request):
        # ... (lógica sin cambios, usa el servicio) ...
        user = request.user
        if not hasattr(user, 'customer_profile') or not user.customer_profile:
            return Response(
                {"detail": _("Solo los clientes pueden usar la creación masiva de respuestas.")},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            created_responses = FormResponseService.bulk_create_responses(
                serializer.validated_data,
                user.customer_profile
            )
            return Response(
                {"message": _("Respuestas creadas exitosamente."), "count": len(created_responses)},
                status=status.HTTP_201_CREATED
            )
        except ValueError as ve:
            logger.warning(f"Error de validación en bulk_create FormResponse por {user.username}: {ve}")
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error inesperado en bulk_create FormResponse por {user.username}: {e}", exc_info=True)
            return Response(
                {"detail": _("Ocurrió un error interno procesando las respuestas.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )