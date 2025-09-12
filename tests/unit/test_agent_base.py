from hygroup.agent.base import Attachment, Message, Thread


class TestAttachmentFromDicts:
    """Test Attachment.from_dicts static method."""

    def test_from_dicts_empty_list(self):
        """Test from_dicts with empty list."""
        result = Attachment.from_dicts([])
        assert result == []

    def test_from_dicts_single_attachment(self):
        """Test from_dicts with single attachment dictionary."""
        attachment_dict = {"path": "/tmp/file.txt", "name": "file.txt", "media_type": "text/plain"}
        result = Attachment.from_dicts([attachment_dict])

        assert len(result) == 1
        assert isinstance(result[0], Attachment)
        assert result[0].path == "/tmp/file.txt"
        assert result[0].name == "file.txt"
        assert result[0].media_type == "text/plain"

    def test_from_dicts_multiple_attachments(self):
        """Test from_dicts with multiple attachment dictionaries."""
        attachment_dicts = [
            {"path": "/tmp/doc.pdf", "name": "document.pdf", "media_type": "application/pdf"},
            {"path": "/tmp/image.jpg", "name": "photo.jpg", "media_type": "image/jpeg"},
            {"path": "/tmp/data.json", "name": "data.json", "media_type": "application/json"},
        ]
        result = Attachment.from_dicts(attachment_dicts)

        assert len(result) == 3
        for i, attachment in enumerate(result):
            assert isinstance(attachment, Attachment)
            assert attachment.path == attachment_dicts[i]["path"]
            assert attachment.name == attachment_dicts[i]["name"]
            assert attachment.media_type == attachment_dicts[i]["media_type"]


