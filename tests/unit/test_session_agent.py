import asyncio
from asyncio import Event
from contextvars import ContextVar
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from hygroup.agent import Agent, AgentRequest, AgentResponse
from hygroup.session import Session, SessionAgent


class MockSession(Mock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = Event()
        self.handle_system_response_mock = AsyncMock()
        self.handle_permission_request_mock = AsyncMock()
        self.handle_feedback_request_mock = AsyncMock()
        self.handle_agent_response_mock = AsyncMock()
        self._sender_info = ContextVar[dict[str, Any]]("sender_info")

    async def handle_permission_request(self, *args, **kwargs):
        await self.handle_permission_request_mock(*args, **kwargs)
        self.event.set()

    async def handle_feedback_request(self, *args, **kwargs):
        await self.handle_feedback_request_mock(*args, **kwargs)
        self.event.set()

    async def handle_system_response(self, *args, **kwargs):
        await self.handle_system_response_mock(*args, **kwargs)
        self.event.set()

    async def handle_agent_response(self, *args, **kwargs):
        await self.handle_agent_response_mock(*args, **kwargs)
        self.event.set()

    async def called(self):
        await self.event.wait()


@pytest.fixture
def mock_session():
    """Create a mock Session instance with async await capability."""
    session = MockSession(spec=Session)
    session.messages = []
    return session


@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.name = "test_agent"
    agent.session_scope.return_value.__aenter__ = AsyncMock()
    agent.session_scope.return_value.__aexit__ = AsyncMock(return_value=None)
    agent.request_scope.return_value.__aenter__ = AsyncMock()
    agent.request_scope.return_value.__aexit__ = AsyncMock(return_value=None)
    return agent


@pytest_asyncio.fixture
async def session_agent(mock_agent, mock_session):
    session_agent = SessionAgent(mock_agent, mock_session)
    yield session_agent
    if session_agent._worker_task:
        session_agent._worker_task.cancel()
        try:
            await session_agent._worker_task
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_worker_handles_agent_run_exception(session_agent: SessionAgent, mock_agent, mock_session):
    """Test that worker handles exceptions from agent.run() properly."""
    test_exception = Exception("Test exception")

    async def failing_generator(*args, **kwargs):
        raise test_exception
        yield  # This won't be reached but makes it a generator

    mock_agent.run = failing_generator

    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)

    # Mock the logger to verify exception logging
    with patch("hygroup.session.logger") as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)

        # Wait for handle_system_response to be called
        await mock_session.called()

        # Verify exception was logged
        mock_logger.exception.assert_called_once_with(test_exception)

        # Verify system response was sent
        call_args = mock_session.handle_system_response_mock.call_args
        assert call_args[1]["receiver"] == sender
        assert call_args[1]["response"].text == "Execution of agent 'test_agent' failed."
        assert call_args[1]["response"].final is True


@pytest.mark.asyncio
async def test_worker_handles_agent_run_success(session_agent, mock_agent, mock_session):
    """Test that worker handles successful agent.run() properly."""
    # Mock agent.run to yield a successful response
    test_response = AgentResponse(text="Test response", final=True)

    async def response_generator(*args, **kwargs):
        yield test_response

    mock_agent.run = response_generator

    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)

    # Mock the logger to verify no exception logging
    with patch("hygroup.session.logger") as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)

        # Give the worker a moment to process the request
        await mock_session.called()

        # Verify no exception was logged
        mock_logger.exception.assert_not_called()

        # Verify agent response was handled
        call_args = mock_session.handle_agent_response_mock.call_args
        assert call_args[1]["sender"] == "test_agent"
        assert call_args[1]["receiver"] == sender
        assert call_args[1]["response"].text == "Test response"
        assert call_args[1]["response"].final is True
        assert call_args[1]["response"].request_id is not None  # request_id is added by SessionAgent

        # Verify system response was NOT called
        mock_session.handle_system_response_mock.assert_not_called()


@pytest.mark.asyncio
async def test_worker_continues_after_exception(session_agent, mock_agent, mock_session):
    """Test that worker continues processing after handling an exception."""
    sender = "test_user"

    first_request = AgentRequest(query="first query", sender=sender)
    first_exception = Exception("First exception")

    async def failing_generator(*args, **kwargs):
        raise first_exception
        yield  # This won't be reached but makes it a generator

    # Second request - will succeed
    second_response = AgentResponse(text="Second response", final=True)

    async def response_generator(*args, **kwargs):
        yield second_response

    with patch("hygroup.session.logger") as mock_logger:
        mock_agent.run = failing_generator

        # Invoke first request (will fail)
        await session_agent.invoke(first_request, secrets=None)

        # Give the worker a moment to process the first request
        await mock_session.called()
        mock_session.event.clear()

        # Verify first exception was handled
        mock_logger.exception.assert_called_once_with(first_exception)
        assert mock_session.handle_system_response_mock.call_count == 1

        # reset for second request
        mock_logger.reset_mock()
        mock_session.handle_system_response_mock.reset_mock()

        # Now mock agent.run to succeed for second request
        mock_agent.run = response_generator

        # Invoke second request (will succeed)
        second_request = AgentRequest(query="second query", sender=sender)
        await session_agent.invoke(second_request, secrets=None)

        # Give the worker a moment to process the second request
        await mock_session.called()

        # Verify second request was processed successfully
        mock_logger.exception.assert_not_called()
        call_args = mock_session.handle_agent_response_mock.call_args
        assert call_args[1]["sender"] == "test_agent"
        assert call_args[1]["receiver"] == sender
        assert call_args[1]["response"].text == "Second response"
        assert call_args[1]["response"].final is True
        assert call_args[1]["response"].request_id is not None
        mock_session.handle_system_response_mock.assert_not_called()


@pytest.mark.parametrize(
    "exception_type, exception_message",
    [
        (ValueError, "Invalid value"),
        (RuntimeError, "Runtime error occurred"),
        (ConnectionError, "Connection failed"),
        (Exception, "Generic exception"),
    ],
)
@pytest.mark.asyncio
async def test_worker_handles_different_exception_types(
    session_agent, mock_agent, mock_session, exception_type, exception_message
):
    """Test that worker handles various exception types consistently."""
    # Mock agent.run to raise the specified exception
    test_exception = exception_type(exception_message)

    async def failing_generator(*args, **kwargs):
        raise test_exception
        yield  # This won't be reached but makes it a generator

    mock_agent.run = failing_generator

    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)

    # Mock the logger to verify exception logging
    with patch("hygroup.session.logger") as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)

        # Give the worker a moment to process the request
        await mock_session.called()

        # Verify exception was logged
        mock_logger.exception.assert_called_once_with(test_exception)

        # Verify system response was sent with generic message regardless of exception type
        call_args = mock_session.handle_system_response_mock.call_args
        assert call_args[1]["receiver"] == sender
        assert call_args[1]["response"].text == "Execution of agent 'test_agent' failed."
        assert call_args[1]["response"].final is True
