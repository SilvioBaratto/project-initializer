"""Unit tests of the Entra token verifier: rejections, scope, principal and wiring.

Real RS256 tokens, signed by a key the tests generate, go through the real
verifier and the real cooldown resolver. Only the key source is a stub, so no
tenant and no network are involved.
"""

import time
from collections.abc import Callable
from functools import partial

import pytest

from app.domain.exceptions import AuthenticationError, AuthorizationError
from app.infrastructure.auth import entra as entra_module
from app.infrastructure.auth.entra import EntraTokenVerifier, expected_audiences
from app.infrastructure.auth.entra_jwks import CooldownSigningKeyResolver
from app.infrastructure.auth_settings import AuthSettings
from tests.auth_test_env import AUTH_TEST_ENV, TEST_API_CLIENT_ID, TEST_TENANT_ID
from tests.entra_tokens import (
    AUTHORITY,
    OBJECT_ID,
    SCOPE_NAME,
    USER_EMAIL,
    USERNAME,
    StubKeySource,
    build_verifier,
    forge_hmac_token,
    forge_token_with_header,
    forge_unsigned_token,
    make_token,
    sign_token,
    tenant_key_source,
    tenant_signing_key,
    unpublished_signing_key,
    valid_claims,
)

pytestmark = pytest.mark.unit

API_AUDIENCE = f"api://{TEST_API_CLIENT_ID}"
PAST_ISSUED_AT = 1_700_000_000
PAST_EXPIRY = PAST_ISSUED_AT + 3600
FUTURE_OFFSET_SECONDS = 3600
SKEW_MARGIN_SECONDS = 5
# The tolerance the API promises, spelled out so a change to the constant is noticed.
PROMISED_LEEWAY_SECONDS = 30
OTHER_TENANT_ID = "0f9e8d7c-6b5a-4c3d-8e2f-1a0b9c8d7e6f"
SUBJECT_ID = "subject-without-oid"
KEY_TIMEOUT_SECONDS = 2.5
KEY_COOLDOWN_SECONDS = 12.5
DISALLOWED_ALGORITHMS = ["RS384", "RS512", "PS256"]


