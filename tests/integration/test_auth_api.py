import shutil
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from hygroup.api.app import create_app
from hygroup.api.config import ApiServerSettings
from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry

# Test constants
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpassword"
JWT_EXPIRATION_SECONDS = 7 * 24 * 60 * 60
INVALID_CREDENTIALS_MSG = "Invalid username or password"
SESSION_TERMINATED_MSG = "User session has been terminated"
LOGOUT_SUCCESS_MSG = "Successfully logged out"


@pytest_asyncio.fixture
async def test_registry():
    temp_dir = tempfile.mkdtemp()
    registry = DefaultUserRegistry(Path(temp_dir) / "test_registry.json")

    test_user = User(name=TEST_USERNAME, secrets={"test_key": "test_value"})
    await registry.register(test_user, TEST_PASSWORD)

    yield registry
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def test_app(test_registry):
    settings = ApiServerSettings(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiration_days=7,
    )

    return create_app(
        settings=settings,
        user_registry=test_registry,
    )


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


# Helper functions
def login_and_get_token(client, username=TEST_USERNAME, password=TEST_PASSWORD):
    """Login and return the access token."""
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return response.json()["access_token"]


def make_auth_headers(token):
    """Create authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


def assert_login_success(response):
    """Assert that a login response is successful with correct structure."""
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == JWT_EXPIRATION_SECONDS
    assert len(data["access_token"]) > 0


def assert_unauthorized(response, detail=INVALID_CREDENTIALS_MSG):
    """Assert that a response is 401 with expected detail."""
    assert response.status_code == 401
    assert response.json()["detail"] == detail


@pytest.mark.asyncio
async def test_login_valid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    assert_login_success(response)


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": TEST_USERNAME, "password": "wrongpassword"})
    assert_unauthorized(response)


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = client.post("/api/v1/auth/login", json={"username": "nonexistent", "password": "anypassword"})
    assert_unauthorized(response)


@pytest.mark.asyncio
async def test_get_current_user_with_valid_token(client):
    token = login_and_get_token(client)
    response = client.get("/api/v1/users/info", headers=make_auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == TEST_USERNAME


@pytest.mark.asyncio
async def test_get_current_user_without_token(client):
    response = client.get("/api/v1/users/info")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_with_invalid_token(client):
    response = client.get("/api/v1/users/info", headers=make_auth_headers("invalid-token"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_valid_token(client):
    token = login_and_get_token(client)
    response = client.post("/api/v1/auth/logout", headers=make_auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == LOGOUT_SUCCESS_MSG


@pytest.mark.asyncio
async def test_logout_without_token(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_endpoint_after_logout(client):
    token = login_and_get_token(client)
    auth_headers = make_auth_headers(token)

    # Verify token works before logout
    me_response = client.get("/api/v1/users/info", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == TEST_USERNAME

    # Logout with the token
    logout_response = client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_response.status_code == 200

    # Try to use the same token after logout - should fail
    me_after_logout_response = client.get("/api/v1/users/info", headers=auth_headers)
    assert_unauthorized(me_after_logout_response, SESSION_TERMINATED_MSG)
