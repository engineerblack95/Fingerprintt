from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Owner / administrator account used to sign in to the dashboard."""

    email = models.EmailField(unique=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username
