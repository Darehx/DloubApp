# api/views/utilities.py
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import Notification, AuditLog
from ..permissions import IsAuthenticated, CanViewAuditLogs, IsAdminOrDragon

# --- Importaciones de Serializers Corregidas ---
from ..serializers.utilities import NotificationSerializer, AuditLogSerializer
# ----------------------------------------------

logger = logging.getLogger(__name__)
User = get_user_model()

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Notificaciones de usuario.
    """
    # Usa el serializer importado correctamente
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """ Filtra las notificaciones para mostrar solo las del usuario actual. """
        user_instance = self.request.user
        return Notification.objects.filter(user=user_instance).order_by('-created_at')

    def perform_update(self, serializer):
         # ... (lógica sin cambios) ...
         return Response({"detail": "Acción no permitida. Usa 'mark-read'."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def perform_destroy(self, instance):
        # ... (lógica sin cambios) ...
        if instance.user != self.request.user:
             return Response(status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        logger.info(f"Notificación {instance.id} eliminada por usuario {self.request.user.username}")


    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_as_read(self, request, pk=None):
        # ... (lógica sin cambios) ...
        notification = self.get_object()
        if not notification.read:
            notification.read = True
            notification.save(update_fields=['read'])
            logger.debug(f"Notificación {pk} marcada como leída por {request.user.username}")
        # Usa el serializer de la clase (NotificationSerializer)
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_as_read(self, request):
        # ... (lógica sin cambios) ...
        queryset = self.get_queryset().filter(read=False)
        updated_count = queryset.update(read=True)
        logger.info(f"{updated_count} notificaciones marcadas como leídas para {request.user.username}")
        return Response({'status': f'{updated_count} notificaciones marcadas como leídas'})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        # ... (lógica sin cambios) ...
        count = self.get_queryset().filter(read=False).count()
        return Response({'unread_count': count})


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de solo lectura para ver los Registros de Auditoría (Audit Logs).
    """
    queryset = AuditLog.objects.select_related('user').all().order_by('-timestamp')
    # Usa el serializer importado correctamente
    serializer_class = AuditLogSerializer
    permission_classes = [CanViewAuditLogs]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'user__username': ['exact', 'icontains'],
        'action': ['exact', 'icontains'],
        'timestamp': ['date', 'date__gte', 'date__lte', 'year', 'month', 'time__gte', 'time__lte'],
        'target_model': ['exact', 'icontains'],
        'target_id': ['exact'],
        'ip_address': ['exact'],
    }