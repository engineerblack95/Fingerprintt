import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .serializers import (
    OwnerTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


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


class RegisterView(APIView):
    """POST /api/auth/register/ - create a standard dashboard account.

    The endpoint is public and throttled. Every account it creates is a
    regular user (``is_staff=False``, ``is_superuser=False``): they can sign in
    and monitor the shared dashboard but cannot modify data or open the Django
    admin. Only the existing administrator can create staff accounts, via the
    Django admin.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()
        except IntegrityError:
            # Covers a race where two requests pass validation together.
            raise ValidationError(
                "That username or email address is already registered."
            )

        refresh = OwnerTokenObtainPairSerializer.get_token(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/ - email a single-use reset link.

    The response is deliberately identical whether or not the address belongs
    to an account, so the endpoint cannot be used to discover which email the
    owner registered with.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    GENERIC_MESSAGE = (
        "If an account exists for that email address, a password reset link "
        "is on its way. Check your inbox (and the spam folder)."
    )

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip()
        user = (
            User.objects.filter(email__iexact=email, is_active=True)
            .order_by("pk")
            .first()
        )

        if user is not None:
            try:
                self._send_reset_email(user)
            except Exception:
                # Never leak delivery problems (or account existence) to the
                # caller; the failure is logged for the operator instead.
                logger.exception(
                    "Failed to send password reset email for user %s", user.pk
                )

        return Response({"detail": self.GENERIC_MESSAGE})

    @staticmethod
    def _send_reset_email(user: User) -> None:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = (
            f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
        )

        from notifications.emails import send_password_reset_email

        send_password_reset_email(user, reset_url)


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/ - set a new password.

    Accepts the ``uid`` and ``token`` from the emailed link plus the new
    password. Expired or already-used tokens are rejected with a clear 400 so
    the UI can ask for a fresh link.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    INVALID_LINK_MESSAGE = (
        "This password reset link is invalid or has expired. "
        "Please request a new one."
    )

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = self._user_from_uid(serializer.validated_data["uid"])
        if user is None or not default_token_generator.check_token(
            user, serializer.validated_data["token"]
        ):
            raise ValidationError(self.INVALID_LINK_MESSAGE)

        # Re-run the validators with the account attached so passwords that are
        # too similar to the username or email are rejected as well.
        try:
            validate_password(serializer.validated_data["password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError(" ".join(exc.messages))

        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        logger.info("Password reset completed for user %s", user.pk)

        return Response(
            {
                "detail": (
                    "Your password has been updated. You can now sign in with "
                    "your new password."
                )
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _user_from_uid(uid: str):
        try:
            user_id = urlsafe_base64_decode(uid).decode()
            return User.objects.get(pk=user_id, is_active=True)
        except (
            ValueError,
            TypeError,
            OverflowError,
            UnicodeDecodeError,
            User.DoesNotExist,
        ):
            return None
