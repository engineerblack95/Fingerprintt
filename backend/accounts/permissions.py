from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_administrator(user) -> bool:
    """The platform administrator is a staff/superuser account."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
    )


class IsAdminOrReadOnly(BasePermission):
    """Signed-in users may read; only the administrator may change data.

    Used by the shared-workspace resources (members, templates). Standard
    accounts created through the public registration page are deliberately
    read-only, while the Django superuser keeps full control.
    """

    message = "Administrator access is required to make changes."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return is_administrator(request.user)


class IsAdministrator(BasePermission):
    """Only the platform administrator may use this endpoint."""

    message = "Administrator access is required."

    def has_permission(self, request, view):
        return is_administrator(request.user)
