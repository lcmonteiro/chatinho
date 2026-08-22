"""Connectors for chatinho."""

from .base import BaseConnector
from .a2a import A2AConnector
from .openai import OpenAIConnector

__all__ = [
    "BaseConnector",
    "A2AConnector",
    "OpenAIConnector",
]