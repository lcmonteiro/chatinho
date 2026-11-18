"""
The hive: the server every chat is kept and seen in.

A chat is a name and a key; ``HiveBackend`` writes its conversation,
attachments and traces here and reads them back, and an admin watches every
chat live from the page at ``/``. Run it with ``chatinho-hive serve``. It needs
``chatinho[hive]``: FastAPI, uvicorn and SQLAlchemy.
"""

# @req REQ-HIVE-010
try:
    import fastapi   # noqa: F401
    import sqlalchemy  # noqa: F401
    import uvicorn   # noqa: F401
except ImportError as exc:
    raise ImportError("The hive needs chatinho[hive] (pip install 'chatinho[hive]'): %s" % exc) from exc

from .app import create_app  # noqa: E402

__all__ = ["create_app"]
