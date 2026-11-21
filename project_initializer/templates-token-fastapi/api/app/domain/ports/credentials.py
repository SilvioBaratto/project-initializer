"""Credential ports: password hashing and signed access tokens."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordHasherPort(Protocol):
    """Turns passwords into storable hashes and checks candidates against them."""

    def hash(self, password: str) -> str:
        """Hash a password with a fresh random salt.

        Args:
            password: Plain-text password.

        Returns:
            A self-describing hash; hashing the same password twice gives two
            different values.

        Raises:
            ValueError: The password is longer than the algorithm can use.
        """
        ...

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Check a candidate password against a stored hash.

        Args:
            password: Plain-text candidate.
            password_hash: Stored hash. None, empty or malformed stands for an
                account that cannot match, such as an unknown email: the check
                still costs the same as a real one, so response time does not
                reveal that the account is missing.

        Returns:
            True only when the password matches the hash. Never raises for bad
            input.
        """
        ...


@runtime_checkable
class AccessTokenIssuerPort(Protocol):
    """Signs short-lived access tokens and reads the subject back from them."""

    def issue(self, subject: str) -> str:
        """Create a signed token that expires on its own.

        Args:
            subject: Identifier of the account the token is for.

        Returns:
            The encoded token.
        """
        ...

    def subject_of(self, token: str) -> str:
        """Verify a token and return the account it names.

        Args:
            token: Encoded token received from a client.

        Returns:
            The subject the token was issued for.

        Raises:
            AuthenticationError: The token is malformed, tampered with, expired,
                signed with another key or algorithm, or lacks an expiry or a
                subject.
        """
        ...
