import asyncio
from asyncio import Future
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from hygroup.agent import ConfirmationRequest, FeedbackRequest, PermissionRequest
from hygroup.user.base import RequestHandler
from hygroup.user.default.channel import RequestClient, RequestServer


class MockRequestHandler(RequestHandler):
    """Test RequestHandler that stores responses for verification."""

    def __init__(self):
        self.permission_calls = []
        self.feedback_calls = []
        self.confirmation_calls = []
        self.permission_response = 1  # Default: grant once
        self.feedback_response = "test response"  # Default response
        self.confirmation_response = (True, None)  # Default: confirm with no comment

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str, session_id: str):
        """Handle permission request and store call details."""
        self.permission_calls.append(
            {
                "tool_name": request.tool_name,
                "tool_args": request.tool_args,
                "tool_kwargs": request.tool_kwargs,
                "sender": sender,
                "receiver": receiver,
                "session_id": session_id,
            }
        )
        request.respond(self.permission_response)

    async def handle_feedback_request(self, request: FeedbackRequest, sender: str, receiver: str, session_id: str):
        """Handle feedback request and store call details."""
        self.feedback_calls.append(
            {"question": request.question, "sender": sender, "receiver": receiver, "session_id": session_id}
        )
        request.respond(self.feedback_response)

    async def handle_confirmation_request(
        self, request: ConfirmationRequest, sender: str, receiver: str, session_id: str
    ):
        """Handle confirmation request and store call details."""
        self.confirmation_calls.append(
            {"query": request.query, "sender": sender, "receiver": receiver, "session_id": session_id}
        )
        confirmed, comment = self.confirmation_response
        request.respond(confirmed, comment)


@pytest.fixture
def mock_user_registry():
    """Create a mock UserRegistry."""
    registry = AsyncMock()
    registry.authenticate = AsyncMock(return_value=True)
    registry.deauthenticate = AsyncMock(return_value=True)
    return registry


@pytest.fixture
def mock_request_handler():
    """Create a mock RequestHandler."""
    return MockRequestHandler()


@pytest_asyncio.fixture
async def request_server(mock_user_registry):
    """Create a RequestServer instance."""
    server = RequestServer(mock_user_registry, host="127.0.0.1", port=8627)
    await server.start(join=False)
    await asyncio.sleep(0.2)
    yield server
    await server.stop()


@pytest_asyncio.fixture
async def request_client(request_server: RequestServer, mock_request_handler):
    """Create a RequestClient instance."""
    client = RequestClient(handler=mock_request_handler, host=request_server.host, port=request_server.port)
    await client.authenticate("martin", "password")
    yield client, mock_request_handler
    await client.deauthenticate()


@pytest.mark.asyncio
async def test_permission_request_grant_once(request_server: RequestServer, request_client):
    """Test permission request with grant once response."""
    client, handler = request_client
    handler.permission_response = 1

    # Create permission request
    future: Future = Future()
    request = PermissionRequest("test_tool", ("arg1", "arg2"), {"kwarg1": "value1"}, future)

    # Handle request on server (should propagate to client) and await response
    await request_server.handle_permission_request(request, "agent1", "martin", "session123")
    result = await request.response()

    # Verify client handler was called
    assert len(handler.permission_calls) == 1
    call = handler.permission_calls[0]
    assert call["tool_name"] == "test_tool"
    assert call["tool_args"] == ("arg1", "arg2")
    assert call["tool_kwargs"] == {"kwarg1": "value1"}
    assert call["sender"] == "agent1"
    assert call["receiver"] == "martin"
    assert call["session_id"] == "session123"

    # Verify response was received by server
    assert result == 1


@pytest.mark.asyncio
async def test_permission_request_deny(request_server: RequestServer, request_client):
    """Test permission request with deny response."""
    client, handler = request_client
    handler.permission_response = 0

    # Create permission request
    future: Future = Future()
    request = PermissionRequest("dangerous_tool", (), {}, future)

    # Handle request on server and await response
    await request_server.handle_permission_request(request, "agent2", "martin", "session456")
    result = await request.response()

    # Verify client handler was called
    assert len(handler.permission_calls) == 1
    call = handler.permission_calls[0]
    assert call["tool_name"] == "dangerous_tool"
    assert call["sender"] == "agent2"
    assert call["session_id"] == "session456"

    # Verify response was received by server
    assert result == 0


@pytest.mark.asyncio
async def test_permission_request_grant_session(request_server: RequestServer, request_client):
    """Test permission request with grant session response."""
    client, handler = request_client
    handler.permission_response = 2

    # Create permission request
    future: Future = Future()
    request = PermissionRequest("batch_tool", ("item1", "item2"), {"batch_size": 10}, future)

    # Handle request on server and await response
    await request_server.handle_permission_request(request, "agent3", "martin", "session789")
    result = await request.response()

    # Verify client handler was called
    assert len(handler.permission_calls) == 1
    call = handler.permission_calls[0]
    assert call["tool_name"] == "batch_tool"
    assert call["tool_args"] == ("item1", "item2")
    assert call["tool_kwargs"] == {"batch_size": 10}

    # Verify response was received by server
    assert result == 2


