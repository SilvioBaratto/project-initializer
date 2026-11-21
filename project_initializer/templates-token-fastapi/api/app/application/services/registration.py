"""Account registration use case of the token variant.

The service depends on ports only, so unit tests run it against in-memory fakes.
It needs no token issuer, so registration keeps working while JWT signing is not
configured.
"""

from app.application.commands.user import RegisterUserCommand
from app.application.dto.user import UserDTO
from app.domain.entities.user import NewUser
from app.domain.exceptions import ConflictError, DomainValidationError
from app.domain.ports.credentials import PasswordHasherPort
from app.domain.ports.unit_of_work import UnitOfWorkPort
from app.domain.ports.user_repository import UserRepositoryPort

REGISTRATION_CONFLICT_MESSAGE = "Registration could not be completed"
UNUSABLE_PASSWORD_MESSAGE = "The password cannot be used"


class RegistrationService:
    """Creates accounts from a registration command."""

    def __init__(
        self,
        users: UserRepositoryPort,
        unit_of_work: UnitOfWorkPort,
        hasher: PasswordHasherPort,
    ) -> None:
        """Wire the service.

        Args:
            users: Account storage. Must flush only and never commit.
            unit_of_work: Transaction that the repository's writes belong to.
            hasher: Password hashing.
        """
        self._users = users
        self._unit_of_work = unit_of_work
        self._hasher = hasher

    def register(self, command: RegisterUserCommand) -> UserDTO:
        """Create an active account and commit.

        Args:
            command: Email, plain-text password and optional profile fields.
                The email must already be in the form accounts are stored and
                looked up by.

        Returns:
            The new account without credentials.

        Raises:
            ConflictError: The email or the username is already in use, whether
                the availability check or a concurrent registration found it. The
                message does not say which field collided; the cause goes into
                ``log_context``, which holds no email address.
            DomainValidationError: The password is longer than the hasher can use.
                The API schema rejects such passwords first.
        """
        if self._users.is_email_or_username_taken(command.email, command.username):
            raise _registration_conflict("existing_email_or_username")
        new_user = NewUser(
            email=command.email,
            password_hash=self._hash_password(command.password),
            username=command.username,
            first_name=command.first_name,
            last_name=command.last_name,
        )
        # A concurrent registration can slip past the availability check and
        # only the unique keys notice, when the row is flushed or committed. It
        # must look like the ordinary conflict.
        try:
            created = self._users.add(new_user)
            self._unit_of_work.commit()
        except ConflictError as error:
            raise _registration_conflict("unique_key_violation") from error
        return UserDTO.from_entity(created)

    def _hash_password(self, password: str) -> str:
        try:
            return self._hasher.hash(password)
        except ValueError as error:
            raise DomainValidationError(UNUSABLE_PASSWORD_MESSAGE) from error


def _registration_conflict(reason: str) -> ConflictError:
    return ConflictError(REGISTRATION_CONFLICT_MESSAGE, log_context={"reason": reason})
