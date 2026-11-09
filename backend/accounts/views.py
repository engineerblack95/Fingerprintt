from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import OwnerTokenObtainPairSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ - obtain an access/refresh JWT pair."""

    serializer_class = OwnerTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ - rotate an expired access token."""


class MeView(APIView):
    """GET /api/auth/me/ - profile of the signed-in owner."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