class TestMessageFromDict:
    """Test Message.from_dict static method, especially with attachments."""

    def test_from_dict_simple_message(self):
        """Test from_dict with simple message without threads or attachments."""
        message_dict = {
            "text": "Hello world",
            "sender": "alice",
            "receiver": "bob",
            "id": "msg123",
        }
        result = Message.from_dict(message_dict)

        assert isinstance(result, Message)
        assert result.text == "Hello world"
        assert result.sender == "alice"
        assert result.receiver == "bob"
        assert result.id == "msg123"
        assert result.threads == []
        assert result.attachments == []

    def test_from_dict_with_attachments(self):
        """Test from_dict properly converts attachment dictionaries to Attachment objects."""
        message_dict = {
            "text": "Message with attachments",
            "sender": "user1",
            "receiver": "agent1",
            "attachments": [
                {"path": "/tmp/doc.pdf", "name": "document.pdf", "media_type": "application/pdf"},
                {"path": "/tmp/image.png", "name": "screenshot.png", "media_type": "image/png"},
            ],
        }
        result = Message.from_dict(message_dict)

        assert isinstance(result, Message)
        assert result.text == "Message with attachments"
        assert len(result.attachments) == 2

        # Verify first attachment
        assert isinstance(result.attachments[0], Attachment)
        assert result.attachments[0].path == "/tmp/doc.pdf"
        assert result.attachments[0].name == "document.pdf"
        assert result.attachments[0].media_type == "application/pdf"

        # Verify second attachment
        assert isinstance(result.attachments[1], Attachment)
        assert result.attachments[1].path == "/tmp/image.png"
        assert result.attachments[1].name == "screenshot.png"
        assert result.attachments[1].media_type == "image/png"

    def test_from_dict_with_empty_attachments(self):
        """Test from_dict with empty attachments list."""
        message_dict = {
            "text": "Message with empty attachments",
            "sender": "user1",
            "receiver": "agent1",
            "attachments": [],
        }
        result = Message.from_dict(message_dict)

        assert isinstance(result, Message)
        assert result.attachments == []

    def test_from_dict_with_threads_and_attachments(self):
        """Test from_dict with both threads and attachments."""
        message_dict = {
            "text": "Complex message",
            "sender": "user1",
            "receiver": "agent1",
            "threads": [
                {
                    "session_id": "thread-1",
                    "messages": [
                        {
                            "text": "Nested message with attachment",
                            "sender": "user2",
                            "receiver": "agent2",
                            "attachments": [
                                {"path": "/tmp/nested.txt", "name": "nested.txt", "media_type": "text/plain"}
                            ],
                        }
                    ],
                }
            ],
            "attachments": [
                {"path": "/tmp/main.pdf", "name": "main.pdf", "media_type": "application/pdf"},
            ],
        }
        result = Message.from_dict(message_dict)

        assert isinstance(result, Message)
        assert result.text == "Complex message"

        # Verify main message attachment
        assert len(result.attachments) == 1
        assert isinstance(result.attachments[0], Attachment)
        assert result.attachments[0].path == "/tmp/main.pdf"

        # Verify thread
        assert len(result.threads) == 1
        assert isinstance(result.threads[0], Thread)
        assert result.threads[0].session_id == "thread-1"

        # Verify nested message attachment
        nested_message = result.threads[0].messages[0]
        assert len(nested_message.attachments) == 1
        assert isinstance(nested_message.attachments[0], Attachment)
        assert nested_message.attachments[0].path == "/tmp/nested.txt"

    def test_from_dict_no_attachments_field(self):
        """Test from_dict when attachments field is missing."""
        message_dict = {
            "text": "Message without attachments field",
            "sender": "user1",
            "receiver": "agent1",
        }
        result = Message.from_dict(message_dict)

        assert isinstance(result, Message)
        assert result.attachments == []

    def test_from_dict_mixed_complex_scenario(self):
        """Test from_dict with a complex real-world scenario mixing threads and attachments."""
        message_dict = {
            "text": "Project discussion with files",
            "sender": "project_manager",
            "receiver": "development_team",
            "id": "proj-msg-001",
            "attachments": [
                {"path": "/uploads/spec.pdf", "name": "requirements.pdf", "media_type": "application/pdf"},
                {"path": "/uploads/mockup.png", "name": "ui_mockup.png", "media_type": "image/png"},
            ],
            "threads": [
                {
                    "session_id": "technical-discussion",
                    "messages": [
                        {
                            "text": "Technical analysis",
                            "sender": "tech_lead",
                            "receiver": "developers",
                            "attachments": [
                                {
                                    "path": "/tech/analysis.json",
                                    "name": "analysis.json",
                                    "media_type": "application/json",
                                }
                            ],
                        },
                        {
                            "text": "Architecture proposal",
                            "sender": "architect",
                            "receiver": "tech_lead",
                            "attachments": [
                                {"path": "/arch/diagram.svg", "name": "architecture.svg", "media_type": "image/svg+xml"}
                            ],
                            "threads": [
                                {
                                    "session_id": "detailed-review",
                                    "messages": [
                                        {
                                            "text": "Detailed review comments",
                                            "sender": "senior_dev",
                                            "receiver": "architect",
                                            "attachments": [
                                                {
                                                    "path": "/reviews/comments.md",
                                                    "name": "review_comments.md",
                                                    "media_type": "text/markdown",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            ],
        }

        result = Message.from_dict(message_dict)

        # Verify main message
        assert result.text == "Project discussion with files"
        assert result.sender == "project_manager"
        assert len(result.attachments) == 2
        assert result.attachments[0].name == "requirements.pdf"
        assert result.attachments[1].name == "ui_mockup.png"

        # Verify thread structure
        assert len(result.threads) == 1
        tech_thread = result.threads[0]
        assert tech_thread.session_id == "technical-discussion"
        assert len(tech_thread.messages) == 2

        # Verify first nested message
        analysis_msg = tech_thread.messages[0]
        assert analysis_msg.text == "Technical analysis"
        assert len(analysis_msg.attachments) == 1
        assert analysis_msg.attachments[0].name == "analysis.json"

        # Verify second nested message with deeper nesting
        proposal_msg = tech_thread.messages[1]
        assert proposal_msg.text == "Architecture proposal"
        assert len(proposal_msg.attachments) == 1
        assert proposal_msg.attachments[0].name == "architecture.svg"
        assert len(proposal_msg.threads) == 1

        # Verify deeply nested message
        review_thread = proposal_msg.threads[0]
        assert review_thread.session_id == "detailed-review"
        assert len(review_thread.messages) == 1
        review_msg = review_thread.messages[0]
        assert review_msg.text == "Detailed review comments"
        assert len(review_msg.attachments) == 1
        assert review_msg.attachments[0].name == "review_comments.md"
        assert review_msg.attachments[0].media_type == "text/markdown"
