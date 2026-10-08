from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrAuthenticatedReadOnly(BasePermission):
    """Allow authenticated users to read the catalog; only staff may change it."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or user.is_staff
