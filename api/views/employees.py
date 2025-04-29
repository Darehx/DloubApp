# api/views/employees.py
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model

# Importaciones relativas
from ..models import Employee, JobPosition
from ..permissions import CanManageEmployees, CanManageJobPositions, IsAdminOrDragon

# --- Importaciones de Serializers Corregidas ---
from ..serializers.employees import (
    EmployeeSerializer, EmployeeCreateSerializer, JobPositionSerializer
)
# ----------------------------------------------

User = get_user_model()

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Empleados (Employees).
    """
    queryset = Employee.objects.select_related(
        'user',
        'user__profile__primary_role',
        'position'
    ).prefetch_related(
        'user__secondary_role_assignments__role'
    ).filter(user__is_active=True)
    permission_classes = [CanManageEmployees]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'position__name': ['exact', 'icontains'],
        'user__username': ['exact', 'icontains'],
        'user__email': ['exact', 'icontains'],
        'user__first_name': ['icontains'],
        'user__last_name': ['icontains'],
        'user__profile__primary_role__name': ['exact', 'icontains'],
        'user__is_active': ['exact']
    }

    def get_serializer_class(self):
        """ Usa un serializer diferente para la creación. """
        # Usa los serializers importados correctamente
        if self.action == 'create':
            return EmployeeCreateSerializer
        return EmployeeSerializer

    # Similar a CustomerViewSet, puedes sobrescribir create si necesitas
    # devolver la instancia creada usando EmployeeSerializer en lugar de EmployeeCreateSerializer
    # (aunque el comportamiento por defecto suele ser suficiente).
    def perform_create(self, serializer):
        serializer.save()


class JobPositionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar Puestos de Trabajo (Job Positions).
    """
    queryset = JobPosition.objects.all()
    # Usa el serializer importado correctamente
    serializer_class = JobPositionSerializer
    permission_classes = [CanManageJobPositions]