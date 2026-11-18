"""
``chatinho-hive``: serve the hive, and make its chats and admin keys.

    chatinho-hive serve [--db URL] [--host 127.0.0.1] [--port 8700]
    chatinho-hive chat add NAME | chat list | chat remove NAME [--db URL]
    chatinho-hive admin add [--db URL]
"""

from typing import List, Optional

#: The database a hive uses when none is named.
DEFAULT_DB : str = "sqlite:///hive.db"


def main(argv: Optional[List[str]] = None) -> int:
    """
    Runs one command; returns the exit status.

    Args:
        argv: The arguments after the program's name; ``sys.argv[1:]`` when None.
    """
    raise NotImplementedError
