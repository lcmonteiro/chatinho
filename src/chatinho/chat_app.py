"""Textual presentation layer for a :class:`~chatinho.chat_session.ChatSession`.

The public entry point is :func:`create_chat`, which returns a ready-to-run
application. The class itself (``_Chat``) is private on purpose: build one
through the factory rather than instantiating it directly.

The presentation is a peer like any other — it is registered at
:data:`~chatinho.chat_message.LOCAL`, because the user is peer zero by
definition, and it declares the same hooks a connector does. There is no
privileged path: a terminal reaches the conversation through exactly the doors
a weather service does.

This module is the *only* place that knows the chat is a terminal app. It owns
the widget tree, the reply target (a click is a UI concept), thread marshalling
and the welcome message.

The parts live next door:

- :mod:`chatinho.chat_session` — the hub; imports no UI framework.
- :mod:`chatinho.chat_message` — the message model and the history store.
- :mod:`chatinho.chat_hooks`   — the hook constants, decorator and registry.
- :mod:`chatinho.chat_log`     — the scrollable log widget and its bubbles.
- :mod:`chatinho.chat_input`   — the input line and its autocomplete popup.
"""

import logging
import threading
from typing import Any, List, Optional

from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual.containers import Container, Vertical
from textual.widgets import Input

from .chat_hooks import (
    Answer,
    Ask,
    HookAsk,
    HookContext,
    HookOnAsk,
    HookListen,
    HookPeers,
    HookInvoke,
    HookSay,
    Context,
    Peers,
    Invoke,
    Say,
    connector,
    require,
)
from .chat_input import COMMAND_PREFIX, SUGGESTIONS_ID, CommandInput, CommandSuggestions
from .chat_log import ChatLog
from .chat_message import LOCAL, ChatMessage
from .chat_session import ChatSession
from .chat_style import ChatStyle

logger = logging.getLogger(__name__)

CHAT_LOG_ID : str = "chat-log"
INPUT_ID    : str = "input-line"


def create_chat(
    connectors      : Optional[List[Any]] = None,
    commands        : Optional[List[Any]] = None,
    backend         : Optional[Any] = None,
    title           : str = "Chatinho",
    welcome_message : str = "",
    max_displayed   : int = 100,
    style           : Optional[ChatStyle] = None,
) -> "_Chat":
    """Create a chat application from peers and a backend.

    A **connector** is a peer: it has an id and a queue, and the conversation
    reaches it. A **command** is not: it has neither, and it runs only when
    someone runs it. They are separate parameters because they are separate
    things.

    For a chat without a terminal — a script, a bot, a test — build a
    :class:`~chatinho.chat_session.ChatSession` directly and attach your own
    presentation.

    Args:
        connectors: Links to agents or APIs; peers, numbered from one.
        commands: Things the user runs as ``/name``; not peers.
        backend: Backend used by ``save_data``/``load_data``.
        title: Title of the chat application.
        welcome_message: Message displayed on mount; empty means none.
        max_displayed: How many messages are rendered at once (sliding window).
        style: Colour scheme; defaults to :class:`~chatinho.chat_style.ChatStyle`.

    Returns:
        _Chat: The configured application; call ``run()`` to start it.
    """
    return _Chat(
        session         = ChatSession(connectors=connectors, commands=commands,
                                      backend=backend),
        title           = title,
        welcome_message = welcome_message,
        max_displayed   = max_displayed,
        style           = style,
    )


