import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from hygroup.agent import Agent, AgentRequest, AgentResponse
from hygroup.session import Session, SessionAgent


@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.name = "test_agent"
    agent.session_scope.return_value.__aenter__ = AsyncMock()
    agent.session_scope.return_value.__aexit__ = AsyncMock()
    agent.request_scope.return_value.__aenter__ = AsyncMock()
    agent.request_scope.return_value.__aexit__ = AsyncMock()
    return agent


@pytest.fixture
def mock_session():
    """Create a mock Session instance."""
    session = Mock(spec=Session)
    session.messages = []
    session.handle_system_response = AsyncMock()
    session.handle_permission_request = AsyncMock()
    session.handle_feedback_request = AsyncMock()
    session.handle_agent_response = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_worker_handles_agent_run_exception(mock_agent, mock_session):
    """Test that worker handles exceptions from agent.run() properly."""
    # Mock agent.run to raise an exception
    test_exception = Exception("Test exception")
    mock_agent.run = AsyncMock(side_effect=test_exception)
    
    # Create SessionAgent and test request
    session_agent = SessionAgent(mock_agent, mock_session)
    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)
    
    # Mock the logger to verify exception logging
    with patch('hygroup.session.logger') as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)
        
        # Give the worker a moment to process the request
        await session_agent._queue.join()
        
        # Verify exception was logged
        mock_logger.exception.assert_called_once_with(test_exception)
        
        # Verify system response was sent
        mock_session.handle_system_response.assert_called_once_with(
            response="Execution of agent 'test_agent' failed.",
            receiver=sender
        )


@pytest.mark.asyncio
async def test_worker_handles_agent_run_success(mock_agent, mock_session):
    """Test that worker handles successful agent.run() properly."""
    # Mock agent.run to yield a successful response
    test_response = AgentResponse(text="Test response", final=True)
    mock_agent.run = AsyncMock()
    mock_agent.run.return_value.__aiter__ = AsyncMock(return_value=iter([test_response]))
    
    # Create SessionAgent and test request
    session_agent = SessionAgent(mock_agent, mock_session)
    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)
    
    # Mock the logger to verify no exception logging
    with patch('hygroup.session.logger') as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)
        
        # Give the worker a moment to process the request
        await session_agent._queue.join()
        
        # Verify no exception was logged
        mock_logger.exception.assert_not_called()
        
        # Verify agent response was handled
        mock_session.handle_agent_response.assert_called_once_with(
            response=test_response,
            sender="test_agent", 
            receiver=sender
        )
        
        # Verify system response was NOT called
        mock_session.handle_system_response.assert_not_called()


@pytest.mark.asyncio
async def test_worker_continues_after_exception(mock_agent, mock_session):
    """Test that worker continues processing after handling an exception."""
    # Create SessionAgent
    session_agent = SessionAgent(mock_agent, mock_session)
    sender = "test_user"
    
    # First request - will raise exception
    first_exception = Exception("First exception")
    mock_agent.run = AsyncMock(side_effect=first_exception)
    first_request = AgentRequest(query="first query", sender=sender)
    
    # Second request - will succeed
    second_response = AgentResponse(text="Second response", final=True)
    
    with patch('hygroup.session.logger') as mock_logger:
        # Invoke first request (will fail)
        await session_agent.invoke(first_request, secrets=None)
        
        # Give the worker a moment to process the first request
        await session_agent._queue.join()
        
        # Verify first exception was handled
        mock_logger.exception.assert_called_once_with(first_exception)
        assert mock_session.handle_system_response.call_count == 1
        
        # Now mock agent.run to succeed for second request
        mock_agent.run = AsyncMock()
        mock_agent.run.return_value.__aiter__ = AsyncMock(return_value=iter([second_response]))
        
        # Reset mocks for second request verification
        mock_logger.reset_mock()
        mock_session.reset_mock()
        
        # Invoke second request (will succeed)
        second_request = AgentRequest(query="second query", sender=sender)
        await session_agent.invoke(second_request, secrets=None)
        
        # Give the worker a moment to process the second request
        await session_agent._queue.join()
        
        # Verify second request was processed successfully
        mock_logger.exception.assert_not_called()
        mock_session.handle_agent_response.assert_called_once_with(
            response=second_response,
            sender="test_agent",
            receiver=sender
        )
        mock_session.handle_system_response.assert_not_called()


@pytest.mark.parametrize(
    "exception_type, exception_message",
    [
        (ValueError, "Invalid value"),
        (RuntimeError, "Runtime error occurred"), 
        (ConnectionError, "Connection failed"),
        (Exception, "Generic exception"),
    ]
)
@pytest.mark.asyncio
async def test_worker_handles_different_exception_types(mock_agent, mock_session, exception_type, exception_message):
    """Test that worker handles various exception types consistently."""
    # Mock agent.run to raise the specified exception
    test_exception = exception_type(exception_message)
    mock_agent.run = AsyncMock(side_effect=test_exception)
    
    # Create SessionAgent and test request
    session_agent = SessionAgent(mock_agent, mock_session)
    sender = "test_user"
    request = AgentRequest(query="test query", sender=sender)
    
    # Mock the logger to verify exception logging
    with patch('hygroup.session.logger') as mock_logger:
        # Invoke the agent with the request
        await session_agent.invoke(request, secrets=None)
        
        # Give the worker a moment to process the request
        await session_agent._queue.join()
        
        # Verify exception was logged
        mock_logger.exception.assert_called_once_with(test_exception)
        
        # Verify system response was sent with generic message regardless of exception type
        mock_session.handle_system_response.assert_called_once_with(
            response="Execution of agent 'test_agent' failed.",
            receiver=sender
        )