# api/views/authentication.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import status
from django.contrib.auth import get_user_model

# --- Importaciones de Serializers Corregidas ---
# Importar desde los nuevos módulos específicos
from ..serializers.authentication import CustomTokenObtainPairSerializer
from ..serializers.base import BasicUserSerializer
# ----------------------------------------------

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Vista personalizada para obtener tokens JWT, usando el serializer customizado.
    """
    # El serializer_class ahora apunta al importado correctamente
    serializer_class = CustomTokenObtainPairSerializer

class CheckAuthView(APIView):
    """
    Verifica si el usuario actual está autenticado y devuelve sus datos básicos.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Devuelve el estado de autenticación y los datos del usuario.
        """
        try:
            user = User.objects.select_related(
                'profile__primary_role',
                'employee_profile__position'
            ).get(pk=request.user.pk)
        except User.DoesNotExist:
             return Response({"isAuthenticated": False, "user": None}, status=status.HTTP_401_UNAUTHORIZED)
        except AttributeError as e:
             print(f"Advertencia: Error al acceder a relaciones en CheckAuthView para usuario {request.user.pk}: {e}")
             user = request.user

        # Usa el BasicUserSerializer importado correctamente
        serializer = BasicUserSerializer(user, context={'request': request})
        data = {"isAuthenticated": True, "user": serializer.data}
        return Response(data)