import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from hygroup.api.app import create_app
from hygroup.api.config import ApiServerSettings
from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry


@pytest_asyncio.fixture
async def test_registry():
    temp_dir = tempfile.mkdtemp()
    registry = DefaultUserRegistry(Path(temp_dir) / "test_registry.json")

    # Setup test users
    await registry.register(
        User(
            name="testuser",
            secrets={"api_key": "secret123", "db_pass": "dbsecret"},
            mappings={"slack": "john.doe", "github": "johndoe123"},
        ),
        "testpassword",
    )
    await registry.register(
        User(
            name="anotheruser",
            secrets={"their_key": "their_secret"},
            mappings={"github": "another-github-user", "slack": "another.user"},
        ),
        "anotherpassword",
    )
    await registry.register(User(name="emptyuser", secrets={}, mappings={}), "emptypassword")
    await registry.register(
        User(name="singlemappinguser", secrets={"single_secret": "value"}, mappings={"gitlab": "single.user"}),
        "singlepassword",
    )

    yield registry
    shutil.rmtree(temp_dir)


@pytest_asyncio.fixture
async def test_app(test_registry):
    settings = ApiServerSettings(
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_algorithm="HS256",
        jwt_expiration_days=7,
    )
    return create_app(settings=settings, user_registry=test_registry)


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


class TestHelpers:
    @staticmethod
    def get_auth_headers(client: TestClient, username: str, password: str) -> dict:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @staticmethod
    def assert_unauthorized(response, detail: str | None = None):
        assert response.status_code == 401
        if detail:
            assert response.json()["detail"] == detail

    @staticmethod
    def assert_forbidden(response):
        assert response.status_code == 403

    @staticmethod
    def assert_not_found(response, resource: str):
        assert response.status_code == 404
        assert response.json()["detail"] == f"Secret '{resource}' not found"

    @staticmethod
    def assert_conflict(response, resource: str):
        assert response.status_code == 409
        assert response.json()["detail"] == f"Secret '{resource}' already exists"

    @staticmethod
    def assert_validation_error(response):
        assert response.status_code == 422

    @staticmethod
    def assert_server_error(response, operation: str):
        assert response.status_code == 500
        assert response.json()["detail"] == f"Failed to {operation}"

    @staticmethod
    def get_secret_names(client: TestClient, headers: dict) -> list[str]:
        response = client.get("/api/v1/users/secrets", headers=headers)
        assert response.status_code == 200
        return [s["name"] for s in response.json()["secrets"]]

    @staticmethod
    def get_mappings(client: TestClient, headers: dict) -> list[dict]:
        response = client.get("/api/v1/users/mappings", headers=headers)
        assert response.status_code == 200
        return response.json()["mappings"]

    @staticmethod
    def get_mapping_gateways(client: TestClient, headers: dict) -> list[str]:
        mappings = TestHelpers.get_mappings(client, headers)
        return [m["gateway_name"] for m in mappings]


