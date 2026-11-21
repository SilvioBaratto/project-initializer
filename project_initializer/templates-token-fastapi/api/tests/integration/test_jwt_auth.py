"""Integration tests of the JWT login flow: register, token and the guarded route.

The tests drive the real application over the in-memory database with the real
JWT issuer and its key pinned in ``tests/auth_test_env.py``. Only the password
hasher is swapped for one at bcrypt's lowest cost, so the suite stays fast.
"""

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from jose import jwt
from pydantic import SecretStr
from sqlalchemy import select

from app.api.auth_deps import (
    LOGIN_UNAVAILABLE_MESSAGE,
    TOKEN_URL,
    get_access_token_issuer,
    get_password_hasher,
)
from app.api.bearer import MAX_BEARER_TOKEN_LENGTH
from app.application.services.auth_service import INVALID_LOGIN_MESSAGE
from app.application.services.registration import (
    REGISTRATION_CONFLICT_MESSAGE,
)
from app.domain.constants import PASSWORD_MAX_BYTES, PASSWORD_MIN_LENGTH
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.audit import AUDIT_LOGGER_NAME
from app.infrastructure.orm.user import UserRecord
from app.infrastructure.repositories.user import SqlAlchemyUserRepository
from app.infrastructure.security import BcryptPasswordHasher, JwtAccessTokenIssuer
from app.infrastructure.settings import settings
from app.main import app
from tests.audit_records import audit_records
from tests.auth_assertions import assert_authentication_failure
from tests.auth_test_env import (
    TEST_ACCESS_TOKEN_EXPIRE_MINUTES,
    TEST_AUTH_TOKEN,
    TEST_JWT_ALGORITHM,
    TEST_JWT_SECRET_KEY,
)

pytestmark = pytest.mark.integration

FAST_BCRYPT_ROUNDS = 4
# The literal is the contract: raising the cost is a decision, not a side effect.
DEFAULT_COST_HASH_PREFIX = "$2b$12$"
SECONDS_PER_MINUTE = 60
EMAIL = "jwt-user@example.com"
MIXED_CASE_EMAIL = "JWT-User@Example.COM"
USERNAME = "jwtuser"
PASSWORD = "strongpassword"
OTHER_EMAIL = "other-user@example.com"
INVALID_SALT_HASH = "$2b$04$" + "/" * 53
BLANK_USERNAMES = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
]
FAR_FUTURE_EPOCH = 4_102_444_800
ITEM_BODY = {"name": "Widget", "price": 1.0}
AUDIT_REGISTER_ACTION = "user.register"
AUDIT_LOGIN_ACTION = "user.login"

