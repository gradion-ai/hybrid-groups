# Slack Gateway Testing Strategy

## Overview

This document outlines a comprehensive testing strategy for the Slack gateway implementation in the `hygroup/gateway/slack.py` module. The strategy covers unit tests, integration tests, and testing best practices specifically tailored for Slack applications using the `slack-bolt` and `slack-sdk` libraries.

## Dependencies and Testing Stack

Based on the project's current dependencies:
- **Testing Framework**: `pytest` with `pytest-asyncio` for async testing
- **Mocking**: Python's built-in `unittest.mock` (no separate Slack test kit available)
- **Slack Dependencies**: `slack-bolt ^1.23.0`, `slack-sdk ^3.35.0`, `markdown-to-mrkdwn ^0.2.0`
- **Coverage**: `pytest-cov` for coverage reporting

## Testing Structure

### Directory Organization
```
tests/
├── unit/
│   └── gateway/
│       ├── test_slack_gateway.py
│       ├── test_slack_thread.py
│       └── test_slack_message_parsing.py
├── integration/
│   └── test_slack_gateway_integration.py
└── fixtures/
    └── slack_fixtures.py
```

## Unit Testing Strategy

### 1. SlackGateway Class Tests

#### Test Categories:

**A. Initialization and Configuration**
```python
class TestSlackGatewayInitialization:
    def test_initialization_with_valid_params(self):
        # Test gateway initialization with proper dependencies
    
    def test_initialization_with_user_mapping(self):
        # Test user mapping configuration
    
    def test_environment_variable_requirements(self):
        # Test that required env vars (SLACK_BOT_TOKEN, SLACK_APP_TOKEN) are handled
```

**B. Message Parsing and Processing**
```python
class TestSlackMessageParsing:
    @pytest.mark.parametrize("slack_message,expected_parsed", [
        # Test cases for various Slack message formats
    ])
    def test_parse_slack_message(self, slack_message, expected_parsed):
        # Test _parse_slack_message method
    
    def test_resolve_user_mappings(self):
        # Test _resolve_core_user_id and _resolve_slack_user_id
    
    def test_extract_mentions_and_thread_refs(self):
        # Test mention extraction and thread reference parsing
```

**C. Thread Management**
```python
class TestSlackThreadManagement:
    def test_register_slack_thread(self):
        # Test thread registration and session management
    
    def test_thread_history_loading(self):
        # Test _load_thread_history with mocked API calls
    
    def test_concurrent_thread_access(self):
        # Test thread locking mechanism
```

**D. Event Handling**
```python
class TestSlackEventHandling:
    @patch('hygroup.gateway.slack.AsyncWebClient')
    async def test_handle_slack_message_new_thread(self, mock_client):
        # Test handling new thread creation
    
    @patch('hygroup.gateway.slack.AsyncWebClient')
    async def test_handle_slack_message_existing_thread(self, mock_client):
        # Test handling messages in existing threads
    
    async def test_handle_agent_response(self):
        # Test agent response formatting and posting
```

### 2. SlackThread Class Tests

```python
class TestSlackThread:
    async def test_handle_message_new_message(self):
        # Test handling new messages
    
    async def test_handle_message_duplicate_prevention(self):
        # Test duplicate message handling
    
    async def test_agent_invocation(self):
        # Test agent invocation logic
    
    async def test_concurrent_message_handling(self):
        # Test lock mechanism in message handling
```

### 3. Mock Strategy for Slack SDK Components

#### AsyncWebClient Mocking
```python
@pytest.fixture
def mock_slack_client():
    with patch('hygroup.gateway.slack.AsyncWebClient') as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        
        # Configure common API responses
        mock_instance.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        mock_instance.conversations_replies.return_value = {
            "messages": [],
            "has_more": False
        }
        
        yield mock_instance
```

#### AsyncApp and SocketModeHandler Mocking
```python
@pytest.fixture
def mock_slack_app():
    with patch('hygroup.gateway.slack.AsyncApp') as mock_app, \
         patch('hygroup.gateway.slack.AsyncSocketModeHandler') as mock_handler:
        
        app_instance = AsyncMock()
        handler_instance = AsyncMock()
        
        mock_app.return_value = app_instance
        mock_handler.return_value = handler_instance
        
        # Mock event handler registration
        app_instance.message.return_value = AsyncMock()
        
        yield app_instance, handler_instance
```

### 4. Test Data and Fixtures

```python
# tests/fixtures/slack_fixtures.py

@pytest.fixture
def sample_slack_message():
    return {
        "type": "message",
        "user": "U1234567890",
        "text": "@agent_name Hello, how are you?",
        "ts": "1234567890.123456",
        "channel": "C1234567890",
        "thread_ts": "1234567890.000000"
    }

@pytest.fixture
def sample_thread_history():
    return {
        "messages": [
            {
                "type": "message",
                "user": "U1234567890",
                "text": "Hello",
                "ts": "1234567890.123456"
            },
            {
                "type": "message",
                "user": "U0987654321",
                "text": "Hi there!",
                "ts": "1234567890.123457"
            }
        ],
        "has_more": False
    }

@pytest.fixture
def user_mapping():
    return {
        "U1234567890": "user1",
        "U0987654321": "agent_name"
    }
```

## Integration Testing Strategy

### 1. End-to-End Message Flow Tests

```python
class TestSlackGatewayIntegration:
    async def test_complete_message_flow(self):
        """Test complete flow from Slack message to agent response"""
        # Setup gateway with real session manager
        # Send mock Slack message
        # Verify session creation, agent invocation, and response posting
    
    async def test_multi_user_conversation(self):
        """Test conversation with multiple users and agents"""
        # Test complex conversation scenarios
    
    async def test_thread_persistence(self):
        """Test thread persistence across gateway restarts"""
        # Test session loading and restoration
```

