from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hygroup.agent import Thread
from hygroup.session import SessionManager


@pytest.fixture
def session_manager():
    """Create a SessionManager with mocked dependencies."""
    manager = SessionManager(
        agent_registry=MagicMock(),
        user_registry=MagicMock(),
        permission_store=MagicMock(),
        preferences_store=MagicMock(),
        request_handler=MagicMock(),
        composio_config=MagicMock(),
        root_dir=MagicMock(),
    )
    return manager


@pytest.mark.asyncio
async def test_load_thread_simple(session_manager):
    """Test loading a simple thread without nested threads."""
    session_id = "test-session-1"

    # Create test data
    state = {
        "messages": [
            {"text": "Hello", "sender": "user1", "receiver": "agent1", "threads": [], "id": "msg1"},
            {"text": "Hi there", "sender": "agent1", "receiver": "user1", "threads": [], "id": "msg2"},
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify the thread
        assert thread.session_id == session_id
        assert len(thread.messages) == 2
        assert thread.messages[0].text == "Hello"
        assert thread.messages[0].sender == "user1"
        assert thread.messages[0].receiver == "agent1"
        assert thread.messages[0].threads == []
        assert thread.messages[1].text == "Hi there"
        assert thread.messages[1].sender == "agent1"
        assert thread.messages[1].receiver == "user1"
        assert thread.messages[1].threads == []


@pytest.mark.asyncio
async def test_load_thread_with_one_level_nesting(session_manager):
    """Test loading a thread with one level of nested threads."""
    session_id = "test-session-2"

    # Create test data with nested threads
    state = {
        "messages": [
            {
                "text": "Main message",
                "sender": "user1",
                "receiver": "agent1",
                "threads": [
                    {
                        "session_id": "nested-session-1",
                        "messages": [
                            {
                                "text": "Nested message 1",
                                "sender": "user2",
                                "receiver": "agent2",
                                "threads": [],
                                "id": "nested-msg1",
                            }
                        ],
                    }
                ],
                "id": "msg1",
            }
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify the main thread
        assert thread.session_id == session_id
        assert len(thread.messages) == 1
        assert thread.messages[0].text == "Main message"

        # Verify the nested thread
        assert len(thread.messages[0].threads) == 1
        nested_thread = thread.messages[0].threads[0]
        assert isinstance(nested_thread, Thread)
        assert nested_thread.session_id == "nested-session-1"
        assert len(nested_thread.messages) == 1
        assert nested_thread.messages[0].text == "Nested message 1"
        assert nested_thread.messages[0].sender == "user2"
        assert nested_thread.messages[0].receiver == "agent2"


@pytest.mark.asyncio
async def test_load_thread_with_multiple_levels_nesting(session_manager):
    """Test loading a thread with multiple levels of nested threads."""
    session_id = "test-session-3"

    # Create test data with deeply nested threads
    state = {
        "messages": [
            {
                "text": "Level 0 message",
                "sender": "user0",
                "receiver": "agent0",
                "threads": [
                    {
                        "session_id": "level-1-session",
                        "messages": [
                            {
                                "text": "Level 1 message",
                                "sender": "user1",
                                "receiver": "agent1",
                                "threads": [
                                    {
                                        "session_id": "level-2-session",
                                        "messages": [
                                            {
                                                "text": "Level 2 message",
                                                "sender": "user2",
                                                "receiver": "agent2",
                                                "threads": [],
                                                "id": "level2-msg",
                                            }
                                        ],
                                    }
                                ],
                                "id": "level1-msg",
                            }
                        ],
                    }
                ],
                "id": "level0-msg",
            }
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify level 0
        assert thread.session_id == session_id
        assert len(thread.messages) == 1
        assert thread.messages[0].text == "Level 0 message"

        # Verify level 1
        assert len(thread.messages[0].threads) == 1
        level1_thread = thread.messages[0].threads[0]
        assert isinstance(level1_thread, Thread)
        assert level1_thread.session_id == "level-1-session"
        assert len(level1_thread.messages) == 1
        assert level1_thread.messages[0].text == "Level 1 message"

        # Verify level 2
        assert len(level1_thread.messages[0].threads) == 1
        level2_thread = level1_thread.messages[0].threads[0]
        assert isinstance(level2_thread, Thread)
        assert level2_thread.session_id == "level-2-session"
        assert len(level2_thread.messages) == 1
        assert level2_thread.messages[0].text == "Level 2 message"
        assert level2_thread.messages[0].threads == []


@pytest.mark.asyncio
async def test_load_thread_with_multiple_nested_threads(session_manager):
    """Test loading a thread with multiple nested threads at the same level."""
    session_id = "test-session-4"

    # Create test data with multiple nested threads
    state = {
        "messages": [
            {
                "text": "Main message with multiple threads",
                "sender": "user1",
                "receiver": "agent1",
                "threads": [
                    {
                        "session_id": "nested-1",
                        "messages": [
                            {
                                "text": "First nested",
                                "sender": "user2",
                                "receiver": "agent2",
                                "threads": [],
                                "id": "nested1-msg",
                            }
                        ],
                    },
                    {
                        "session_id": "nested-2",
                        "messages": [
                            {
                                "text": "Second nested",
                                "sender": "user3",
                                "receiver": "agent3",
                                "threads": [],
                                "id": "nested2-msg",
                            }
                        ],
                    },
                    {
                        "session_id": "nested-3",
                        "messages": [
                            {
                                "text": "Third nested",
                                "sender": "user4",
                                "receiver": "agent4",
                                "threads": [],
                                "id": "nested3-msg",
                            }
                        ],
                    },
                ],
                "id": "main-msg",
            }
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify the main thread
        assert thread.session_id == session_id
        assert len(thread.messages) == 1
        assert thread.messages[0].text == "Main message with multiple threads"

        # Verify all nested threads
        assert len(thread.messages[0].threads) == 3

        # Check first nested thread
        assert thread.messages[0].threads[0].session_id == "nested-1"
        assert thread.messages[0].threads[0].messages[0].text == "First nested"

        # Check second nested thread
        assert thread.messages[0].threads[1].session_id == "nested-2"
        assert thread.messages[0].threads[1].messages[0].text == "Second nested"

        # Check third nested thread
        assert thread.messages[0].threads[2].session_id == "nested-3"
        assert thread.messages[0].threads[2].messages[0].text == "Third nested"


@pytest.mark.asyncio
async def test_load_thread_empty_threads_list(session_manager):
    """Test loading a thread where messages have empty threads lists."""
    session_id = "test-session-5"

    state = {
        "messages": [
            {"text": "Message with empty threads", "sender": "user1", "receiver": "agent1", "threads": [], "id": "msg1"}
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify
        assert thread.session_id == session_id
        assert len(thread.messages) == 1
        assert thread.messages[0].threads == []


@pytest.mark.asyncio
async def test_load_thread_missing_threads_field(session_manager):
    """Test loading a thread where messages don't have a threads field."""
    session_id = "test-session-6"

    state = {
        "messages": [
            {
                "text": "Message without threads field",
                "sender": "user1",
                "receiver": "agent1",
                "id": "msg1",
                # Note: no "threads" field
            }
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify - should default to empty list
        assert thread.session_id == session_id
        assert len(thread.messages) == 1
        assert thread.messages[0].threads == []


@pytest.mark.asyncio
async def test_load_threads_multiple_sessions(session_manager):
    """Test loading multiple threads using load_threads method."""
    # Create multiple sessions with nested threads
    session_ids = ["session-a", "session-b", "session-c"]

    # Create states for each session
    states = {}
    for i, session_id in enumerate(session_ids):
        states[session_id] = {
            "messages": [
                {
                    "text": f"Message in {session_id}",
                    "sender": f"user{i}",
                    "receiver": f"agent{i}",
                    "threads": [
                        {
                            "session_id": f"nested-{session_id}",
                            "messages": [
                                {
                                    "text": f"Nested in {session_id}",
                                    "sender": "nested-user",
                                    "receiver": "nested-agent",
                                    "threads": [],
                                    "id": f"nested-msg-{i}",
                                }
                            ],
                        }
                    ]
                    if i > 0
                    else [],  # First session has no nested threads
                    "id": f"msg-{i}",
                }
            ],
            "agents": {},
        }

    # Mock session_saved to return True for all sessions
    # Mock load_session_state to return the appropriate state for each session
    async def mock_load_state(sid):
        return states[sid]

    with (
        patch.object(session_manager, "session_saved", AsyncMock(return_value=True)),
        patch.object(session_manager, "load_session_state", AsyncMock(side_effect=mock_load_state)),
    ):
        # Load all threads
        threads = await session_manager.load_threads(session_ids)

        # Verify
        assert len(threads) == 3

        # First thread has no nested threads
        assert threads[0].session_id == "session-a"
        assert threads[0].messages[0].threads == []

        # Second and third threads have nested threads
        for i in [1, 2]:
            assert threads[i].session_id == session_ids[i]
            assert len(threads[i].messages[0].threads) == 1
            nested = threads[i].messages[0].threads[0]
            assert isinstance(nested, Thread)
            assert nested.session_id == f"nested-{session_ids[i]}"
            assert nested.messages[0].text == f"Nested in {session_ids[i]}"


@pytest.mark.asyncio
async def test_load_thread_complex_real_world_scenario(session_manager):
    """Test a complex real-world scenario with mixed nesting and multiple messages."""
    session_id = "main-discussion"

    # Simulate a complex conversation with references to other threads
    state = {
        "messages": [
            {"text": "Let's discuss the project", "sender": "alice", "receiver": "bob", "threads": [], "id": "msg1"},
            {
                "text": "Sure, here are the details from our previous discussion",
                "sender": "bob",
                "receiver": "alice",
                "threads": [
                    {
                        "session_id": "prev-discussion-1",
                        "messages": [
                            {
                                "text": "Previous point 1",
                                "sender": "charlie",
                                "receiver": "dave",
                                "threads": [],
                                "id": "prev1",
                            },
                            {
                                "text": "Previous response 1",
                                "sender": "dave",
                                "receiver": "charlie",
                                "threads": [
                                    {
                                        "session_id": "even-earlier",
                                        "messages": [
                                            {
                                                "text": "Historical context",
                                                "sender": "eve",
                                                "receiver": "frank",
                                                "threads": [],
                                                "id": "hist1",
                                            }
                                        ],
                                    }
                                ],
                                "id": "prev2",
                            },
                        ],
                    },
                    {
                        "session_id": "prev-discussion-2",
                        "messages": [
                            {
                                "text": "Another thread of discussion",
                                "sender": "george",
                                "receiver": "helen",
                                "threads": [],
                                "id": "another1",
                            }
                        ],
                    },
                ],
                "id": "msg2",
            },
            {"text": "Thanks for the context", "sender": "alice", "receiver": "bob", "threads": [], "id": "msg3"},
        ],
        "agents": {},
    }

    # Mock load_session_state to return test data
    with patch.object(session_manager, "load_session_state", AsyncMock(return_value=state)):
        # Load the thread
        thread = await session_manager.load_thread(session_id)

        # Verify the structure
        assert thread.session_id == session_id
        assert len(thread.messages) == 3

        # First message has no threads
        assert thread.messages[0].threads == []

        # Second message has two nested threads
        assert len(thread.messages[1].threads) == 2

        # First nested thread has deeper nesting
        first_nested = thread.messages[1].threads[0]
        assert first_nested.session_id == "prev-discussion-1"
        assert len(first_nested.messages) == 2
        assert first_nested.messages[0].threads == []
        assert len(first_nested.messages[1].threads) == 1

        # Check the deeply nested thread
        deeply_nested = first_nested.messages[1].threads[0]
        assert isinstance(deeply_nested, Thread)
        assert deeply_nested.session_id == "even-earlier"
        assert deeply_nested.messages[0].text == "Historical context"

        # Second nested thread is simpler
        second_nested = thread.messages[1].threads[1]
        assert second_nested.session_id == "prev-discussion-2"
        assert len(second_nested.messages) == 1

        # Third message has no threads
        assert thread.messages[2].threads == []
