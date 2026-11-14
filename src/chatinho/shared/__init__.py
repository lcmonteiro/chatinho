"""
What more than one specialization uses, a package or a module per domain.

``keys``, ``workspace``, ``memory`` and ``mcp`` are standard library only, so
either side can import them without the other's library. ``agent/`` is not: it
is what the agent connectors share, and it needs ``chatinho[langchain]``.

Shared code imports the framework (``session``, ``hooks``, ``message``,
``query``) and never a specialization.
"""
