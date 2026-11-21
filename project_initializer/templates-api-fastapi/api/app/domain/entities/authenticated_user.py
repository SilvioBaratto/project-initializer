"""The caller of a request, as the application sees it after authentication."""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """An authenticated principal, independent of how it was authenticated.

    Attributes:
        id: Stable identifier of the principal; safe to write to audit logs.
        auth_method: How the caller proved its identity: ``"development"``,
            ``"static_token"``, ``"jwt"``, ``"supabase"``, ``"entra"`` or
            ``"test"``.
        email: Email address when the identity provider supplies one.
        username: Username when the identity provider supplies one.
        roles: Roles granted to the principal; empty when none apply.
    """

    id: str
    auth_method: str
    email: str | None = None
    username: str | None = None
    roles: tuple[str, ...] = ()

    def has_any_role(self, roles: Iterable[str]) -> bool:
        """Report whether the principal holds at least one of the given roles.

        Args:
            roles: Acceptable roles. An empty iterable matches nobody.

        Returns:
            True when at least one given role is among the principal's roles.
        """
        return not set(self.roles).isdisjoint(roles)
