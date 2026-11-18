"""
``chatinho-hive``: serve the hive, and make its chats and admin keys.

    chatinho-hive serve [--db URL] [--host 127.0.0.1] [--port 8700]
    chatinho-hive chat add NAME | chat list | chat remove NAME [--db URL]
    chatinho-hive admin add [--db URL]

A key is printed once, when it is made, and never again: the hive keeps only
its hash.
"""

import argparse
import sys
from typing import List, Optional

#: The database a hive uses when none is named.
DEFAULT_DB : str = "sqlite:///hive.db"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatinho-hive",
                                     description="The hive: where every chat is kept and seen.")
    db     = argparse.ArgumentParser(add_help=False)
    db.add_argument("--db", default=DEFAULT_DB, help="the database URL (default: %(default)s)")
    verbs  = parser.add_subparsers(dest="verb", required=True)

    serve = verbs.add_parser("serve", parents=[db], help="run the hive")
    serve.add_argument("--host", default="127.0.0.1", help="where to listen (default: %(default)s)")
    serve.add_argument("--port", type=int, default=8700, help="the port (default: %(default)s)")

    chat  = verbs.add_parser("chat", help="the chats: a name and a key each")
    chats = chat.add_subparsers(dest="action", required=True)
    add   = chats.add_parser("add", parents=[db], help="make a chat and print its key, once")
    add.add_argument("name")
    chats.add_parser("list", parents=[db], help="every chat's name, never a key")
    remove = chats.add_parser("remove", parents=[db], help="delete a chat and everything kept for it")
    remove.add_argument("name")

    admin  = verbs.add_parser("admin", help="the admin keys, which read every chat")
    admins = admin.add_subparsers(dest="action", required=True)
    admins.add_parser("add", parents=[db], help="make an admin key and print it, once")
    return parser


# @req REQ-HIVE-001, REQ-HIVE-002, REQ-HIVE-010
def main(argv: Optional[List[str]] = None) -> int:
    """
    Runs one command; returns the exit status.

    Args:
        argv: The arguments after the program's name; ``sys.argv[1:]`` when None.
    """
    args = _parser().parse_args(argv)
    try:
        from .keys import hash_key, make_key
        from .store import NameTaken, Store
    except ImportError as exc:
        print("The hive needs chatinho[hive] (pip install 'chatinho[hive]'): %s" % exc, file=sys.stderr)
        return 2

    if args.verb == "serve":
        return _serve(args.db, args.host, args.port)

    store = Store(args.db)
    try:
        if args.verb == "chat" and args.action == "add":
            key = make_key()
            try:
                store.add_chat(args.name, hash_key(key))
            except NameTaken as exc:
                print("%s; pick another." % exc, file=sys.stderr)
                return 1
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print("Chat %s made. Its key, shown this once:" % args.name)
            print(key)
            return 0
        if args.verb == "chat" and args.action == "list":
            for chat in store.chats():
                print("%-24s made %s, %d messages" % (chat["name"], chat["created"][:19], chat["messages"]))
            return 0
        if args.verb == "chat" and args.action == "remove":
            if not store.remove_chat(args.name):
                print("No chat %r" % args.name, file=sys.stderr)
                return 1
            print("Chat %s removed, with everything kept for it." % args.name)
            return 0
        if args.verb == "admin" and args.action == "add":
            key = make_key()
            store.add_admin(hash_key(key))
            print("An admin key, shown this once:")
            print(key)
            return 0
    finally:
        store.close()
    return 2                                                            # pragma: no cover - argparse refuses


def _serve(db: str, host: str, port: int) -> int:
    import uvicorn

    from .app import create_app

    print("The hive at http://%s:%d/ (database %s)" % (host, port, db), flush=True)
    uvicorn.run(create_app(db), host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
