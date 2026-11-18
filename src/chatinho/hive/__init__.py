"""
The hive: the server every chat is kept and seen in.

A chat is a name and a key; ``HiveBackend`` writes its conversation,
attachments and traces here and reads them back, and an admin watches every
chat live from the page at ``/``. Run it with ``chatinho-hive serve``. It needs
``chatinho[hive]``: FastAPI, uvicorn and SQLAlchemy.
"""

from .app import create_app

__all__ = ["create_app"]
