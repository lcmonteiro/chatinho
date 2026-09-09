"""A2A (Agent-to-Agent) connector for chatinho."""

import logging
from typing import Any, Dict
import requests

from ..chat_hooks import HookAnswer, connector, require

logger = logging.getLogger(__name__)


@connector("a2a")
@require(HookAnswer)
class A2AConnector:
    """Connector for communicating with A2A (Agent-to-Agent) protocol endpoints."""
    
    def __init__(
        self,
        name: str,
        url: str,
        api_key: str,
        timeout: int = 30,
        **kwargs
    ):
        self.name = name
        self.config = kwargs
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
                logger.warning(
                    f"A2A connector '{self.name}' received status {response.status_code} from {self.url}"
                )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not connect to A2A endpoint during initialization: {e}")
            # Don't fail initialization - allow for lazy connection
    
    async def answer(self, msg: Any, **kwargs) -> Any:
        """Ask the A2A agent and return its answer.
        
        Args:
            msg: The question; its text is what goes out
            **kwargs: Additional parameters including:
                - context_id: Optional context ID for conversation continuity
                - task_id: Optional task ID if this is part of an ongoing task
                - streaming: Whether to expect a streaming response
                
        Returns:
            Dict: Response from the A2A agent
        """
        logger.debug(f"Answering via A2A connector '{self.name}': {msg.text[:100]}...")
        
        # Prepare A2A SendMessageRequest
        request_data: Dict[str, Any] = {
            "message": {
                "parts": [
                    {
                        "type": "text",
                        "text": msg.text
                    }
                ],
                "role": "user"
            }
        }
        
        # Add optional context if provided
        if "context_id" in kwargs:
            request_data["message"]["contextId"] = kwargs["context_id"]
        
        if "task_id" in kwargs:
            # Beside contextId, inside the message: both are fields of the A2A
            # Message object, not of the request envelope. At the top level a
            # spec-conformant agent never sees it and treats every turn as a
            # new task — which breaks the correlation the inbound direction
            # depends on.
            request_data["message"]["taskId"] = kwargs["task_id"]
        
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