from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError

from hygroup.api.auth.jwt import create_access_token, get_current_username, verify_token
from hygroup.api.config import ApiServerSettings


@pytest.fixture
def settings():
    return ApiServerSettings(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiration_days=7,
    )


@pytest.fixture
def expired_settings():
    return ApiServerSettings(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiration_days=-1,  # Already expired
    )


def test_create_access_token(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    # Token should be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0

    # Token should contain 3 parts separated by dots (header.payload.signature)
    parts = token.split(".")
    assert len(parts) == 3


def test_verify_token_valid(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    payload = verify_token(token, settings)

    # Payload should contain expected fields
    assert "username" in payload
    assert "exp" in payload
    assert "iat" in payload
    assert payload["username"] == username


def test_verify_token_invalid_signature(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    # Tamper with the token
    tampered_token = token[:-5] + "xxxxx"

    with pytest.raises(JWTError):
        verify_token(tampered_token, settings)


def test_verify_token_wrong_secret(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    # Create settings with different secret key
    wrong_settings = ApiServerSettings(jwt_secret_key="wrong-secret-key", jwt_algorithm="HS256", jwt_expiration_days=7)

    with pytest.raises(JWTError):
        verify_token(token, wrong_settings)


def test_verify_token_expired(expired_settings):
    username = "testuser"
    token = create_access_token(username, expired_settings)

    with pytest.raises(JWTError):
        verify_token(token, expired_settings)


def test_get_current_username_valid(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    extracted_username = get_current_username(token, settings)
    assert extracted_username == username


def test_get_current_username_invalid_token(settings):
    invalid_token = "invalid.token.here"

    extracted_username = get_current_username(invalid_token, settings)
    assert extracted_username is None


def test_get_current_username_expired_token(expired_settings):
    username = "testuser"
    token = create_access_token(username, expired_settings)

    extracted_username = get_current_username(token, expired_settings)
    assert extracted_username is None


def test_token_contains_expected_claims(settings):
    username = "testuser"
    token = create_access_token(username, settings)

    payload = verify_token(token, settings)

    # Check username claim
    assert payload["username"] == username

    # Check that expiration is set correctly (approximately)
    exp_timestamp = payload["exp"]
    expected_exp = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiration_days)
    actual_exp = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)  # type: ignore

    # Allow 1 minute tolerance for test execution time
    time_diff = abs((actual_exp - expected_exp).total_seconds())
    assert time_diff < 60, f"Expiration time difference: {time_diff} seconds"

    # Check that issued at time is recent
    iat_timestamp = payload["iat"]
    iat_time = datetime.fromtimestamp(iat_timestamp, tz=timezone.utc)  # type: ignore
    now = datetime.now(timezone.utc)

    # Should be issued within the last minute
    time_since_issued = (now - iat_time).total_seconds()
    assert time_since_issued < 60, f"Token issued {time_since_issued} seconds ago"