@pytest.fixture(autouse=True)
def unset_entra_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hide every Entra variable, so settings built here start from the defaults."""
    for name in {
        *AUTH_TEST_ENV,
        *(field.upper() for field in AuthSettings.model_fields),
    }:
        monkeypatch.delenv(name, raising=False)


def forged_unsigned() -> str:
    """Token that declares ``alg: none``."""
    return forge_unsigned_token(valid_claims())


def forged_hmac() -> str:
    """Token signed with HS256 using the public key as secret."""
    return forge_hmac_token(valid_claims(), tenant_signing_key())


def rotated_kid() -> str:
    """Token whose key id the tenant does not publish."""
    return sign_token(valid_claims(), tenant_signing_key(), kid="rotated-away")


def other_signer() -> str:
    """Token signed by a key the tenant never published, under the published id."""
    return sign_token(valid_claims(), unpublished_signing_key())


def not_a_jwt() -> str:
    """Token that is not three base64 segments."""
    return "not-a-jwt"


def seconds_from_now(offset: int) -> int:
    """Epoch second ``offset`` seconds away from the present."""
    return int(time.time()) + offset


REJECTIONS = [
    pytest.param(
        partial(make_token, iat=PAST_ISSUED_AT, exp=PAST_EXPIRY),
        "expired",
        id="expired",
    ),
    pytest.param(
        lambda: make_token(
            iat=seconds_from_now(FUTURE_OFFSET_SECONDS),
            exp=seconds_from_now(2 * FUTURE_OFFSET_SECONDS),
        ),
        "not_yet_valid",
        id="issued-in-the-future",
    ),
    pytest.param(
        lambda: make_token(nbf=seconds_from_now(FUTURE_OFFSET_SECONDS)),
        "not_yet_valid",
        id="not-before-in-the-future",
    ),
    pytest.param(
        partial(make_token, iss=f"{AUTHORITY}/{OTHER_TENANT_ID}/v2.0"),
        "wrong_issuer",
        id="wrong-issuer",
    ),
    pytest.param(
        partial(make_token, aud="api://someone-else"),
        "wrong_audience",
        id="wrong-audience",
    ),
    pytest.param(partial(make_token, exp=None), "missing_claim", id="no-exp"),
    pytest.param(partial(make_token, iat=None), "missing_claim", id="no-iat"),
    pytest.param(partial(make_token, iss=None), "missing_claim", id="no-iss"),
    pytest.param(partial(make_token, aud=None), "missing_claim", id="no-aud"),
    pytest.param(
        partial(make_token, tid=OTHER_TENANT_ID), "wrong_tenant", id="wrong-tenant"
    ),
    pytest.param(partial(make_token, tid=None), "wrong_tenant", id="no-tenant"),
    pytest.param(
        partial(make_token, oid=None, sub=None),
        "missing_subject",
        id="no-oid-and-no-sub",
    ),
    pytest.param(forged_unsigned, "disallowed_algorithm", id="alg-none"),
    pytest.param(forged_hmac, "disallowed_algorithm", id="hs256-key-confusion"),
    pytest.param(rotated_kid, "unknown_signing_key", id="unknown-kid"),
    pytest.param(other_signer, "bad_signature", id="bad-signature"),
    pytest.param(not_a_jwt, "malformed_token", id="malformed"),
]
MISSING_SCOPES = [
    pytest.param(None, id="no-scp-claim"),
    pytest.param("other_scope", id="other-scope"),
    pytest.param("access_as_user_extra", id="scope-that-only-starts-the-same"),
    pytest.param(["access_as_user"], id="scp-not-a-string"),
    pytest.param("", id="empty-scp"),
]
ACCEPTED_SCOPE_CLAIMS = [
    pytest.param("access_as_user", id="only-scope"),
    pytest.param("profile access_as_user offline", id="among-others"),
]
SCOPE_CONFIGURATIONS = [
    pytest.param("access_as_user", id="bare-name"),
    pytest.param(f"{API_AUDIENCE}/access_as_user", id="full-uri"),
    pytest.param(f"  {API_AUDIENCE}/access_as_user ", id="full-uri-with-spaces"),
]
ACCEPTED_AUDIENCES = [
    pytest.param(TEST_API_CLIENT_ID, id="bare-client-id"),
    pytest.param(API_AUDIENCE, id="api-uri"),
    pytest.param([API_AUDIENCE, "another"], id="list-with-an-accepted-value"),
]


def verify_with(token: str, **verifier_overrides: object):
    """Verify ``token`` with a verifier for the test tenant."""
    return build_verifier(**verifier_overrides).verify(token)


@pytest.mark.parametrize(("build_token", "reason"), REJECTIONS)
def test_when_a_token_is_invalid_then_authentication_fails_with_the_reason(
    build_token: Callable[[], str], reason: str
):
    """when any check fails, AuthenticationError carries only the reason code.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    with pytest.raises(AuthenticationError) as raised:
        verify_with(build_token())

    assert raised.value.log_context["reason"] == reason
    assert raised.value.public_message == AuthenticationError.default_message
    assert reason not in raised.value.public_message
    assert USERNAME not in repr(raised.value.log_context)


