"""
Small pieces shared by more than one connector or frontend.

``memory`` and ``mcp`` are standard library only, so either side can import them
without the other's library. ``agent/`` is not: it is what the agent connectors
share, and it needs ``chatinho[langchain]``.
"""
