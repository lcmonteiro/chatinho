"""OpenAI connector for chatinho."""

import logging
from typing import Any, Optional
import openai

from ..chat_hooks import HookAsk, connector, require

logger = logging.getLogger(__name__)


@connector("openai")
@require(HookAsk)
class OpenAIConnector:
    """Connector for communicating with OpenAI API."""
    
    def __init__(
        self,
        name: str,
        api_key: str,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        self.name = name
        self.config = kwargs
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=api_key)
    
    def initialize(self):
        """Initialize the OpenAI connector by validating the API key."""
        logger.info(f"Initializing OpenAI connector '{self.name}' with model {self.model}")
        try:
            # Make a simple API call to validate the key
            self.client.models.list()
            logger.info(f"OpenAI connector '{self.name}' initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI connector '{self.name}': {e}")
            raise
    
    def ask(self, message: str, **kwargs) -> Any:
        """Ask the OpenAI model and return its reply.
        
        Args:
            message: The message to send
            **kwargs: Additional parameters including:
                - model: Override default model
                - temperature: Override default temperature
                - max_tokens: Override default max tokens
                - system_message: System message to prepend
                - conversation_history: Previous messages for context
                
        Returns:
            str: Response from OpenAI
        """
        logger.debug(f"Sending message via OpenAI connector '{self.name}': {message[:100]}...")
        
        # Prepare messages
        messages = []
        
        # Add system message if provided
        system_message = kwargs.get("system_message")
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        # Add conversation history if provided
        conversation_history = kwargs.get("conversation_history", [])
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        # Prepare request parameters
        params = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        if self.max_tokens is not None:
            params["max_tokens"] = kwargs.get("max_tokens", self.max_tokens)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(**params)
            
            # Extract the response text
            response_text = response.choices[0].message.content
            
            logger.debug(f"OpenAI response received: {response_text[:100]}...")
            return response_text
            
        except Exception as e:
            logger.error(f"Failed to send message via OpenAI connector '{self.name}': {e}")
            raise