### 2. Error Handling and Edge Cases

```python
class TestSlackGatewayErrorHandling:
    async def test_slack_api_errors(self):
        """Test handling of various Slack API errors"""
        # Test rate limiting, network errors, auth failures
    
    async def test_malformed_messages(self):
        """Test handling of malformed or unexpected message formats"""
        # Test robustness against edge cases
    
    async def test_concurrent_access_scenarios(self):
        """Test high-concurrency scenarios"""
        # Test thread safety and race conditions
```

## Performance Testing

### 1. Load Testing Strategy

```python
class TestSlackGatewayPerformance:
    async def test_message_throughput(self):
        """Test gateway performance under message load"""
        # Simulate high message volume
    
    async def test_thread_scalability(self):
        """Test performance with many concurrent threads"""
        # Test memory usage and response times
    
    async def test_history_loading_performance(self):
        """Test performance of loading large thread histories"""
        # Test with large conversation histories
```

## Security Testing

### 1. Authentication and Authorization

```python
class TestSlackGatewaySecurity:
    def test_token_validation(self):
        """Test proper token handling and validation"""
        # Test token security measures
    
    def test_user_mapping_security(self):
        """Test user mapping and access control"""
        # Test user resolution security
    
    def test_message_sanitization(self):
        """Test message content sanitization"""
        # Test XSS and injection prevention
```

## Test Implementation Examples

### Example 1: Message Parsing Test

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from hygroup.gateway.slack import SlackGateway

class TestSlackMessageParsing:
    def setup_method(self):
        self.mock_session_manager = Mock()
        self.user_mapping = {"U1234": "user1", "U5678": "agent1"}
        
        with patch.dict('os.environ', {
            'SLACK_BOT_TOKEN': 'xoxb-test-token',
            'SLACK_APP_TOKEN': 'xapp-test-token'
        }):
            self.gateway = SlackGateway(
                session_manager=self.mock_session_manager,
                user_mapping=self.user_mapping
            )
    
    def test_parse_slack_message_with_mention(self):
        slack_message = {
            "user": "U1234",
            "text": "@agent1 Hello there!",
            "ts": "1234567890.123456",
            "channel": "C1234567890"
        }
        
        parsed = self.gateway._parse_slack_message(slack_message)
        
        assert parsed["sender"] == "U1234"
        assert parsed["sender_resolved"] == "user1"
        assert parsed["receiver"] == "agent1"
        assert parsed["receiver_resolved"] == "agent1"
        assert parsed["text"] == "Hello there!"
        assert parsed["id"] == "1234567890.123456"
```

### Example 2: Agent Response Test

```python
class TestSlackAgentResponse:
    @patch('hygroup.gateway.slack.AsyncWebClient')
    async def test_handle_agent_response_with_handoffs(self, mock_client_class):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Setup gateway and mock thread
        gateway = SlackGateway(Mock(), {"user1": "U1234"})
        gateway._threads["thread123"] = Mock()
        gateway._threads["thread123"].channel = "C1234567890"
        gateway._threads["thread123"].id = "thread123"
        
        # Create agent response with handoffs
        response = Mock()
        response.text = "Here's my response"
        response.handoffs = {"agent2": "Please continue this task"}
        
        await gateway.handle_agent_response(
            response=response,
            sender="agent1",
            receiver="user1",
            session_id="thread123"
        )
        
        # Verify message was posted with correct formatting
        mock_client.chat_postMessage.assert_called_once()
        call_args = mock_client.chat_postMessage.call_args
        
        assert "Here's my response" in call_args.kwargs["text"]
        assert "Handoffs:" in call_args.kwargs["text"]
        assert "agent2" in call_args.kwargs["text"]
```

## Test Coverage Goals

### Coverage Targets
- **Overall Coverage**: >90%
- **Critical Paths**: 100% (message handling, agent invocation)
- **Error Handling**: 100%
- **Edge Cases**: >95%

### Coverage Areas
1. **Message Processing Pipeline**: 100%
2. **Thread Management**: 95%
3. **User Resolution**: 100%
4. **API Error Handling**: 100%
5. **Concurrency Control**: 90%

## Continuous Integration

### Test Execution Strategy
```yaml
# Example CI configuration
test_matrix:
  - unit_tests: "invoke ut --cov"
  - integration_tests: "invoke it --cov"
  - performance_tests: "pytest tests/performance/ -v"
```

### Mock Environment Setup
```python
# CI environment variables for testing
TEST_ENV_VARS = {
    'SLACK_BOT_TOKEN': 'xoxb-test-token',
    'SLACK_APP_TOKEN': 'xapp-test-token',
    'SLACK_SIGNING_SECRET': 'test-signing-secret'
}
```

## Best Practices Summary

1. **Isolation**: Mock all external Slack API calls
2. **Async Testing**: Use `pytest-asyncio` for all async components
3. **Fixtures**: Reuse common test data and mock configurations
4. **Parameterization**: Test multiple scenarios efficiently
5. **Error Simulation**: Test failure modes extensively
6. **Performance**: Include performance benchmarks
7. **Documentation**: Document test scenarios and expected behaviors
8. **Maintenance**: Keep tests aligned with Slack API changes

## Implementation Priority

### Phase 1: Core Unit Tests
1. Message parsing and user resolution
2. Thread management basics
3. Agent response handling

### Phase 2: Integration Tests
1. End-to-end message flows
2. Session persistence
3. Error handling scenarios

### Phase 3: Advanced Testing
1. Performance and load testing
2. Security testing
3. Concurrency testing

This testing strategy provides comprehensive coverage for the Slack gateway while following industry best practices for testing Slack applications with the Python SDK and Bolt framework.