@pytest.mark.asyncio
async def test_permission_request_grant_always(request_server: RequestServer, request_client):
    """Test permission request with grant always response."""
    client, handler = request_client
    handler.permission_response = 3

    # Create permission request
    future: Future = Future()
    request = PermissionRequest("trusted_tool", (), {"trust_level": "high"}, future)

    # Handle request on server and await response
    await request_server.handle_permission_request(request, "trusted_agent", "martin", "global_session")
    result = await request.response()

    # Verify client handler was called
    assert len(handler.permission_calls) == 1
    call = handler.permission_calls[0]
    assert call["tool_name"] == "trusted_tool"
    assert call["sender"] == "trusted_agent"
    assert call["session_id"] == "global_session"

    # Verify response was received by server
    assert result == 3


@pytest.mark.asyncio
async def test_feedback_request(request_server: RequestServer, request_client):
    """Test feedback request handling."""
    client, handler = request_client
    handler.feedback_response = "This is my feedback"

    # Create feedback request
    future: Future = Future()
    request = FeedbackRequest("What do you think about this approach?", future)

    # Handle request on server and await response
    await request_server.handle_feedback_request(request, "agent1", "martin", "session123")
    result = await request.response()

    # Verify client handler was called
    assert len(handler.feedback_calls) == 1
    call = handler.feedback_calls[0]
    assert call["question"] == "What do you think about this approach?"
    assert call["sender"] == "agent1"
    assert call["receiver"] == "martin"
    assert call["session_id"] == "session123"

    # Verify response was received by server
    assert result == "This is my feedback"


@pytest.mark.asyncio
async def test_multiple_permission_requests(request_server: RequestServer, request_client):
    """Test handling multiple permission requests."""
    client, handler = request_client
    handler.permission_response = 1

    # Create and handle multiple permission requests
    results = []
    for i in range(3):
        future: Future = Future()
        request = PermissionRequest(f"tool_{i}", (f"arg_{i}",), {f"key_{i}": f"value_{i}"}, future)
        await request_server.handle_permission_request(request, f"agent_{i}", "martin", f"session_{i}")
        result = await request.response()
        results.append(result)

    # Verify all client handler calls
    assert len(handler.permission_calls) == 3

    for i in range(3):
        call = handler.permission_calls[i]
        assert call["tool_name"] == f"tool_{i}"
        assert call["tool_args"] == (f"arg_{i}",)
        assert call["tool_kwargs"] == {f"key_{i}": f"value_{i}"}
        assert call["sender"] == f"agent_{i}"
        assert call["session_id"] == f"session_{i}"
        assert results[i] == 1


@pytest.mark.asyncio
async def test_mixed_requests(request_server: RequestServer, request_client):
    """Test handling mixed permission and feedback requests."""
    client, handler = request_client
    handler.permission_response = 2
    handler.feedback_response = "Mixed response"

    # Handle permission request
    perm_future: Future = Future()
    perm_request = PermissionRequest("mixed_tool", ("arg",), {"key": "value"}, perm_future)
    await request_server.handle_permission_request(perm_request, "agent1", "martin", "session1")
    perm_result = await perm_request.response()

    # Handle feedback request
    feedback_future: Future = Future()
    feedback_request = FeedbackRequest("How was the mixed test?", feedback_future)
    await request_server.handle_feedback_request(feedback_request, "agent2", "martin", "session2")
    feedback_result = await feedback_request.response()

    # Verify both handler calls
    assert len(handler.permission_calls) == 1
    assert len(handler.feedback_calls) == 1

    perm_call = handler.permission_calls[0]
    assert perm_call["tool_name"] == "mixed_tool"
    assert perm_call["sender"] == "agent1"
    assert perm_call["session_id"] == "session1"

    feedback_call = handler.feedback_calls[0]
    assert feedback_call["question"] == "How was the mixed test?"
    assert feedback_call["sender"] == "agent2"
    assert feedback_call["session_id"] == "session2"

    # Verify both responses
    assert perm_result == 2
    assert feedback_result == "Mixed response"


@pytest.mark.asyncio
async def test_request_when_user_not_connected(request_server: RequestServer, mock_user_registry):
    """Test handling requests when user is not connected."""
    # Create permission request for non-connected user
    future: Future = Future()
    request = PermissionRequest("test_tool", (), {}, future)

    # Handle request on server (user not connected) and await response
    await request_server.handle_permission_request(request, "agent1", "not_connected_user", "session123")
    perm_result = await request.response()

    # Should get denial response immediately
    assert perm_result == 0

    # Create feedback request for non-connected user
    feedback_future: Future = Future()
    feedback_request = FeedbackRequest("Test question", feedback_future)

    # Handle request on server (user not connected) and await response
    await request_server.handle_feedback_request(feedback_request, "agent1", "not_connected_user", "session123")
    feedback_result = await feedback_request.response()

    # Should get empty response immediately
    assert feedback_result == ""