@pytest.mark.parametrize(
    ("overrides", "expected_context"),
    [
        pytest.param(
            {"tid": OTHER_TENANT_ID},
            {"reason": "wrong_tenant", "oid": OBJECT_ID, "tid": OTHER_TENANT_ID},
            id="wrong-tenant",
        ),
        pytest.param(
            {"oid": None, "sub": None},
            {"reason": "missing_subject", "oid": None, "tid": TEST_TENANT_ID},
            id="no-subject",
        ),
    ],
)
def test_when_the_signature_holds_but_identity_fails_then_the_verified_ids_are_logged(
    overrides: dict[str, object], expected_context: dict[str, object]
):
    """when a signed token fails an identity check, the log context names its ids.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    with pytest.raises(AuthenticationError) as raised:
        verify_with(make_token(**overrides))

    assert raised.value.log_context == expected_context


@pytest.mark.parametrize(
    "header",
    [
        pytest.param({"alg": "RS256"}, id="no-kid"),
        pytest.param({"alg": "RS256", "kid": ""}, id="kid-is-empty"),
        pytest.param({"alg": "RS256", "kid": 7}, id="kid-is-a-number"),
        pytest.param({"alg": "RS256", "kid": None}, id="kid-is-null"),
    ],
)
def test_when_the_kid_is_unusable_then_authentication_fails_without_loading_keys(
    header,
):
    """when the header has no text kid, the token is refused and Entra is not asked.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    key_source = tenant_key_source()
    token = forge_token_with_header(header, valid_claims())

    with pytest.raises(AuthenticationError) as raised:
        verify_with(token, key_source=key_source)

    assert raised.value.log_context["reason"] in {
        "unknown_signing_key",
        "malformed_token",
    }
    assert key_source.loads == []


@pytest.mark.parametrize("granted_scope", MISSING_SCOPES)
def test_when_the_token_lacks_the_scope_then_authorization_fails_with_the_verified_ids(
    granted_scope: object,
):
    """when scp lacks the required scope, AuthorizationError logs reason, oid and tid.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    token = make_token(scp=granted_scope)

    with pytest.raises(AuthorizationError) as raised:
        verify_with(token)

    assert raised.value.log_context == {
        "reason": "missing_scope",
        "oid": OBJECT_ID,
        "tid": TEST_TENANT_ID,
    }
    assert raised.value.public_message == AuthorizationError.default_message
    assert SCOPE_NAME not in raised.value.public_message


@pytest.mark.parametrize("granted_scope", ACCEPTED_SCOPE_CLAIMS)
def test_when_scp_lists_the_required_scope_then_the_token_is_accepted(granted_scope):
    """when scp holds the required scope alone or among others, the token passes.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    assert verify_with(make_token(scp=granted_scope)).id == OBJECT_ID


@pytest.mark.parametrize("configured_scope", SCOPE_CONFIGURATIONS)
def test_when_the_scope_is_configured_in_any_form_then_the_bare_scp_matches(
    configured_scope,
):
    """when the required scope is a name or a URI, a token with the bare scp passes.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.__init__().
    """
    principal = verify_with(make_token(), required_scope=configured_scope)

    assert principal.id == OBJECT_ID


@pytest.mark.parametrize("audience", ACCEPTED_AUDIENCES)
def test_when_the_audience_uses_a_registered_form_then_the_token_is_accepted(audience):
    """when aud is the client id, its api:// form or a list holding one, it passes.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    assert verify_with(make_token(aud=audience)).id == OBJECT_ID


def test_when_the_token_has_oid_and_sub_then_oid_is_the_identity():
    """when both oid and sub are present, the id is the stable oid.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    assert verify_with(make_token(sub=SUBJECT_ID)).id == OBJECT_ID


def test_when_the_token_has_no_oid_then_the_subject_is_the_identity():
    """when oid is absent, the id falls back to sub.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    assert verify_with(make_token(oid=None, sub=SUBJECT_ID)).id == SUBJECT_ID


def test_when_the_token_carries_several_roles_then_all_of_them_are_kept():
    """when the roles claim lists several app roles, every one reaches the principal.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    principal = verify_with(make_token(roles=["Admin", "Reader"]))

    assert principal.roles == ("Admin", "Reader")


