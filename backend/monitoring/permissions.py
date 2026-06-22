"""
Smart-Stua RBAC — Permission Helpers
======================================
Provides:
  - get_smartstua_user(django_user)  — resolve shadow Django auth.User → monitoring.User
  - is_admin(user_obj)               — True when user has the 'admin' role
  - IsNodeOwnerOrAdmin               — DRF permission class for node-scoped views
  - IsAdminRole                      — DRF permission class for admin-only views

Architecture note
-----------------
DRF TokenAuthentication sets request.user to a django.contrib.auth.User.
Our custom monitoring.User is linked via the shadow username pattern:
    django.auth.User.username == f"smartstua_{monitoring.User.user_id}"

get_smartstua_user() resolves this link efficiently with a single extra DB query
(only called once per request via the view; result can be cached on request).
"""

import logging
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


# ─── User Resolution ──────────────────────────────────────────────────────────

def get_smartstua_user(django_user):
    """
    Resolve a DRF-authenticated django.contrib.auth.User back to the
    corresponding monitoring.User instance.

    Returns None for anonymous users or if the mapping is broken.
    """
    from .models import User as SmartstuaUser

    if not django_user or not django_user.is_authenticated:
        return None

    username = django_user.username  # e.g. "smartstua_3"
    if not username.startswith('smartstua_'):
        # Legacy admin login via Django admin panel — treat as platform admin
        if django_user.is_superuser:
            # Return the first admin user in our custom model as proxy
            return SmartstuaUser.objects.filter(role='admin', is_active=True).first()
        return None

    try:
        user_id = int(username.split('_')[1])
        return SmartstuaUser.objects.get(user_id=user_id, is_active=True)
    except (ValueError, IndexError, SmartstuaUser.DoesNotExist):
        logger.warning(f'[RBAC] Could not resolve smartstua user for django user: {username}')
        return None


def is_admin(user_obj) -> bool:
    """Return True if the monitoring.User has the 'admin' role."""
    if user_obj is None:
        return False
    return user_obj.role == 'admin'


def assert_node_access(user_obj, node):
    """
    Raise PermissionDenied if a non-admin user attempts to access a node
    they do not own.

    Usage in views:
        user_obj = get_smartstua_user(request.user)
        assert_node_access(user_obj, node)
    """
    if user_obj is None:
        raise PermissionDenied('Authentication required.')

    if is_admin(user_obj):
        return  # Admins have global access

    if node.owner is None:
        # Unowned nodes: only admins can access (prevents data leaks)
        raise PermissionDenied(
            'This node has not been assigned to an owner. '
            'Contact your system administrator.'
        )

    if node.owner_id != user_obj.user_id:
        raise PermissionDenied(
            'You do not have permission to access this sensor node.'
        )


# ─── DRF Permission Classes ───────────────────────────────────────────────────

class IsAdminRole(BasePermission):
    """
    Grants access only to users with the monitoring.User role='admin'.
    Use for user management, platform-wide analytics, etc.
    """
    message = 'Only system administrators can perform this action.'

    def has_permission(self, request, view):
        user_obj = get_smartstua_user(request.user)
        return is_admin(user_obj)


class IsNodeOwnerOrAdmin(BasePermission):
    """
    Object-level permission: allow access only if the user is the node
    owner OR has the admin role.

    Apply to ViewSets or generic views that deal with a single SensorNode.
    For function-based views, use assert_node_access() directly.
    """
    message = 'You do not have permission to access this sensor node.'

    def has_object_permission(self, request, view, obj):
        user_obj = get_smartstua_user(request.user)
        if user_obj is None:
            return False
        if is_admin(user_obj):
            return True
        return obj.owner_id == user_obj.user_id
