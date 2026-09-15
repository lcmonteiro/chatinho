"""The ``/copy`` command: puts a message on the clipboard, and says so in the chat.

There are already two ways to copy — hold a message, or press ``copy_key`` —
and on a phone terminal neither is certain to arrive: Termux takes the long
press for its own menu, and a key binding only fires if the terminal sends the
key at all. Both of those report through a *notification*, which is a third
thing that may not be visible.

This one reports the only way a chat is guaranteed to be able to report:
**as a message in the conversation**. What it answers is posted in ``TOOL``'s
name, in the log, where the whole point is that you can read it.
"""

from typing import Optional

from .. import chat_clipboard
from ..chat_hooks import Context, HookContext, HookExecute, require, tool
from ..chat_message import LOCAL, TOOL, ChatMessage


@tool("copy", "Copies a message to the clipboard: /copy, or /copy msg-3")
@require(HookExecute)
@require(HookContext)
class CopyCommand:
    """Copies a message by id, or the last one somebody said.

    It reaches the clipboard through a helper — ``termux-clipboard-set``,
    ``wl-copy``, ``xclip``, ``xsel``, ``pbcopy`` — because that is the route
    that works without the terminal's cooperation. OSC 52 is the presentation's
    to send, and a command is not the presentation.
    """

    context : Context

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs) -> str:
        """Copies, and answers with what happened.

        Args:
            args: A message id, or empty for the last message said.
            by: The id of the peer that ran it. Unused: what reaches the
                clipboard is the machine's, not the asker's.
            **kwargs: Ignored.

        Returns:
            str: What was copied and by which route, or why nothing was.
        """
        del by, kwargs
        wanted = args.strip()
        msg    = self._pick(wanted)
        if msg is None:
            return ("Nothing to copy: no message %s." % wanted if wanted
                    else "Nothing to copy: the conversation is empty.")

        route = chat_clipboard.put(msg.text)
        if route is None:
            return (
                "Could not copy %s: no clipboard helper on this system.\n"
                "On Termux install both halves — `pkg install termux-api` *and* "
                "the Termux:API app — then try again.\n"
                "Looked for: %s." % (msg.id, ", ".join(c[0] for c in chat_clipboard.HELPERS))
            )
        return "Copied %s to the clipboard with %s." % (msg.id, route)

    def _pick(self, wanted: str) -> Optional[ChatMessage]:
        """The message to copy: the one asked for, or the last one said.

        The invocation of ``/copy`` is itself in the conversation by the time
        this runs — everything that crosses the session is — so the default
        skips what a command wrote, or ``/copy`` would copy ``/copy``.

        Args:
            wanted: A message id, or empty for the last one said.

        Returns:
            Optional[ChatMessage]: The message, or None if there is none.
        """
        history = self.context()
        if wanted:
            return next((m for m in history if m.id == wanted), None)
        said = [m for m in history if m.frm != TOOL and m.to != TOOL]
        return said[-1] if said else None