@pytest.mark.parametrize(
    "roles",
    [
        pytest.param("Admin", id="roles-is-a-string"),
        pytest.param({"Admin": True}, id="roles-is-an-object"),
        pytest.param(None, id="no-roles-claim"),
    ],
)
def test_when_the_roles_claim_is_not_a_list_then_the_principal_has_no_roles(roles):
    """when roles is missing or not a list, no role is granted.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    assert verify_with(make_token(roles=roles)).roles == ()


def test_when_the_roles_claim_has_non_text_entries_then_only_the_names_are_kept():
    """when roles mixes names and other values, only the strings become roles.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    principal = verify_with(make_token(roles=["Admin", 7, None, "Reader"]))

    assert principal.roles == ("Admin", "Reader")


def test_when_the_token_has_an_email_claim_then_it_is_the_email_not_the_username():
    """when email and preferred_username are present, each fills its own field.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    principal = verify_with(make_token(email=USER_EMAIL))

    assert (principal.email, principal.username) == (USER_EMAIL, USERNAME)


def test_when_only_a_preferred_username_exists_then_it_is_never_promoted_to_email():
    """when there is no email claim, the sign-in name stays the username only.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    principal = verify_with(make_token())

    assert (principal.email, principal.username) == (None, USERNAME)


def test_when_the_token_has_no_name_claims_then_email_and_username_are_empty():
    """when neither email nor preferred_username is present, both fields are None.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    principal = verify_with(make_token(preferred_username=None))

    assert (principal.email, principal.username) == (None, None)


@pytest.mark.parametrize("algorithm", DISALLOWED_ALGORITHMS)
def test_when_a_token_uses_another_rsa_algorithm_then_it_is_rejected(algorithm):
    """when a token is signed with RS384, RS512 or PS256, only RS256 is honoured.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.verify().
    """
    token = sign_token(valid_claims(), tenant_signing_key(), algorithm=algorithm)

    with pytest.raises(AuthenticationError) as raised:
        verify_with(token)

    assert raised.value.log_context["reason"] == "disallowed_algorithm"


def test_when_the_expiry_is_inside_the_leeway_then_the_token_is_accepted():
    """when exp passed a few seconds before the leeway ends, the token still passes.

    Validates app.infrastructure.auth.entra.CLOCK_SKEW_LEEWAY_SECONDS.
    """
    expired_by = PROMISED_LEEWAY_SECONDS - SKEW_MARGIN_SECONDS
    token = make_token(exp=seconds_from_now(-expired_by))

    assert verify_with(token).id == OBJECT_ID


def test_when_the_expiry_is_beyond_the_leeway_then_the_token_is_rejected():
    """when exp passed a few seconds after the leeway ended, the token is expired.

    Validates app.infrastructure.auth.entra.CLOCK_SKEW_LEEWAY_SECONDS.
    """
    expired_by = PROMISED_LEEWAY_SECONDS + SKEW_MARGIN_SECONDS
    token = make_token(exp=seconds_from_now(-expired_by))

    with pytest.raises(AuthenticationError) as raised:
        verify_with(token)

    assert raised.value.log_context["reason"] == "expired"


@pytest.mark.parametrize("claim", ["iat", "nbf"])
def test_when_a_start_time_is_inside_the_leeway_then_the_token_is_accepted(claim):
    """when iat or nbf lies a few seconds ahead, the leeway absorbs the clock skew.

    Validates app.infrastructure.auth.entra.CLOCK_SKEW_LEEWAY_SECONDS.
    """
    ahead_by = PROMISED_LEEWAY_SECONDS - SKEW_MARGIN_SECONDS
    token = make_token(**{claim: seconds_from_now(ahead_by)})

    assert verify_with(token).id == OBJECT_ID


@pytest.mark.parametrize(
    ("configured", "extra_audience", "expected"),
    [
        pytest.param(
            TEST_API_CLIENT_ID,
            "",
            (TEST_API_CLIENT_ID, API_AUDIENCE),
            id="client-id-only",
        ),
        pytest.param(
            TEST_API_CLIENT_ID,
            "https://api.example.com",
            (TEST_API_CLIENT_ID, API_AUDIENCE, "https://api.example.com"),
            id="with-a-custom-audience",
        ),
        pytest.param(
            TEST_API_CLIENT_ID,
            API_AUDIENCE,
            (TEST_API_CLIENT_ID, API_AUDIENCE),
            id="duplicate-is-listed-once",
        ),
        pytest.param("", "", (), id="nothing-configured"),
        pytest.param(
            "",
            "https://api.example.com",
            ("https://api.example.com",),
            id="audience-only",
        ),
    ],
)
def test_when_audiences_are_expected_then_every_registered_form_is_listed_once(
    configured, extra_audience, expected
):
    """when settings are read, the client id, its api:// form and any extra are listed.

    Validates app.infrastructure.auth.entra.expected_audiences().
    """
    auth_settings = AuthSettings(
        entra_api_client_id=configured, entra_api_audience=extra_audience
    )

    assert expected_audiences(auth_settings) == expected


def test_when_no_audience_is_given_then_construction_fails():
    """when the audience list is empty, the verifier refuses to be built.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.__init__().
    """
    with pytest.raises(ValueError, match="audience"):
        build_verifier(audiences=())


@pytest.mark.parametrize("scope", ["", "  ", f"{API_AUDIENCE}/"])
def test_when_the_scope_is_empty_then_construction_fails_so_the_check_cannot_be_skipped(
    scope,
):
    """when the required scope normalises to nothing, the verifier refuses to be built.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.__init__().
    """
    with pytest.raises(ValueError, match="scope"):
        build_verifier(required_scope=scope)


def capture_key_wiring(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], type[StubKeySource]]:
    """Swap the key client and the resolver for doubles that record their arguments.

    Returns:
        The dict the doubles fill in once ``from_settings`` builds them, and the
        key client double's type, which the resolver is expected to receive.
    """
    captured: dict[str, object] = {}

    class CapturingKeyClient(StubKeySource):
        """Records its construction instead of fetching anything."""

        def __init__(self, uri: str, *, timeout: float) -> None:
            super().__init__({})
            captured.update(uri=uri, timeout=timeout)

    class CapturingResolver(CooldownSigningKeyResolver):
        """Records the cooldown it is given."""

        def __init__(self, key_source, *, refresh_cooldown_seconds, **options) -> None:
            captured.update(key_source=key_source, cooldown=refresh_cooldown_seconds)
            super().__init__(
                key_source, refresh_cooldown_seconds=refresh_cooldown_seconds, **options
            )

    monkeypatch.setattr(entra_module, "PyJWKClient", CapturingKeyClient)
    monkeypatch.setattr(entra_module, "CooldownSigningKeyResolver", CapturingResolver)
    return captured, CapturingKeyClient


def test_when_built_from_settings_then_the_key_client_and_the_cooldown_follow_them(
    monkeypatch,
):
    """when from_settings runs, the key client and the resolver get their settings.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.from_settings().
    """
    captured, key_client_type = capture_key_wiring(monkeypatch)
    auth_settings = AuthSettings(
        entra_tenant_id=TEST_TENANT_ID,
        entra_api_client_id=TEST_API_CLIENT_ID,
        entra_jwks_timeout=KEY_TIMEOUT_SECONDS,
        entra_jwks_refresh_cooldown=KEY_COOLDOWN_SECONDS,
    )

    verifier = EntraTokenVerifier.from_settings(auth_settings)

    assert isinstance(verifier, EntraTokenVerifier)
    assert isinstance(captured.pop("key_source"), key_client_type)
    assert captured == {
        "uri": auth_settings.entra_jwks_url,
        "timeout": KEY_TIMEOUT_SECONDS,
        "cooldown": KEY_COOLDOWN_SECONDS,
    }


def test_when_built_from_settings_without_an_audience_then_it_fails_loudly():
    """when neither client id nor audience is set, from_settings raises ValueError.

    Validates app.infrastructure.auth.entra.EntraTokenVerifier.from_settings().
    """
    with pytest.raises(ValueError, match="audience"):
        EntraTokenVerifier.from_settings(AuthSettings(entra_tenant_id=TEST_TENANT_ID))