# GET /info tests
@pytest.mark.asyncio
async def test_get_user_info_success(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.get("/api/v1/users/info", headers=headers)

    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,expected_status",
    [
        (None, 403),
        ({"Authorization": "Bearer invalid-token"}, 401),
    ],
)
async def test_get_user_info_auth_errors(client, headers, expected_status):
    response = client.get("/api/v1/users/info", headers=headers)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_get_user_info_after_logout(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    # Logout
    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200

    # Try to access with invalidated token
    response = client.get("/api/v1/users/info", headers=headers)
    TestHelpers.assert_unauthorized(response, "User session has been terminated")


# GET /secrets tests
@pytest.mark.asyncio
async def test_get_secrets_empty_user(client):
    headers = TestHelpers.get_auth_headers(client, "emptyuser", "emptypassword")

    response = client.get("/api/v1/users/secrets", headers=headers)

    assert response.status_code == 200
    assert response.json()["secrets"] == []


@pytest.mark.asyncio
async def test_get_secrets_with_data(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.get("/api/v1/users/secrets", headers=headers)

    assert response.status_code == 200
    secret_names = [s["name"] for s in response.json()["secrets"]]
    assert set(secret_names) == {"api_key", "db_pass"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,expected_status",
    [
        (None, 403),
        ({"Authorization": "Bearer invalid-token"}, 401),
    ],
)
async def test_get_secrets_auth_errors(client, headers, expected_status):
    response = client.get("/api/v1/users/secrets", headers=headers)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_get_secrets_registry_error(client, test_registry):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    with patch.object(test_registry, "get_secrets", side_effect=Exception("Registry error")):
        response = client.get("/api/v1/users/secrets", headers=headers)

    TestHelpers.assert_server_error(response, "retrieve secrets")


# POST /secrets tests
@pytest.mark.asyncio
async def test_create_secret_success(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.post(
        "/api/v1/users/secrets",
        json={"name": "new_secret", "value": "new_value"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Secret 'new_secret' created successfully"
    assert "new_secret" in TestHelpers.get_secret_names(client, headers)


@pytest.mark.asyncio
async def test_create_secret_duplicate(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.post(
        "/api/v1/users/secrets",
        json={"name": "api_key", "value": "new_value"},
        headers=headers,
    )

    TestHelpers.assert_conflict(response, "api_key")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,value",
    [
        ("", "some_value"),
        ("new_secret", ""),
    ],
)
async def test_create_secret_validation_errors(client, name, value):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.post("/api/v1/users/secrets", json={"name": name, "value": value}, headers=headers)

    TestHelpers.assert_validation_error(response)


@pytest.mark.asyncio
async def test_create_secret_no_auth(client):
    response = client.post("/api/v1/users/secrets", json={"name": "new_secret", "value": "new_value"})
    TestHelpers.assert_forbidden(response)


@pytest.mark.asyncio
async def test_create_secret_registry_error(client, test_registry):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    with patch.object(test_registry, "set_secret", side_effect=Exception("Registry error")):
        response = client.post(
            "/api/v1/users/secrets",
            json={"name": "new_secret", "value": "new_value"},
            headers=headers,
        )

    TestHelpers.assert_server_error(response, "create secret")


# PUT /secrets/{key} tests
@pytest.mark.asyncio
async def test_update_secret_success(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.put("/api/v1/users/secrets/api_key", json={"value": "updated_value"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Secret 'api_key' updated successfully"


@pytest.mark.asyncio
async def test_update_nonexistent_secret(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.put("/api/v1/users/secrets/nonexistent", json={"value": "some_value"}, headers=headers)

    TestHelpers.assert_not_found(response, "nonexistent")


@pytest.mark.asyncio
async def test_update_secret_empty_value(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.put("/api/v1/users/secrets/api_key", json={"value": ""}, headers=headers)

    TestHelpers.assert_validation_error(response)


@pytest.mark.asyncio
async def test_update_secret_no_auth(client):
    response = client.put("/api/v1/users/secrets/api_key", json={"value": "new_value"})
    TestHelpers.assert_forbidden(response)


@pytest.mark.asyncio
async def test_update_secret_registry_error(client, test_registry):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    with patch.object(test_registry, "set_secret", side_effect=Exception("Registry error")):
        response = client.put("/api/v1/users/secrets/api_key", json={"value": "new_value"}, headers=headers)

    TestHelpers.assert_server_error(response, "update secret")


# DELETE /secrets/{key} tests
@pytest.mark.asyncio
async def test_delete_secret_success(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.delete("/api/v1/users/secrets/api_key", headers=headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Secret 'api_key' deleted successfully"
    assert "api_key" not in TestHelpers.get_secret_names(client, headers)


@pytest.mark.asyncio
async def test_delete_nonexistent_secret(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.delete("/api/v1/users/secrets/nonexistent", headers=headers)

    TestHelpers.assert_not_found(response, "nonexistent")


@pytest.mark.asyncio
async def test_delete_secret_no_auth(client):
    response = client.delete("/api/v1/users/secrets/api_key")
    TestHelpers.assert_forbidden(response)


@pytest.mark.asyncio
async def test_delete_secret_registry_error(client, test_registry):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    with patch.object(test_registry, "delete_secret", side_effect=Exception("Registry error")):
        response = client.delete("/api/v1/users/secrets/api_key", headers=headers)

    TestHelpers.assert_server_error(response, "delete secret")


# GET /mappings tests
@pytest.mark.asyncio
async def test_get_mappings_empty_user(client):
    headers = TestHelpers.get_auth_headers(client, "emptyuser", "emptypassword")

    response = client.get("/api/v1/users/mappings", headers=headers)

    assert response.status_code == 200
    assert response.json()["mappings"] == []


@pytest.mark.asyncio
async def test_get_mappings_with_data(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    response = client.get("/api/v1/users/mappings", headers=headers)

    assert response.status_code == 200
    mappings = response.json()["mappings"]
    assert len(mappings) == 2

    # Convert to dict for easier assertion
    mappings_dict = {m["gateway_name"]: m["gateway_username"] for m in mappings}
    assert mappings_dict == {"slack": "john.doe", "github": "johndoe123"}


@pytest.mark.asyncio
async def test_get_mappings_single_mapping(client):
    headers = TestHelpers.get_auth_headers(client, "singlemappinguser", "singlepassword")

    response = client.get("/api/v1/users/mappings", headers=headers)

    assert response.status_code == 200
    mappings = response.json()["mappings"]
    assert len(mappings) == 1
    assert mappings[0]["gateway_name"] == "gitlab"
    assert mappings[0]["gateway_username"] == "single.user"


@pytest.mark.asyncio
async def test_get_mappings_multiple_gateways(client):
    headers = TestHelpers.get_auth_headers(client, "anotheruser", "anotherpassword")

    response = client.get("/api/v1/users/mappings", headers=headers)

    assert response.status_code == 200
    mappings = response.json()["mappings"]
    assert len(mappings) == 2

    # Verify gateway names
    gateway_names = TestHelpers.get_mapping_gateways(client, headers)
    assert set(gateway_names) == {"github", "slack"}

    # Verify actual mapping values for anotheruser
    mappings_dict = {m["gateway_name"]: m["gateway_username"] for m in mappings}
    assert mappings_dict == {"github": "another-github-user", "slack": "another.user"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers,expected_status",
    [
        (None, 403),
        ({"Authorization": "Bearer invalid-token"}, 401),
    ],
)
async def test_get_mappings_auth_errors(client, headers, expected_status):
    response = client.get("/api/v1/users/mappings", headers=headers)
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_get_mappings_after_logout(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    # Logout
    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200

    # Try to access with invalidated token
    response = client.get("/api/v1/users/mappings", headers=headers)
    TestHelpers.assert_unauthorized(response, "User session has been terminated")


@pytest.mark.asyncio
async def test_get_mappings_registry_error(client, test_registry):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")

    with patch.object(test_registry, "get_mappings", side_effect=Exception("Registry error")):
        response = client.get("/api/v1/users/mappings", headers=headers)

    TestHelpers.assert_server_error(response, "retrieve mappings")


# Integration tests
@pytest.mark.asyncio
async def test_secret_lifecycle(client):
    headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")
    secret_name = "lifecycle_secret"

    # Create
    create_response = client.post(
        "/api/v1/users/secrets", json={"name": secret_name, "value": "initial_value"}, headers=headers
    )
    assert create_response.status_code == 200

    # Verify exists
    assert secret_name in TestHelpers.get_secret_names(client, headers)

    # Update
    update_response = client.put(
        f"/api/v1/users/secrets/{secret_name}", json={"value": "updated_value"}, headers=headers
    )
    assert update_response.status_code == 200

    # Delete
    delete_response = client.delete(f"/api/v1/users/secrets/{secret_name}", headers=headers)
    assert delete_response.status_code == 200

    # Verify deleted
    assert secret_name not in TestHelpers.get_secret_names(client, headers)


@pytest.mark.asyncio
async def test_user_secrets_isolation(client):
    # Setup users with their secrets
    user1_headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")
    user2_headers = TestHelpers.get_auth_headers(client, "anotheruser", "anotherpassword")

    client.post(
        "/api/v1/users/secrets",
        json={"name": "user1_secret", "value": "user1_value"},
        headers=user1_headers,
    )

    client.post(
        "/api/v1/users/secrets",
        json={"name": "user2_secret", "value": "user2_value"},
        headers=user2_headers,
    )

    # Verify isolation
    user1_secrets = TestHelpers.get_secret_names(client, user1_headers)
    user2_secrets = TestHelpers.get_secret_names(client, user2_headers)

    assert "user1_secret" in user1_secrets
    assert "user2_secret" not in user1_secrets
    assert "user2_secret" in user2_secrets
    assert "user1_secret" not in user2_secrets

    # Verify cross-user access fails
    response = client.delete("/api/v1/users/secrets/user2_secret", headers=user1_headers)
    TestHelpers.assert_not_found(response, "user2_secret")


@pytest.mark.asyncio
async def test_user_mappings_isolation(client):
    # Setup users with their auth headers
    user1_headers = TestHelpers.get_auth_headers(client, "testuser", "testpassword")
    user2_headers = TestHelpers.get_auth_headers(client, "anotheruser", "anotherpassword")

    # Get mappings for each user
    user1_mappings = TestHelpers.get_mappings(client, user1_headers)
    user2_mappings = TestHelpers.get_mappings(client, user2_headers)

    # Verify user1 has their own mappings
    user1_gateways = {m["gateway_name"] for m in user1_mappings}
    assert user1_gateways == {"slack", "github"}

    # Verify user2 has their own different mappings
    user2_gateways = {m["gateway_name"] for m in user2_mappings}
    assert user2_gateways == {"github", "slack"}

    # Verify no cross-user data leakage
    user1_slack_mapping = next(m for m in user1_mappings if m["gateway_name"] == "slack")
    user2_slack_mapping = next(m for m in user2_mappings if m["gateway_name"] == "slack")

    assert user1_slack_mapping["gateway_username"] == "john.doe"
    assert user2_slack_mapping["gateway_username"] == "another.user"

    # Both users have same gateway types but different usernames - verify complete isolation
    user1_github_mapping = next(m for m in user1_mappings if m["gateway_name"] == "github")
    user2_github_mapping = next(m for m in user2_mappings if m["gateway_name"] == "github")

    # Verify each user has their specific github username
    assert user1_github_mapping["gateway_username"] == "johndoe123"
    assert user2_github_mapping["gateway_username"] == "another-github-user"

    # Verify no cross-user data leakage for any mapping values
    user1_values = {m["gateway_username"] for m in user1_mappings}
    user2_values = {m["gateway_username"] for m in user2_mappings}

    assert "another-github-user" not in user1_values
    assert "another.user" not in user1_values
    assert "johndoe123" not in user2_values
    assert "john.doe" not in user2_values
