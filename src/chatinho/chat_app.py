"""Textual presentation layer for a :class:`~chatinho.chat_session.ChatSession`.

The class here, :class:`ChatApp`, is built and attached to a session by
:func:`~chatinho.chat_builder.build_chat`, the public entry point — it takes
no session of its own, because it is a normal connector like any other, wired
up by whoever builds the chat rather than by its own constructor.

The presentation is a peer like any other. ``@frontend`` is what says so — it
is ``@connector`` pinned to :data:`~chatinho.chat_message.LOCAL`, because the
user is peer zero by definition — and beyond that it declares the same hooks a
connector does. There is no privileged path: a terminal reaches the
conversation through exactly the doors a weather service does.

This module is the *only* place that knows the chat is a terminal app. It owns
the widget tree, the reply target (a click is a UI concept), thread marshalling
and the welcome message.

The parts live next door:

- :mod:`chatinho.chat_session` — the hub; imports no UI framework.
- :mod:`chatinho.chat_message` — the message model and the history store.
- :mod:`chatinho.chat_hooks`   — the hook constants, decorator and registry.
- :mod:`chatinho.chat_log`     — the scrollable log widget and its bubbles.
- :mod:`chatinho.chat_input`   — the input line and its autocomplete popup.
- :mod:`chatinho.chat_builder` — :func:`build_chat`, which wires this to a session.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.css.query import NoMatches
from textual._ansi_sequences import ANSI_SEQUENCES_KEYS
from textual.keys import KEY_ALIASES, Keys
from textual.containers import Container, Vertical
from textual.widgets import TextArea

from .chat_hooks import (
    Ask,
    HookAsk,
    HookContext,
    HookAnswer,
    HookListen,
    HookPeers,
    HookCommands,
    HookInvoke,
    HookSay,
    Context,
    Peers,
    Commands,
    Invoke,
    Say,
    frontend,
    require,
)
from .chat_input import (
    COMMAND_PREFIX,
    NEWLINE_ESCAPE,
    SUGGESTIONS_ID,
    CommandInput,
    CommandSuggestions,
    validate_escape,
)
from .chat_log import ChatLog
from .chat_message import ChatMessage
from .chat_style import ChatStyle

logger = logging.getLogger(__name__)

CHAT_LOG_ID : str = "chat-log"
CHAT_BODY_ID: str = "chat-body"
INPUT_ID    : str = "input-line"


#: What Textual answers to, by name: every key it enumerates, plus its aliases.
_KEY_NAMES = {key.value for key in Keys} | set(KEY_ALIASES)

#: Prefixes a key may carry. Textual only enumerates ctrl and shift, but a
#: terminal that reports the others passes them through unchanged.
_MODIFIERS = frozenset({"ctrl", "shift", "alt", "meta", "super", "hyper"})


def _swallowed_keys() -> Dict[str, str]:
    """The ctrl combos a terminal never delivers as themselves.

    A terminal sends one control byte for ``ctrl+h`` and for Backspace alike,
    so Textual reports ``backspace`` for both and a ``ctrl+h`` binding can
    never fire. The same holds for ``ctrl+i``/Tab, ``ctrl+m``/Enter and
    ``ctrl+[``/Escape. This is derived from Textual's own sequence table
    rather than listed by hand, so it cannot drift from what Textual does.

    Returns:
        Dict[str, str]: Each unusable combo, mapped to what arrives instead.
    """
    swallowed : Dict[str, str] = {}
    for code in list(range(1, 27)) + [27]:
        combo    = "ctrl+%s" % chr(ord("a") + code - 1) if code < 27 else "ctrl+["
        arriving = ANSI_SEQUENCES_KEYS.get(chr(code))
        # The table's values are a tuple of keys for the sequences that name
        # one; anything else is not a key this could collide with.
        if not isinstance(arriving, tuple) or not arriving:
            continue
        delivered = str(getattr(arriving[0], "value", arriving[0]))
        if delivered != combo:
            swallowed[combo] = delivered
    return swallowed


#: Combos that look like keys and are not — see :func:`_swallowed_keys`.
_SWALLOWED : Dict[str, str] = _swallowed_keys()


def _validate_key(key: str) -> str:
    """Returns *key* if Textual could ever receive it, and raises if not.

    ``Binding`` itself only rejects the empty string — ``Binding("not a key",
    "quit")`` is built happily and then never fires, which is a keybinding that
    silently does nothing. Checking here turns that into an error at
    construction rather than a mystery at runtime.

    Args:
        key: A key or key-combination, as Textual writes them: ``"ctrl+q"``,
            ``"f5"``, ``"escape"``, ``"q"``. Comma-separated alternatives are
            allowed, because ``Binding`` expands them.

    Returns:
        str: The key, unchanged.

    Raises:
        ValueError: The key is empty, carries an unknown modifier, names
            something Textual has no key for, or is a combo the terminal
            delivers as a different key entirely.
    """
    for part in key.split(","):
        part = part.strip()
        if not part:
            raise ValueError(
                "quit_key must be a Textual key, not %r: a part of it is empty" % key
            )
        if part in _SWALLOWED:
            raise ValueError(
                "quit_key %r cannot work: a terminal sends the same byte for %s "
                "as for %s, so Textual reports %r and the binding never fires. "
                "Try 'ctrl+g' or 'f10'."
                % (key, part, _SWALLOWED[part], _SWALLOWED[part])
            )
        if part in _KEY_NAMES:
            continue
        *modifiers, base = part.split("+")
        unknown = [m for m in modifiers if m not in _MODIFIERS]
        if unknown:
            raise ValueError(
                "quit_key %r has an unknown modifier %r; Textual knows %s"
                % (key, unknown[0], ", ".join(sorted(_MODIFIERS)))
            )
        if not base or (len(base) > 1 and base not in _KEY_NAMES):
            raise ValueError(
                "quit_key %r is not a Textual key; try one of 'ctrl+q', 'f5', "
                "'escape', or a single character" % key
            )
    return key


@frontend("chat")
@require(HookSay)
@require(HookAsk)
@require(HookListen)
@require(HookAnswer)
@require(HookContext)
@require(HookPeers)
@require(HookCommands)
@require(HookInvoke)
class ChatApp(App):
    """
    Terminal presentation of a :class:`~chatinho.chat_session.ChatSession`.

    Build instances with :func:`~chatinho.chat_builder.build_chat` rather than
    directly. It takes no session: it is a normal connector, and it is
    :meth:`~chatinho.chat_session.ChatSession.add_connector` that grants it
    ``say``, ``ask``, ``context``, ``peers``, ``commands`` and ``invoke``, and
    subscribes ``listen`` and ``answer`` — the same as any other peer. A
    connector does not hold the session; whatever it needs of it is granted,
    the same way ``HelpCommand`` is granted its own ``commands``.

    ``max_displayed`` limits how many messages are rendered in the terminal
    (sliding window). The full history is always kept — older messages only
    leave the screen, not memory.
    """

    # Default stylesheet, rendered from ChatStyle() at class definition time.
    CSS = ChatStyle().to_css()

    # Granted by the session at attach; annotated so a type checker sees them.
    say     : Say
    ask     : Ask
    context : Context
    peers   : Peers
    commands: Commands
    invoke  : Invoke

    def __init__(
        self,
        title           : str = "Chatinho",
        welcome_message : str = "",
        max_displayed   : int = 100,
        style           : Optional[ChatStyle] = None,
        quit_key        : str = "ctrl+q",
        copy_key        : str = "ctrl+y",
        newline_escape  : Optional[str] = NEWLINE_ESCAPE,
        name            : Optional[str] = None,
    ) -> None:
        super().__init__()
        if name is not None:
            # Only works because @frontend wrote `name` onto the class:
            # DOMNode.name is a read-only property, so on a plain App this
            # same line raises. The decorator's class attribute shadows it.
            if not name.strip():
                raise ValueError("name must not be blank: it is shown as @name in the log")
            # mypy only sees DOMNode's read-only property, not the class
            # attribute the decorator put in front of it.
            self.name = name  # type: ignore[misc]
        # Validated here as well as in the widget, because the widget is not
        # built until compose() — and a mount is not where the caller looks.
        self._newline_escape : Optional[str] = validate_escape(newline_escape)
        self._rebind_quit(_validate_key(quit_key))
        self._bindings.bind(
            _validate_key(copy_key), "copy_selected",
            description="Copy the selected message", show=False, priority=True,
        )
        # Held, not just rendered: the log reads the bubble's maximum width and
        # the header palette from the same object the stylesheet came from.
        self._style : ChatStyle = style or ChatStyle()
        if style is not None:
            # Instance-level override: Textual reads ``self.CSS`` at mount.
            self.CSS = style.to_css()  # type: ignore[misc]

        self.title = title
        self.welcome_message = welcome_message
        self._input_placeholder = "Type a message or /command"
        self.max_displayed : int = max_displayed
        # Thread id of the app's main loop (set in on_mount)
        self._app_thread_id : Optional[int] = None

    def initialize(self) -> None:
        """
        Wraps ``say``/``ask`` to repaint, once ``add_connector`` grants them.

        Lifecycle, not a hook: the session calls this from ``start()``, which
        ``on_mount`` awaits before doing anything with ``say``/``context`` of
        its own.
        """
        self._repaint_after("say", "ask")

    async def serve(self) -> None:
        """
        Runs the terminal, and returns when the user quits.

        Lifecycle, not a hook: :meth:`ChatSession.run` calls this on every peer
        that has one and closes the session when the first returns. Quitting the
        chat is the end of the chat, even if a connector is still listening on a
        socket.
        """
        await self.run_async()

    def _rebind_quit(self, quit_key: str) -> None:
        """
        Moves the quit binding onto *quit_key*, and off whatever held it.

        ``ChatApp`` declares no ``BINDINGS`` of its own: quit is inherited from
        ``App``, and Textual *merges* a subclass's bindings with its parent's
        rather than replacing them — so declaring a new one would leave
        ``ctrl+q`` quitting as well. The instance's own map is what has to
        change, and it is already a private copy: ``DOMNode.__init__`` builds it
        with ``self._merged_bindings.copy()``, so this cannot leak into another
        chat or into ``App`` itself.

        Only bindings whose action is ``quit`` move. ``ctrl+c`` is a different
        action (``help_quit``) and ``ctrl+p`` opens the command palette; both are
        left exactly as they were.

        Args:
            quit_key: An already-validated key or key-combination.
        """
        bindings = self._bindings
        bindings.key_to_bindings = {
            key: kept
            for key, held in bindings.key_to_bindings.items()
            if (kept := [b for b in held if b.action != "quit"])
        }
        bindings.bind(quit_key, "quit", description="Quit", show=False, priority=True)

    def action_copy_selected(self) -> None:
        """Copies the message selected as the reply target.

        The keyboard way in, because the long press is not always reachable: a
        phone terminal may take the gesture for its own menu before the
        application sees any of it. Tap a message, then press the key.
        """
        target = self._reply_target
        if target is None:
            self.notify("Select a message first, then copy it", timeout=3)
            return
        self._chat_log.copy_message(target)

    def _repaint_after(self, *granted: str) -> None:
        """
        Wraps the granted verbs so the terminal repaints when we speak.

        A sender does not hear its own broadcast — that is what stops a
        connector answering its own answer forever — so nothing would repaint
        the log when the user speaks. The presentation, which is the thing that
        renders, wraps its own grants rather than asking the session for an
        exception. Only grants: ``answer`` is a method now, and it repaints
        itself.
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
                peers=self.peers,
                max_displayed=self.max_displayed,
                style=self._style,
                on_reply_target_change=self._on_reply_target_change,
                id=CHAT_LOG_ID,
            ),
            Vertical(
                CommandSuggestions(self.commands, id=SUGGESTIONS_ID),
                CommandInput(
                    newline_escape = self._newline_escape,
                    placeholder    = self._input_placeholder,
                    id             = INPUT_ID,
                ),
                id="input-area",
            ),
            id=CHAT_BODY_ID,
        )

    async def on_mount(self) -> None:
        """
        Focus the input, and show the history and welcome message.

        Whoever starts the session — ``run()``, or a test that mounts this app
        directly — starts it before the queues can deliver anything here.
        """
        self._app_thread_id = threading.get_ident()
        self.query_one("#%s" % INPUT_ID, CommandInput).focus()
        if self.context():
            self._chat_log.sync()
            self._chat_log.scroll_to_bottom()
        if self.welcome_message:
            await self.say(self.welcome_message)

    async def on_command_input_submitted(self, message: CommandInput.Submitted) -> None:
        """Handle the user sending what they typed.

        The text arrives on the message already stripped, and a blank input
        sends nothing at all, so there is nothing to check here.
        """
        text = message.text
        message.input.clear()
        if text.startswith(COMMAND_PREFIX):
            name, _, args = text[1:].strip().partition(" ")
            await self.command(name, args)
        else:
            target = self._reply_target
            self._clear_reply_target()
            await self.say(text, reply_to=target)

    def on_text_area_changed(self, message: TextArea.Changed) -> None:
        """Update the command-suggestion popup as the user types."""
        if message.text_area.id != INPUT_ID:
            return
        self.query_one("#%s" % SUGGESTIONS_ID, CommandSuggestions).update_for(
            message.text_area.text
        )

    # === The conversation ===========================================================

    async def command(self, name: str, args: str = "") -> Optional[str]:
        """
        Runs ``/name args`` and returns whatever it answered.

        Both the invocation and the answer *are* messages: the session posts
        the invocation addressed to ``TOOL``, and what ``execute`` returned in
        ``TOOL``'s name, replying to it. So the log shows the whole exchange
        without this having to write anything, and the return value is for the
        caller.

        Args:
            name: The command's name, without the prefix.
            args: The rest of the line.

        Returns:
            Optional[str]: What the command answered, if anything.
        """
        if name not in self.commands():
            await self.say("Unknown command: %s%s" % (COMMAND_PREFIX, name))
            return None
        return await self.invoke(name, args)

    async def listen(self, msg: ChatMessage, **kwargs) -> None:
        """Someone spoke to everyone: repaint."""
        self._repaint()

    async def answer(self, msg: ChatMessage, **kwargs) -> Optional[str]:
        """
        Someone asked the user something.

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
        """
        Says *text* as a reply to the selected message, if there is one.

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
        """
        Schedules a render on the app's own message pump.

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
        inp = self.query_one("#%s" % INPUT_ID, CommandInput)
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
