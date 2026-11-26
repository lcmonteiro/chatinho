"""
What a specialization is built from, a package per kind: ``agent/`` is the whole
chat around an agent, and a connector only picks a factory.

A kit imports the framework and the parts, never a specialization, and
may need an extra: ``agent/`` needs ``chatinho[langchain]``, and ``model/``, the one
model every component calls, ``chatinho[openai]``.
"""
