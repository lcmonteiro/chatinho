"""
Test doubles: stand-ins for what the tests must not reach for real.

- :mod:`fakes.llm`: a stubbed ``AsyncOpenAI`` that records every client and request.
- :mod:`fakes.agent`: a scripted LangChain chat model, deciding each call from its own run.
- :mod:`fakes.mcp`: a remote chatinho session served over MCP, a client onto it, and peers to ask.

No network and no key: every test runs offline.
"""
