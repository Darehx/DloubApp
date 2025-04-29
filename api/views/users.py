# api/views/users.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth import get_user_model

# --- Importaciones de Serializers Corregidas ---
from ..serializers.base import BasicUserSerializer # Importar desde base.py
# ----------------------------------------------

User = get_user_model()

class UserMeView(APIView):
    """
    Devuelve los datos del usuario actualmente autenticado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene y serializa los datos del usuario logueado.
        """
        try:
            user = User.objects.select_related(
                'profile__primary_role',
                'employee_profile__position'
            ).get(pk=request.user.pk)
        except User.DoesNotExist:
             return Response({"detail": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except AttributeError as e:
             print(f"Advertencia: Error al acceder a relaciones en UserMeView para usuario {request.user.pk}: {e}")
             user = request.user

        # Usa el BasicUserSerializer importado correctamente
        serializer = BasicUserSerializer(user, context={'request': request})
        return Response(serializer.data)

# Si añades UserViewSet u otras vistas aquí que usen UserCreateSerializer, UserRoleSerializer, etc.
# deberás importarlos desde ..serializers.users
# from ..serializers.users import UserCreateSerializer, UserRoleSerializer, UserRoleAssignmentSerializer