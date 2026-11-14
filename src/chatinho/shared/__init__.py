"""
What more than one specialization uses, a package or a module per domain:
``keys``, ``workspace``, ``memory`` and ``mcp``.

Standard library only, so either side can import them without the other's
library. Shared code imports the framework (``session``, ``hooks``,
``message``, ``query``) and nothing else of chatinho: not a devkit, not a
specialization, and not another domain of its own.
"""
