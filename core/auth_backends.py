"""Authentication backends for core app."""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate using either username or email with the same password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        lookup_value = username or kwargs.get(user_model.USERNAME_FIELD)
        if lookup_value is None or password is None:
            return None

        try:
            user = user_model.objects.get(
                Q(username__iexact=lookup_value) | Q(email__iexact=lookup_value)
            )
        except user_model.DoesNotExist:
            user_model().set_password(password)
            return None
        except user_model.MultipleObjectsReturned:
            # Fall back to deterministic selection if duplicates exist.
            user = user_model.objects.filter(
                Q(username__iexact=lookup_value) | Q(email__iexact=lookup_value)
            ).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
