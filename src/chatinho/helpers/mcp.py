"""What ``McpFrontend`` and ``McpConnector`` agree on: the credentials key and attachments.

Standard library only, so either end can import it without the other.
"""

import base64
import mimetypes
from typing import Any, Dict

from chatinho.chat_message import Attachment

#: Where a client puts the credentials it lends, in a request's ``_meta``, and
#: the capability extension a server declares the ones it accepts under.
CREDENTIALS_KEY : str = "chatinho/credentials"


def media_type_of(name: str) -> str:
    """The media type a file called *name* most likely holds."""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def encode(item: Attachment) -> Dict[str, str]:
    """An attachment as JSON: its name, media type and base64 content."""
    return {
        "name"       : item.name,
        "media_type" : item.media_type,
        "data_b64"   : base64.b64encode(item.data).decode("ascii"),
    }


def decode(data: Dict[str, Any]) -> Attachment:
    """Reads back an attachment as :func:`encode` wrote it."""
    return Attachment(
        name       = str(data["name"]),
        media_type = str(data.get("media_type") or media_type_of(str(data["name"]))),
        data       = base64.b64decode(data.get("data_b64") or ""),
    )
