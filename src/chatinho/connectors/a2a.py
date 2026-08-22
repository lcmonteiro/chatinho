"""A2A (Agent-to-Agent) connector for chatinho."""

import json
import logging
from typing import Any, Dict, Optional
import requests

from .base import BaseConnector

logger = logging.getLogger(__name__)


class A2AConnector(BaseConnector):
    """Connector for communicating with A2A (Agent-to-Agent) protocol endpoints."""
    
    def __init__(
        self,
        name: str,
        url: str,
        api_key: str,
        timeout: int = 30,
        **kwargs
    ):
        super().__init__(name, url=url, api_key=api_key, timeout=timeout, **kwargs)
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
    
    def initialize(self):
        """Initialize the A2A connector by testing the connection."""
        logger.info(f"Initializing A2A connector '{self.name}' connecting to {self.url}")
        try:
            # Try to get the agent card or make a simple request to verify connectivity
            response = self.session.get(f"{self.url}/.well-known/agent-card.json", timeout=self.timeout)
            if response.status_code == 200:
                logger.info(f"A2A connector '{self.name}' successfully connected to {self.url}")
                agent_card = response.json()
                logger.debug(f"Agent card received: {agent_card.get('name', 'Unknown')}")
            else:
                logger.warning(f"A2A connector '{self.name}' received status {response.status_code} from {self.url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not connect to A2A endpoint during initialization: {e}")
            # Don't fail initialization - allow for lazy connection
    
    def send(self, message: str, **kwargs) -> Any:
        """Send a message via A2A protocol.
        
        Args:
            message: The message to send
            **kwargs: Additional parameters including:
                - context_id: Optional context ID for conversation continuity
                - task_id: Optional task ID if this is part of an ongoing task
                - streaming: Whether to expect a streaming response
                
        Returns:
            Dict: Response from the A2A agent
        """
        logger.debug(f"Sending message via A2A connector '{self.name}': {message[:100]}...")
        
        # Prepare A2A SendMessageRequest
        request_data = {
            "message": {
                "parts": [
                    {
                        "type": "text",
                        "text": message
                    }
                ],
                "role": "user"
            }
        }
        
        # Add optional context if provided
        if "context_id" in kwargs:
            request_data["message"]["contextId"] = kwargs["context_id"]
        
        if "task_id" in kwargs:
            request_data["taskId"] = kwargs["task_id"]
        
        try:
            # Send to A2A agent's message endpoint
            response = self.session.post(
                f"{self.url}/message/send",
                json=request_data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"A2A response received: {str(result)[:200]}...")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send message via A2A connector '{self.name}': {e}")
            raise
    
    def receive(self, **kwargs) -> Any:
        """Receive messages (not typically used in A2A as it's request/response).
        
        For A2A, receiving is usually done through the send method's response
        or through webhook/push notification endpoints.
        
        Args:
            **kwargs: Additional parameters
            
        Returns:
            Any: Received data or None
        """
        logger.debug("A2A receive method called - A2A is primarily request/response")
        # This would be implemented for webhook/push notification scenarios
        return None