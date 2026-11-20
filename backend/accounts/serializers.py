import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User

USERNAME_RE = re.compile(r"^[\w.@+-]+$")


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_staff",
            "is_superuser",
            "last_login",
        )
        read_only_fields = fields

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.username


class OwnerTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT login response enriched with the owner's profile."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class RegisterSerializer(serializers.Serializer):
    """Create a standard (non-staff) dashboard account.

    Registered accounts are intentionally *not* staff and *not* superusers:
    they get read access to the shared dashboard and are refused by every
    write endpoint and by the Django admin.
    """

    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    password = serializers.CharField(
        min_length=8, write_only=True, trim_whitespace=False
    )
    password_confirm = serializers.CharField(
        min_length=8, write_only=True, trim_whitespace=False
    )

    def validate_username(self, value: str) -> str:
        username = value.strip()
        if not USERNAME_RE.match(username):
            raise serializers.ValidationError(
                "Use only letters, numbers and the characters @ . + - _"
            )
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("That username is already taken.")
        return username

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with that email address already exists."
            )
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "The two passwords do not match."}
            )

        # Validate against the account being created so passwords that are too
        # similar to the username or email are rejected too.
        candidate = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        return User.objects.create_user(
            password=password,
            is_staff=False,
            is_superuser=False,
            **validated_data,
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Payload for POST /api/auth/password-reset/."""

    email = serializers.EmailField(
        help_text="Email address on the owner account."
    )


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Payload for POST /api/auth/password-reset/confirm/.

    ``uid`` and ``token`` come from the link in the reset email; the two
    password fields are compared here so the view only deals with a validated
    value.
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(
        min_length=8, write_only=True, trim_whitespace=False
    )
    password_confirm = serializers.CharField(
        min_length=8, write_only=True, trim_whitespace=False
    )

    def validate_password(self, value: str) -> str:
        # Run Django's configured password validators (length, common
        # passwords, all-numeric, similarity to the username/email).
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "The two passwords do not match."}
            )
        return attrs