@connector("chat")
@require(HookSay)
@require(HookAsk)
@require(HookListen)
@require(HookOnAsk)
@require(HookContext)
@require(HookPeers)
@require(HookInvoke)
class _Chat(App):
    """Terminal presentation of a :class:`~chatinho.chat_session.ChatSession`.

    Build instances with :func:`create_chat` rather than directly.

    ``max_displayed`` limits how many messages are rendered in the terminal
    (sliding window). The full history is always kept — older messages only
    leave the screen, not memory.
    """

    # Default stylesheet, rendered from ChatStyle() at class definition time.
    CSS = ChatStyle().to_css()

    # Granted by the session at attach; annotated so a type checker sees them.
    say           : Say
    ask           : Ask
    answer        : Answer
    context : Context
    peers  : Peers
    invoke        : Invoke

    def __init__(
        self,
        session         : Optional[ChatSession] = None,
        title           : str = "Chatinho",
        welcome_message : str = "",
        max_displayed   : int = 100,
        style           : Optional[ChatStyle] = None,
    ) -> None:
        super().__init__()
        if style is not None:
            # Instance-level override: Textual reads ``self.CSS`` at mount.
            self.CSS = style.to_css()  # type: ignore[misc]

        self.session : ChatSession = session if session is not None else ChatSession()
        # Peer zero: the user. This is what grants say, ask, answer and
        # context, and what subscribes listen and on_ask below.
        self.session.attach(self, at=LOCAL)
        self._repaint_after("say", "ask", "answer")

        self.title = title
        self.welcome_message = welcome_message
        self._input_placeholder = "Type a message or /command"
        self.max_displayed : int = max_displayed
        # Thread id of the app's main loop (set in on_mount)
        self._app_thread_id : Optional[int] = None

    def _repaint_after(self, *granted: str) -> None:
        """Wraps the granted verbs so the terminal repaints when we speak.

        A sender does not hear its own broadcast — that is what stops a
        connector answering its own answer forever — and an answer that
        resolves a pending ask reaches nobody at all. Neither would repaint the
        log, so the presentation, which is the thing that renders, wraps its
        own grants rather than asking the session for an exception.
        """
        for verb in granted:
            def wrap(call: Any) -> Any:
                async def spoken(*args, **kwargs) -> Any:
                    result = await call(*args, **kwargs)
                    self._repaint()
                    return result
                return spoken
            setattr(self, verb, wrap(getattr(self, verb)))

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Container(
            ChatLog(
                self.context,
                max_displayed=self.max_displayed,
                on_reply_target_change=self._on_reply_target_change,
                id=CHAT_LOG_ID,
            ),
            Vertical(
                CommandSuggestions(self.session.commands, id=SUGGESTIONS_ID),
                CommandInput(placeholder=self._input_placeholder, id=INPUT_ID),
                id="input-area",
            ),
        )

    async def on_mount(self) -> None:
        """Start the queues, focus the input and show the welcome message."""
        self._app_thread_id = threading.get_ident()
        await self.session.start()
        self.query_one("#%s" % INPUT_ID, Input).focus()
        if self.context():
            self._chat_log.sync()
            self._chat_log.scroll_to_bottom()
        if self.welcome_message:
            await self.say(self.welcome_message)

    async def on_unmount(self) -> None:
        """Shut the session's peers down when the app closes.

        A connector that owns a server or a thread would otherwise outlive the
        terminal it was serving.
        """
        await self.session.close()

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        """Handle the user pressing Enter."""
        del message
        inp = self.query_one("#%s" % INPUT_ID, Input)
        text = inp.value.strip()
        if not text:
            return
        inp.value = ""
        if text.startswith(COMMAND_PREFIX):
            name, _, args = text[1:].strip().partition(" ")
            await self.command(name, args)
        else:
            target = self._reply_target
            self._clear_reply_target()
            await self.say(text, reply_to=target)

    def on_input_changed(self, message: Input.Changed) -> None:
        """Update the command-suggestion popup as the user types."""
        if message.input.id != INPUT_ID:
            return
        self.query_one("#%s" % SUGGESTIONS_ID, CommandSuggestions).update_for(message.value)

    # === The conversation ===========================================================

    async def command(self, name: str, args: str = "") -> Optional[str]:
        """Runs ``/name args`` and shows whatever it answered.

        Neither the invocation nor the answer is a message. A command that
        should be seen declares ``HookSay`` and writes its own output; one that
        only answers is answering whoever ran it, and that is the caller's to
        do something with.

        Args:
            name: The command's name, without the prefix.
            args: The rest of the line.

        Returns:
            Optional[str]: What the command answered, if anything.
        """
        if name not in self.session.commands:
            await self.say("Unknown command: %s%s" % (COMMAND_PREFIX, name))
            return None
        return await self.invoke(name, args)

    async def listen(self, msg: ChatMessage, **kwargs) -> None:
        """Someone spoke to everyone: repaint."""
        self._repaint()

    async def on_ask(self, msg: ChatMessage, **kwargs) -> Optional[str]:
        """Someone asked the user something.

        Returns None on purpose: the answer is not ours to invent. The question
        is already in the history, so the user sees it and replies to it, and
        that reply resolves the wait — the session matches it by ``reply_to``.
        """
        self._repaint()
        return None

    @property
    def messages(self) -> List[ChatMessage]:
        """The full message history, oldest first."""
        return self.context()

    def get_replies(self, msg_id: str) -> List[str]:
        """Returns the ids of the messages that answer *msg_id*."""
        return [m.id for m in self.context() if m.reply_to == msg_id]

    # === Presentation-owned behaviour ===============================================

    async def send_pending_reply(self, text: str) -> Optional[str]:
        """Says *text* as a reply to the selected message, if there is one.

        The reply target is a UI concept — it comes from a click — so this
        lives here rather than in the session.
        """
        target = self._reply_target
        if target is None:
            return None
        self._clear_reply_target()
        return await self.say(text, reply_to=target)

    def has_command_suggestions(self) -> bool:
        """Whether the command-suggestion popup currently has entries."""
        return self.query_one("#%s" % SUGGESTIONS_ID, CommandSuggestions).has_suggestions

    # === Internals ==================================================================

    @property
    def _chat_log(self) -> ChatLog:
        """The log widget that renders the history."""
        return self.query_one("#%s" % CHAT_LOG_ID, ChatLog)

    def _repaint(self) -> None:
        """Schedules a render on the app's own message pump.

        Always through ``call_later``, never straight: a peer may speak
        from a coroutine the app did not start — one handed to
        ``run_coroutine_threadsafe`` by its own server thread — and querying
        the widget tree from there finds no active app. Going through the pump
        puts the work back where the context is.

        Before ``on_mount`` there is no widget tree yet: the messages stay in
        the session and are painted when the app mounts.
        """
        if self._app_thread_id is None:
            return
        self.call_later(self._sync_log)

    def _sync_log(self) -> None:
        """Brings the log in line with the history, if it is still mounted."""
        try:
            self._chat_log.sync()
        except NoMatches:
            pass

    def _on_reply_target_change(self, msg_id: Optional[str]) -> None:
        """Keeps the input placeholder in step with the log's reply target."""
        inp = self.query_one("#%s" % INPUT_ID, Input)
        inp.placeholder = self._input_placeholder if msg_id is None else "Reply to %s…" % msg_id

    def _find_message(self, msg_id: str) -> Optional[ChatMessage]:
        return next((m for m in self.context() if m.id == msg_id), None)

    @property
    def _reply_target(self) -> Optional[str]:
        return self._chat_log.reply_target

    @property
    def _rendered_msg_ids(self) -> List[str]:
        return self._chat_log._rendered_msg_ids

    def _set_reply_target(self, msg_id: str) -> None:
        self._chat_log.set_reply_target(msg_id)

    def _clear_reply_target(self) -> None:
        self._chat_log.clear_reply_target()
