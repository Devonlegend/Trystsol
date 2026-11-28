from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    message = "Administrator role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)


class IsFounderRole(BasePermission):
    message = "Founder role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "founder")


class IsReviewerRole(BasePermission):
    message = "Reviewer role required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "reviewer")
