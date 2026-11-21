"""Unit tests for the registration use case, run against in-memory fakes."""

import pytest

from app.application.commands.user import RegisterUserCommand
from app.application.dto.user import UserDTO
from app.application.services.registration import (
    REGISTRATION_CONFLICT_MESSAGE,
    RegistrationService,
)
from app.domain.constants import PASSWORD_MAX_BYTES
from app.domain.entities.user import NewUser, User
from app.domain.exceptions import ConflictError, DomainValidationError
from tests.auth_fakes import (
    EMAIL,
    HASH_PREFIX,
    PASSWORD,
    FakePasswordHasher,
    FakeUserRepository,
    make_user,
)
from tests.fakes import FakeUnitOfWork

pytestmark = pytest.mark.unit

OTHER_EMAIL = "john.roe@example.com"


class CollidingUnitOfWork(FakeUnitOfWork):
    """Unit of work whose commit loses a race against a concurrent registration."""

    def commit(self) -> None:
        """Raise like a real adapter that met a unique-key violation."""
        raise ConflictError()


class CollidingUserRepository(FakeUserRepository):
    """Repository whose flush loses a race against a concurrent registration."""

    def add(self, new_user: NewUser) -> User:
        """Raise like a real repository whose flush met a unique-key violation."""
        raise ConflictError(log_context={"error_type": "IntegrityError"})


def make_command(**overrides: object) -> RegisterUserCommand:
    """Build a registration for a new account."""
    defaults: dict[str, object] = {
        "email": OTHER_EMAIL,
        "password": PASSWORD,
        "username": "john",
        "first_name": "John",
        "last_name": "Roe",
    }
    return RegisterUserCommand(**{**defaults, **overrides})


@pytest.fixture
def users() -> FakeUserRepository:
    """Repository that already holds one active account."""
    return FakeUserRepository([make_user()])


@pytest.fixture
def unit_of_work() -> FakeUnitOfWork:
    """Unit of work whose commits the test can count."""
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    """Hasher that records every verification."""
    return FakePasswordHasher()


@pytest.fixture
def service(users, unit_of_work, hasher) -> RegistrationService:
    """Service wired to the fakes."""
    return RegistrationService(users, unit_of_work, hasher)


def test_when_a_new_account_registers_then_it_is_stored_hashed_and_committed(
    service, users, unit_of_work
):
    """when an unused email and username register, the account is stored and committed.

    Validates app.application.services.registration.RegistrationService.register().
    """
    created = service.register(make_command())

    assert isinstance(created, UserDTO)
    assert (created.email, created.username, created.is_active) == (
        OTHER_EMAIL,
        "john",
        True,
    )
    assert users.added[0].password_hash == f"{HASH_PREFIX}{PASSWORD}"
    assert unit_of_work.commits == 1


def test_when_an_account_registers_then_the_result_carries_no_credentials(service):
    """when registration succeeds, the DTO has no password or hash field.

    Validates app.application.dto.user.UserDTO.from_entity().
    """
    created = service.register(make_command())

    assert not hasattr(created, "password_hash")
    assert not hasattr(created, "password")
    assert PASSWORD not in repr(created)


def test_when_a_username_is_missing_then_two_accounts_can_still_register(service):
    """when two registrations omit the username, they do not conflict.

    Validates app.application.services.registration.RegistrationService.register().
    """
    service.register(make_command(username=None))

    second = service.register(make_command(email="third@example.com", username=None))

    assert second.username is None


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"email": EMAIL}, id="email-taken"),
        pytest.param({"username": "jane"}, id="username-taken"),
        pytest.param({"email": EMAIL, "username": "jane"}, id="both-taken"),
    ],
)
def test_when_the_email_or_username_is_taken_then_registration_conflicts_generically(
    service, users, unit_of_work, overrides
):
    """when the email or the username exists, one generic conflict is raised.

    The message is the same for every cause, so it does not say which field
    collided.

    Validates app.application.services.registration.RegistrationService.register().
    """
    with pytest.raises(ConflictError) as raised:
        service.register(make_command(**overrides))

    assert raised.value.public_message == REGISTRATION_CONFLICT_MESSAGE
    assert raised.value.log_context == {"reason": "existing_email_or_username"}
    assert users.added == []
    assert unit_of_work.commits == 0


def test_when_a_conflict_is_raised_then_the_log_context_holds_no_personal_data(service):
    """when registration conflicts, the log context names no email or username.

    Validates app.application.services.registration.RegistrationService.register().
    """
    with pytest.raises(ConflictError) as raised:
        service.register(make_command(email=EMAIL, username="jane"))

    logged = str(raised.value.log_context)
    assert EMAIL not in logged
    assert "jane" not in logged


def test_when_a_concurrent_registration_wins_at_commit_then_the_generic_conflict_rises(
    users, hasher
):
    """when the commit meets a unique-key violation, the ordinary conflict is raised.

    Validates app.application.services.registration.RegistrationService.register().
    """
    racing = RegistrationService(users, CollidingUnitOfWork(), hasher)

    with pytest.raises(ConflictError) as raised:
        racing.register(make_command())

    assert raised.value.public_message == REGISTRATION_CONFLICT_MESSAGE
    assert raised.value.log_context == {"reason": "unique_key_violation"}


def test_when_a_concurrent_registration_wins_at_add_then_the_generic_conflict_rises(
    unit_of_work, hasher
):
    """when the repository's flush meets a unique-key violation, the conflict rises.

    The repository flushes inside ``add``, so the race surfaces there before any
    commit is attempted.

    Validates app.application.services.registration.RegistrationService.register().
    """
    racing = RegistrationService(CollidingUserRepository(), unit_of_work, hasher)

    with pytest.raises(ConflictError) as raised:
        racing.register(make_command())

    assert raised.value.public_message == REGISTRATION_CONFLICT_MESSAGE
    assert raised.value.log_context == {"reason": "unique_key_violation"}
    assert unit_of_work.commits == 0


def test_when_the_hasher_refuses_the_password_then_a_validation_error_is_raised(
    service, users
):
    """when the password cannot be hashed, a domain validation error is raised.

    Validates app.application.services.registration.RegistrationService.register().
    """
    too_long = "a" * (PASSWORD_MAX_BYTES + 1)

    with pytest.raises(DomainValidationError):
        service.register(make_command(password=too_long))

    assert users.added == []


def test_when_the_command_is_printed_then_the_password_is_hidden():
    """when a registration command is rendered as text, the password is not in it.

    Validates app.application.commands.user.RegisterUserCommand.
    """
    assert PASSWORD not in repr(make_command())
