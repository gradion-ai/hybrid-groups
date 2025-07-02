"""Storage abstractions for Slack Home data."""

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, Optional

from hygroup.gateway.slack_config.models import (
    ActivationPolicyViewModel,
    GlobalSecretViewModel,
    UserPreferencesViewModel,
    UserSecretViewModel,
)


class Store(ABC):
    """Base store interface."""

    @abstractmethod
    async def initialize(self):
        """Initialize the store."""
        pass


class SecretStore(Store):
    """Store for user and global secrets."""

    def __init__(self):
        self._user_secrets: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._global_secrets: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Initialize the store."""
        # Add demo secrets for testing
        self._user_secrets["U04NM1KQBJ6"] = {
            "USER_TOKEN": "xoxb-54321",
            "USER_APP_TOKEN": "xapp-12345",
        }
        self._global_secrets = {
            "SLACK_BOT_TOKEN": "xoxb-54321",
            "SLACK_APP_TOKEN": "xapp-12345",
        }

    # User secrets methods
    async def get_user_secrets(self, user_id: str) -> Dict[str, str]:
        """Get all secrets for a user."""
        return dict(self._user_secrets.get(user_id, {}))

    async def get_user_secret(self, user_id: str, key: str) -> Optional[str]:
        """Get a specific user secret."""
        return self._user_secrets.get(user_id, {}).get(key)

    async def set_user_secret(self, user_id: str, key: str, value: str) -> UserSecretViewModel:
        """Set a user secret."""
        self._user_secrets[user_id][key] = value
        self.logger.info(f"Set user secret for {user_id}: {key}")
        return UserSecretViewModel(user_id=user_id, key=key, value=value)

    async def delete_user_secret(self, user_id: str, key: str) -> bool:
        """Delete a user secret."""
        if user_id in self._user_secrets and key in self._user_secrets[user_id]:
            del self._user_secrets[user_id][key]
            self.logger.info(f"Deleted user secret for {user_id}: {key}")
            return True
        return False

    # Global secrets methods
    async def get_global_secrets(self) -> Dict[str, str]:
        """Get all global secrets."""
        return dict(self._global_secrets)

    async def get_global_secret(self, key: str) -> Optional[str]:
        """Get a specific global secret."""
        return self._global_secrets.get(key)

    async def set_global_secret(self, key: str, value: str) -> GlobalSecretViewModel:
        """Set a global secret."""
        self._global_secrets[key] = value
        self.logger.info(f"Set global secret: {key}")
        return GlobalSecretViewModel(key=key, value=value)

    async def delete_global_secret(self, key: str) -> bool:
        """Delete a global secret."""
        if key in self._global_secrets:
            del self._global_secrets[key]
            self.logger.info(f"Deleted global secret: {key}")
            return True
        return False


class ActivationPolicyStore(Store):
    """Store for activation policy."""

    def __init__(self):
        self._policy: Optional[ActivationPolicyViewModel] = None
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Initialize with demo policy."""
        demo_policy_content = """# System Activation Policy

## Overview
This document outlines the activation policy for our hybrid agent system. All users and agents must adhere to these guidelines when interacting with the system.

## Core Principles
1. **Responsible Use**: The system should be used for legitimate business purposes only
2. **Data Privacy**: All user data must be handled in accordance with our privacy policy
3. **Security**: Users must follow security best practices when configuring secrets and agents
4. **Compliance**: All activities must comply with applicable laws and regulations

## Agent Activation Guidelines
- Agents should be configured with clear, specific instructions
- Model configurations must be appropriate for the intended use case
- Human feedback should be enabled for sensitive operations
- Handoff capabilities should be used when multiple agents are needed

## User Responsibilities
- Keep all secrets and API keys secure and up to date
- Report any suspicious activity or security concerns
- Use appropriate agents for specific tasks
- Follow data handling guidelines

## System Limitations
- This is a demonstration system with limited capabilities
- Not suitable for production use without proper security review
- Users are responsible for ensuring compliance with their organization's policies

For questions or concerns, please contact your system administrator."""

        self._policy = ActivationPolicyViewModel(content=demo_policy_content)
        self.logger.info("Activation policy initialized with demo content")

    async def get(self) -> Optional[ActivationPolicyViewModel]:
        """Get the current activation policy."""
        return self._policy

    async def update(self, content: str) -> ActivationPolicyViewModel:
        """Update the activation policy."""
        self._policy = ActivationPolicyViewModel(content=content)
        self.logger.info("Activation policy updated")
        return self._policy


class UserPreferencesStore(Store):
    """Store for user preferences."""

    def __init__(self):
        self._preferences: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Initialize the store."""
        # No demo data for user preferences
        pass

    async def get(self, user_id: str) -> Optional[UserPreferencesViewModel]:
        """Get user preferences."""
        content = self._preferences.get(user_id)
        if content:
            return UserPreferencesViewModel(user_id=user_id, content=content)
        return None

    async def set(self, user_id: str, content: str) -> UserPreferencesViewModel:
        """Set user preferences."""
        self._preferences[user_id] = content
        self.logger.info(f"User preferences updated for {user_id}")
        return UserPreferencesViewModel(user_id=user_id, content=content)

    async def has_preferences(self, user_id: str) -> bool:
        """Check if user has preferences."""
        return user_id in self._preferences
