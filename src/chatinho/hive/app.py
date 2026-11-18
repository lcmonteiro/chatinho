"""
The hive's HTTP side: the API a chat's backend speaks, the admin views and stream, and the page.

Every route under ``/api`` needs a key in ``X-Hive-Key`` (the stream also takes
``?key=``): a chat key acts on its own chat, an admin key reads every chat.
"""

from fastapi import FastAPI


def create_app(db_url: str) -> FastAPI:
    """
    The hive's application, over the database at *db_url*.

    Args:
        db_url: Any URL SQLAlchemy accepts.

    Returns:
        FastAPI: The app, with its routes, ``/docs`` and ``/openapi.json``.
    """
    raise NotImplementedError