NON_BEARER_HEADERS = [
    pytest.param(None, id="header-missing"),
    pytest.param("Basic dXNlcjpwYXNz", id="other-scheme"),
    pytest.param("Bearer", id="scheme-only"),
    pytest.param("Bearer ", id="empty-token"),
    pytest.param("Bearer not-a-jwt", id="not-a-jwt"),
    pytest.param("Bearer é.é.é".encode(), id="non-ascii-token"),
    pytest.param("Bearer " + "a" * (MAX_BEARER_TOKEN_LENGTH + 1), id="token-too-long"),
]
SHORT_OR_LONG_PASSWORDS = [
    pytest.param("p" * (PASSWORD_MIN_LENGTH - 1), id="below-the-minimum"),
    pytest.param("p" * (PASSWORD_MAX_BYTES + 1), id="one-byte-over-the-maximum"),
    pytest.param("é" * (PASSWORD_MAX_BYTES // 2 + 1), id="multi-byte-over-the-maximum"),
    pytest.param("p" * 5000, id="very-long"),
]


@pytest.fixture(autouse=True)
def fast_password_hasher(client) -> None:
    """Swap in a low-cost hasher.

    It requests ``client`` so the override is set after that fixture's setup and
    is cleared together with the others when the client tears down.
    """
    hasher = BcryptPasswordHasher(rounds=FAST_BCRYPT_ROUNDS)
    app.dependency_overrides[get_password_hasher] = lambda: hasher


@pytest.fixture
def register_url(api_prefix: str) -> str:
    """URL of the registration route."""
    return f"{api_prefix}/auth/register"


@pytest.fixture
def token_url(api_prefix: str) -> str:
    """URL of the login route."""
    return f"{api_prefix}/auth/token"


@pytest.fixture
def me_jwt_url(api_prefix: str) -> str:
    """URL of the JWT-guarded current-user route."""
    return f"{api_prefix}/auth/me/jwt"


@pytest.fixture
def register(client, register_url):
    """Register an account through the API; keyword arguments override the body."""

    def send(**overrides):
        """POST a registration body with ``overrides`` applied."""
        body = {
            "email": EMAIL,
            "password": PASSWORD,
            "username": USERNAME,
            **overrides,
        }
        return client.post(register_url, json=body)

    return send


@pytest.fixture
def log_in(client, token_url):
    """Log in through the OAuth2 form; the default account is the registered one."""

    def send(email: str = EMAIL, password: str = PASSWORD):
        """POST the login form."""
        return client.post(token_url, data={"username": email, "password": password})

    return send


@pytest.fixture
def access_token(register, log_in) -> str:
    """A valid access token for a freshly registered account."""
    assert register().status_code == HTTPStatus.CREATED
    return log_in().json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    """Authorization header carrying ``token``."""
    return {"Authorization": f"Bearer {token}"}


def forge_token(
    claims: dict[str, object], *, algorithm: str = TEST_JWT_ALGORITHM
) -> str:
    """Sign claims with the test key, bypassing every rule of the issuer."""
    return jwt.encode(claims, TEST_JWT_SECRET_KEY, algorithm=algorithm)


def valid_claims(subject: str, **overrides: object) -> dict[str, object]:
    """Claims the issuer would accept for ``subject``, with ``overrides`` applied."""
    claims: dict[str, object] = {
        "sub": subject,
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return {**claims, **overrides}


def url_safe_json(document: dict[str, object]) -> str:
    """Encode a JSON document the way a JWT segment is encoded."""
    raw = json.dumps(document).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def account_id(db_session, email: str = EMAIL) -> str:
    """Id of the stored account with ``email``."""
    return db_session.scalar(select(UserRecord.id).where(UserRecord.email == email))


@pytest.fixture
def jwt_secret_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the test with an empty ``JWT_SECRET_KEY``, as a fresh checkout has.

    The issuer dependency is cached once it builds, so the cache is cleared to
    make the empty key take effect. A failed build is never cached, so nothing
    from this test outlives the patch.
    """
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr(""))
    get_access_token_issuer.cache_clear()


def test_when_a_new_user_registers_then_201_with_the_public_user_and_no_credentials(
    register,
):
    """when a new user registers, 201 returns the public fields and no credential.

    Validates app.api.v1.endpoints.auth.register().
    """
    response = register(first_name="Jane", last_name="Doe")

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["email"] == EMAIL
    assert body["username"] == USERNAME
    assert body["is_active"] is True
    assert body["id"]
    assert "password" not in body
    assert "password_hash" not in body


def test_when_the_email_is_registered_twice_then_409_with_a_generic_message(register):
    """when an email is registered twice, the second attempt answers 409.

    Validates app.api.v1.endpoints.auth.register().
    """
    register()

    response = register(username="another")

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["error"]["code"] == "CONFLICT"
    assert response.json()["error"]["message"] == REGISTRATION_CONFLICT_MESSAGE


def test_when_the_same_email_differs_only_in_case_then_registration_conflicts(register):
    """when an email is registered again in another case, the answer is 409.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    register()

    response = register(email=MIXED_CASE_EMAIL, username="another")

    assert response.status_code == HTTPStatus.CONFLICT


def test_when_the_email_has_capitals_then_it_is_stored_and_found_in_lower_case(
    register, log_in, db_session
):
    """when an account registers as Jane@Example.COM, it is kept as jane@example.com.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    response = register(email=MIXED_CASE_EMAIL)

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["email"] == EMAIL
    assert db_session.scalar(select(UserRecord.email)) == EMAIL
    assert log_in(email=MIXED_CASE_EMAIL).status_code == HTTPStatus.OK
    assert log_in(email=EMAIL).status_code == HTTPStatus.OK


@pytest.mark.parametrize("field", ["username", "email"])
def test_when_the_unique_key_trips_at_flush_then_409_and_the_session_stays_usable(
    register, log_in, monkeypatch, field
):
    """when the unique key rejects a row the availability check missed, 409 answers.

    The availability check is blinded, as it is for a request that ran just
    before the competing commit. The real repository then meets the constraint
    at flush time.

    Validates app.infrastructure.repositories.user.SqlAlchemyUserRepository.add().
    """
    assert register().status_code == HTTPStatus.CREATED
    monkeypatch.setattr(
        SqlAlchemyUserRepository, "is_email_or_username_taken", lambda *_: False
    )
    colliding = {"email": OTHER_EMAIL} if field == "username" else {"username": "x"}

    response = register(**colliding)

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["error"]["message"] == REGISTRATION_CONFLICT_MESSAGE
    assert log_in().status_code == HTTPStatus.OK


def test_when_the_username_is_registered_twice_then_409_with_the_same_message(register):
    """when a username is reused with a new email, the answer is the same 409.

    The two duplicate cases look the same, so the answer does not say which
    field collided.

    Validates app.api.v1.endpoints.auth.register().
    """
    register()
    duplicate_email = register(username="another")

    duplicate_username = register(email=OTHER_EMAIL)

    assert duplicate_username.status_code == HTTPStatus.CONFLICT
    assert (
        duplicate_username.json()["error"]["message"]
        == (duplicate_email.json()["error"]["message"])
    )


def test_when_accounts_have_no_username_then_they_do_not_conflict(register):
    """when two accounts omit the username, both register.

    Validates app.api.v1.endpoints.auth.register().
    """
    first = register(username=None)
    second = register(username=None, email=OTHER_EMAIL)

    assert (first.status_code, second.status_code) == (
        HTTPStatus.CREATED,
        HTTPStatus.CREATED,
    )


@pytest.mark.parametrize("blank", BLANK_USERNAMES)
def test_when_two_accounts_register_with_a_blank_username_then_both_succeed_without_one(
    register, db_session, blank
):
    """when two registrations send an empty username, neither claims it.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    first = register(username=blank)
    second = register(username=blank, email=OTHER_EMAIL)

    assert (first.status_code, second.status_code) == (
        HTTPStatus.CREATED,
        HTTPStatus.CREATED,
    )
    assert db_session.scalars(select(UserRecord.username)).all() == [None, None]


def test_when_the_client_sends_privileged_fields_then_they_are_ignored(
    register, log_in, db_session
):
    """when the body carries privileged fields, the account is still created plain.

    Validates app.api.schemas.user.UserCreate.
    """
    response = register(is_active=False, is_superuser=True, is_verified=True)

    record = db_session.scalar(select(UserRecord).where(UserRecord.email == EMAIL))
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["is_active"] is True
    assert (record.is_active, record.is_superuser, record.is_verified) == (
        True,
        False,
        False,
    )
    assert log_in().status_code == HTTPStatus.OK


def test_when_the_password_is_stored_then_only_a_bcrypt_hash_is_kept(
    register, db_session
):
    """when an account registers, the database holds a hash and never the password.

    Validates app.application.services.auth_service.AuthService.register().
    """
    register()

    stored = db_session.scalar(
        select(UserRecord.password_hash).where(UserRecord.email == EMAIL)
    )

    assert stored.startswith("$2b$")
    assert PASSWORD not in stored


@pytest.mark.parametrize("password", SHORT_OR_LONG_PASSWORDS)
def test_when_the_password_is_out_of_bounds_then_registration_answers_422(
    register, password
):
    """when the password is too short or longer than bcrypt can use, the answer is 422.

    Validates app.api.schemas.user.UserCreate.
    """
    response = register(password=password)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert password not in response.text


@pytest.mark.parametrize("field", ["username", "first_name", "last_name"])
def test_when_a_text_field_holds_a_nul_character_then_registration_answers_422(
    register, field
):
    """when username, first_name or last_name holds NUL, registration answers 422.

    Validates app.api.schemas.auth.RegistrationRequest.
    """
    response = register(**{field: "a\x00b"})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_when_the_password_has_the_maximum_bytes_then_it_registers_and_logs_in(
    register, log_in
):
    """when the password is exactly 72 bytes, registration and login both work.

    Validates app.api.schemas.user.UserCreate.
    """
    password = "p" * PASSWORD_MAX_BYTES

    assert register(password=password).status_code == HTTPStatus.CREATED
    assert log_in(password=password).status_code == HTTPStatus.OK


def test_when_the_email_is_invalid_then_registration_answers_422(register):
    """when the email is malformed, registration answers 422.

    Validates app.api.schemas.user.UserCreate.
    """
    assert register(email="not-an-email").status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_when_a_registered_user_logs_in_then_a_bearer_token_is_returned(
    register, log_in
):
    """when the right credentials are posted, an access token of type bearer returns.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()

    response = log_in()

    assert response.status_code == HTTPStatus.OK
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_when_a_token_is_issued_then_it_carries_exp_sub_and_the_configured_lifetime(
    access_token, db_session
):
    """when a login succeeds, the JWT carries the account id as sub and a future exp.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.issue().
    """
    claims = jwt.get_unverified_claims(access_token)

    assert claims["sub"] == account_id(db_session)
    assert claims["exp"] - claims["iat"] == (
        TEST_ACCESS_TOKEN_EXPIRE_MINUTES * SECONDS_PER_MINUTE
    )
    assert claims["exp"] > datetime.now(UTC).timestamp()


def test_when_the_password_is_wrong_then_login_answers_401_with_the_generic_message(
    register, log_in
):
    """when the password is wrong, login answers 401 with the bearer challenge.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()

    response = log_in(password="wrong-password")

    assert_authentication_failure(response)
    assert response.json()["error"]["message"] == INVALID_LOGIN_MESSAGE


def test_when_the_email_is_unknown_then_login_answers_exactly_like_a_wrong_password(
    register, log_in
):
    """when the email is unknown, the 401 matches the one for a wrong password.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()
    wrong_password = log_in(password="wrong-password").json()["error"]

    unknown_email = log_in(email="nobody@example.com")

    assert_authentication_failure(unknown_email)
    assert unknown_email.json()["error"]["message"] == wrong_password["message"]
    assert unknown_email.json()["error"]["code"] == wrong_password["code"]


def test_when_the_account_is_inactive_then_login_answers_the_generic_401(
    register, log_in, db_session
):
    """when the account is inactive, login answers the same generic 401.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    register()
    db_session.scalar(
        select(UserRecord).where(UserRecord.email == EMAIL)
    ).is_active = False
    db_session.flush()

    response = log_in()

    assert_authentication_failure(response)
    assert response.json()["error"]["message"] == INVALID_LOGIN_MESSAGE


def test_when_the_stored_hash_is_missing_then_login_answers_401_not_500(
    log_in, db_session
):
    """when an account has no password hash, login answers 401 instead of failing.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    db_session.add(UserRecord(email=EMAIL, password_hash=None))
    db_session.flush()

    assert_authentication_failure(log_in())


def test_when_the_stored_hash_is_corrupt_then_login_answers_401_not_500(
    log_in, db_session
):
    """when the stored hash is not a bcrypt hash, login answers 401 instead of failing.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    db_session.add(UserRecord(email=EMAIL, password_hash="$2b$12$truncated"))
    db_session.flush()

    assert_authentication_failure(log_in())


def test_when_the_stored_hash_has_an_invalid_salt_then_login_answers_401_not_500(
    log_in, db_session
):
    """when a hash has a salt bcrypt refuses, login answers 401 instead of failing.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    db_session.add(UserRecord(email=EMAIL, password_hash=INVALID_SALT_HASH))
    db_session.flush()

    assert_authentication_failure(log_in())


@pytest.mark.parametrize(
    "form",
    [
        pytest.param(
            {"username": "u" * 5000, "password": PASSWORD}, id="long-username"
        ),
        pytest.param({"username": EMAIL, "password": "p" * 5000}, id="long-password"),
        pytest.param(
            {"username": EMAIL, "password": "p" * (PASSWORD_MAX_BYTES + 1)},
            id="password-over-the-maximum",
        ),
        pytest.param({"username": "", "password": PASSWORD}, id="empty-username"),
        pytest.param({"username": EMAIL, "password": ""}, id="empty-password"),
        pytest.param({"username": EMAIL}, id="password-missing"),
        pytest.param({"password": PASSWORD}, id="username-missing"),
        pytest.param(
            {"username": "a\x00b@example.com", "password": PASSWORD},
            id="nul-in-username",
        ),
    ],
)
def test_when_the_login_form_is_out_of_bounds_then_422_not_500(client, token_url, form):
    """when a login field is empty, missing, oversized or holds NUL, the answer is 422.

    Validates app.api.schemas.auth.LoginForm.
    """
    response = client.post(token_url, data=form)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert set(response.json()) == {"error"}


def test_when_the_password_is_longer_than_72_bytes_but_not_72_characters_then_401(
    register, log_in
):
    """when a short-looking password has more than 72 bytes, login answers 401.

    Validates app.infrastructure.security.BcryptPasswordHasher.verify().
    """
    register()

    response = log_in(password="é" * (PASSWORD_MAX_BYTES // 2 + 1))

    assert_authentication_failure(response)


def test_when_login_fails_then_the_log_holds_a_reason_and_no_email(
    register, log_in, caplog
):
    """when a login fails, the log record has a reason code and no email address.

    Validates app.application.services.auth_service.AuthService.authenticate().
    """
    register()

    with caplog.at_level(logging.INFO):
        log_in(password="wrong-password")

    domain_errors = [
        r for r in caplog.records if r.getMessage() == "request.domain_error"
    ]
    assert [r.context for r in domain_errors] == [{"reason": "invalid_credentials"}]
    assert EMAIL not in caplog.text
    assert "wrong-password" not in caplog.text


def test_when_a_user_registers_then_one_audit_record_names_the_new_account(
    register, caplog
):
    """when registration succeeds, an audit record has the new id as resource and actor.

    Validates app.api.v1.endpoints.auth.register().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        response = register()

    (record,) = audit_records(caplog)
    assert record.action == AUDIT_REGISTER_ACTION
    assert record.resource_id == response.json()["id"]
    assert record.actor_id == response.json()["id"]


def test_when_registration_is_refused_then_nothing_is_audited(register, caplog):
    """when registration answers 409, no audit record is written.

    Validates app.api.v1.endpoints.auth.register().
    """
    register()
    caplog.clear()

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        response = register(username="another")

    assert response.status_code == HTTPStatus.CONFLICT
    assert audit_records(caplog) == []


def test_when_a_user_logs_in_then_one_audit_record_names_the_account(
    register, log_in, db_session, caplog
):
    """when a login succeeds, an audit record has the account id as resource and actor.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()
    caplog.clear()

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        response = log_in()

    (record,) = audit_records(caplog)
    assert response.status_code == HTTPStatus.OK
    assert record.action == AUDIT_LOGIN_ACTION
    assert record.resource_id == account_id(db_session)
    assert record.actor_id == account_id(db_session)


def test_when_a_login_fails_then_nothing_is_audited(register, log_in, caplog):
    """when a login answers 401, no audit record is written.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()
    caplog.clear()

    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        response = log_in(password="wrong-password")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert audit_records(caplog) == []


def test_when_registration_and_login_are_audited_then_no_record_holds_personal_data(
    register, log_in, caplog
):
    """when the audit trail is written, it never carries the email or the username.

    Validates app.api.v1.endpoints.auth.register().
    """
    with caplog.at_level(logging.INFO, logger=AUDIT_LOGGER_NAME):
        register()
        log_in()

    records = audit_records(caplog)
    assert [record.action for record in records] == [
        AUDIT_REGISTER_ACTION,
        AUDIT_LOGIN_ACTION,
    ]
    for record in records:
        rendered = f"{record.getMessage()} {vars(record)}".lower()
        assert EMAIL.lower() not in rendered
        assert USERNAME not in rendered


def test_when_a_valid_token_is_sent_then_me_jwt_returns_the_account(
    access_token, client, me_jwt_url, db_session
):
    """when the minted token is sent, /auth/me/jwt returns the principal of the account.

    Validates app.api.v1.endpoints.auth.read_current_jwt_user().
    """
    response = client.get(me_jwt_url, headers=bearer(access_token))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": account_id(db_session),
        "email": EMAIL,
        "username": USERNAME,
        "roles": [],
        "auth_method": "jwt",
    }


@pytest.mark.parametrize("authorization", NON_BEARER_HEADERS)
def test_when_the_authorization_header_is_unusable_then_me_jwt_answers_401(
    client, me_jwt_url, authorization
):
    """when the header is missing or malformed, /auth/me/jwt answers 401.

    Validates app.api.auth_deps.get_current_jwt_user().
    """
    headers = {} if authorization is None else {"Authorization": authorization}

    assert_authentication_failure(client.get(me_jwt_url, headers=headers))


def test_when_the_token_is_expired_then_me_jwt_answers_401(
    register, db_session, client, me_jwt_url
):
    """when the token's lifetime has passed, /auth/me/jwt answers 401.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    register()
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    stale_issuer = JwtAccessTokenIssuer(
        SecretStr(TEST_JWT_SECRET_KEY),
        TEST_JWT_ALGORITHM,
        TEST_ACCESS_TOKEN_EXPIRE_MINUTES,
        clock=lambda: long_ago,
    )

    response = client.get(
        me_jwt_url, headers=bearer(stale_issuer.issue(account_id(db_session)))
    )

    assert_authentication_failure(response)


def test_when_the_token_is_rejected_by_the_verifier_then_me_jwt_answers_401(
    register, db_session, client, me_jwt_url
):
    """when a token breaks a key, algorithm or claim rule, /auth/me/jwt answers 401.

    Validates app.infrastructure.security.JwtAccessTokenIssuer.subject_of().
    """
    register()
    subject = account_id(db_session)
    without_subject = valid_claims(subject)
    del without_subject["sub"]
    without_expiry = valid_claims(subject)
    del without_expiry["exp"]
    unsigned = (
        f"{url_safe_json({'alg': 'none', 'typ': 'JWT'})}."
        f"{url_safe_json({'sub': subject, 'exp': FAR_FUTURE_EPOCH})}."
    )
    rejected_tokens = {
        "other-key": jwt.encode(valid_claims(subject), "x" * 40, algorithm="HS256"),
        "other-algorithm": forge_token(valid_claims(subject), algorithm="HS512"),
        "no-subject": forge_token(without_subject),
        "no-expiry": forge_token(without_expiry),
        "numeric-subject": forge_token(valid_claims(subject, sub=7)),
        "unknown-subject": forge_token(valid_claims("no-such-account")),
        "unsigned": unsigned,
    }

    statuses = {
        name: client.get(me_jwt_url, headers=bearer(token)).status_code
        for name, token in rejected_tokens.items()
    }

    assert statuses == dict.fromkeys(rejected_tokens, HTTPStatus.UNAUTHORIZED)


def test_when_the_account_is_deactivated_after_login_then_the_token_stops_working(
    access_token, me_jwt_url, client, db_session
):
    """when an account is deactivated, its still-valid token is refused at once.

    Validates app.application.services.auth_service.AuthService.resolve_access_token().
    """
    assert client.get(me_jwt_url, headers=bearer(access_token)).status_code == (
        HTTPStatus.OK
    )
    db_session.scalar(
        select(UserRecord).where(UserRecord.email == EMAIL)
    ).is_active = False
    db_session.flush()

    assert_authentication_failure(client.get(me_jwt_url, headers=bearer(access_token)))


def test_when_the_static_token_is_sent_to_the_jwt_route_then_401(client, me_jwt_url):
    """when the shared static token is sent to /auth/me/jwt, it is refused.

    Validates app.api.auth_deps.get_current_jwt_user().
    """
    assert_authentication_failure(
        client.get(me_jwt_url, headers=bearer(TEST_AUTH_TOKEN))
    )


def test_when_a_jwt_is_sent_to_static_routes_then_they_answer_401(
    access_token, client, api_prefix
):
    """when a login JWT is sent to /auth/me or an item write, both refuse it.

    Item writes stay on the static token; a JWT never opens them.

    Validates app.api.auth_deps.get_current_user().
    """
    me = client.get(f"{api_prefix}/auth/me", headers=bearer(access_token))
    write = client.post(
        f"{api_prefix}/items", json=ITEM_BODY, headers=bearer(access_token)
    )

    assert_authentication_failure(me)
    assert_authentication_failure(write)


def test_when_the_hasher_dependency_is_built_then_it_hashes_at_the_default_cost():
    """when the password hasher dependency is built, its hashes carry the default cost.

    Validates app.api.auth_deps.get_password_hasher().
    """
    get_password_hasher.cache_clear()

    password_hash = get_password_hasher().hash("default-cost-password")

    assert password_hash.startswith(DEFAULT_COST_HASH_PREFIX)


def test_when_the_jwt_secret_is_empty_then_the_issuer_dependency_answers_unavailable(
    jwt_secret_unset,
):
    """when JWT_SECRET_KEY is empty, the issuer dependency raises a 503-class error.

    Validates app.api.auth_deps.get_access_token_issuer().
    """
    with pytest.raises(ExternalServiceError) as raised:
        get_access_token_issuer()

    assert raised.value.public_message == LOGIN_UNAVAILABLE_MESSAGE
    assert raised.value.log_context == {"reason": "jwt_secret_key_not_configured"}


def test_when_the_jwt_secret_is_empty_then_registration_still_works(
    jwt_secret_unset, register, db_session
):
    """when JWT_SECRET_KEY is empty, an account can still be registered.

    Validates app.api.auth_deps.get_registration_service().
    """
    response = register()

    assert response.status_code == HTTPStatus.CREATED
    assert db_session.scalar(select(UserRecord.email)) == EMAIL


@pytest.mark.parametrize("password", [PASSWORD, "wrong-password"])
def test_when_the_jwt_secret_is_empty_then_login_answers_503_for_any_password(
    jwt_secret_unset, register, log_in, password
):
    """when JWT_SECRET_KEY is empty, login answers 503 for right and wrong passwords.

    The status must not reveal whether the credentials were right.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()

    response = log_in(password=password)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["message"] == LOGIN_UNAVAILABLE_MESSAGE
    assert "Retry-After" in response.headers


def test_when_the_jwt_secret_is_empty_then_the_jwt_route_answers_503(
    jwt_secret_unset, client, me_jwt_url
):
    """when JWT_SECRET_KEY is empty, a bearer token reaching /auth/me/jwt gets 503.

    Validates app.api.v1.endpoints.auth.read_current_jwt_user().
    """
    response = client.get(me_jwt_url, headers=bearer("any-token"))

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json()["error"]["message"] == LOGIN_UNAVAILABLE_MESSAGE


def test_when_a_login_succeeds_then_the_token_response_is_not_cacheable(
    register, log_in
):
    """when a token is issued, the response forbids storing it.

    Validates app.api.v1.endpoints.auth.login().
    """
    register()

    response = log_in()

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"


def test_when_the_schema_is_read_then_the_token_url_follows_the_api_prefix(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, the OAuth2 token URL follows the API prefix.

    Validates app.api.auth_deps.TOKEN_URL.
    """
    scheme = openapi_schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]

    expected_url = f"{api_prefix.lstrip('/')}/auth/token"

    assert expected_url == TOKEN_URL
    assert scheme["flows"]["password"]["tokenUrl"] == TOKEN_URL


def test_when_the_schema_is_read_then_the_jwt_routes_are_documented(
    openapi_schema, api_prefix
):
    """when OpenAPI is generated, the JWT routes carry summaries and error responses.

    Validates app.api.v1.endpoints.auth.register().
    """
    paths = openapi_schema["paths"]
    register = paths[f"{api_prefix}/auth/register"]["post"]
    token = paths[f"{api_prefix}/auth/token"]["post"]
    me = paths[f"{api_prefix}/auth/me/jwt"]["get"]
    default_description = "Successful Response"

    assert register["summary"] == "Register a new user"
    assert token["summary"] == "Log in for an access token"
    assert me["summary"] == "Get the current JWT user"
    assert register["responses"]["201"]["description"] != default_description
    assert token["responses"]["200"]["description"] != default_description
    assert me["responses"]["200"]["description"] != default_description
    assert register["responses"]["409"]["description"]
    assert token["responses"]["401"]["description"]
    assert me["responses"]["401"]["description"]
