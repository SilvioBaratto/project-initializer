"""Role-based access control on top of ``get_current_user``."""

from collections.abc import Callable

from app.api.auth_deps import CurrentUser
from app.domain.entities.authenticated_user import AuthenticatedUser
from app.domain.exceptions import AuthorizationError


def require_roles(*roles: str) -> Callable[..., AuthenticatedUser]:
    """Build a dependency that admits only callers holding one of the roles.

    Use it as ``Depends(require_roles("admin"))`` on a route or router.

    Args:
        *roles: Acceptable roles; holding any one of them is enough.

    Returns:
        A dependency that returns the authenticated user.

    Raises:
        ValueError: No role was given. Failing at import time beats a route that
            silently rejects everybody.
    """
    if not roles:
        raise ValueError("require_roles needs at least one role")

    def dependency(current_user: CurrentUser) -> AuthenticatedUser:
        """Return the caller when they hold a required role."""
        if not current_user.has_any_role(roles):
            raise AuthorizationError(log_context={"required_roles": list(roles)})
        return current_user

    return dependency
