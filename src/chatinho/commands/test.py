"""Test command for chatinho: a health check of what the chat is wired to."""

import logging
import time

from ..chat_hooks import HookExecute, HookSay, Say, command, require

logger = logging.getLogger(__name__)


@command("test", "Executa um teste simples")
@require(HookExecute)
@require(HookSay)
class TestCommand:
    """Exercises the backend and reports what is registered.

    Declares HookSay, so it writes each line as it goes rather than returning
    one block at the end — a health check is more useful as it happens.
    """

    # Granted by the session because this class declares HookSay.
    say : Say

    def execute(self, chat_instance=None, **kwargs) -> None:
        """Runs the checks, writing each result through ``say``.

        Args:
            chat_instance: The session under test.
            **kwargs: Ignored.
        """
        logger.debug("Executing test command")
        self.say("=== Teste do Chatinho ===")
        self._check_backend(chat_instance)
        self._report("Comandos", getattr(chat_instance, "commands", None))
        self._report("Conectores", getattr(chat_instance, "connectors", None))
        self.say("=========================")

    def _check_backend(self, chat_instance) -> None:
        """Round-trips a value through the backend and reports each step."""
        if getattr(chat_instance, "backend", None) is None:
            self.say("Backend: não configurado")
            return
        key = "test_%d" % int(time.time())
        data = {"message": "Hello from chatinho!", "timestamp": time.time()}
        try:
            self.say("Backend save: %s" % self._tick(chat_instance.save_data(key, data)))
            self.say("Backend load: %s" % self._tick(chat_instance.load_data(key) == data))
            self.say("Backend delete: %s" % self._tick(chat_instance.delete_data(key)))
        except Exception as exc:
            logger.error("Backend test failed: %s", exc)
            self.say("Backend: ✗ (%s)" % exc)

    def _report(self, label: str, registered) -> None:
        """Says how many of *registered* there are, and their names."""
        if not registered:
            self.say("%s: nenhum registado" % label)
            return
        self.say("%s registados: %d" % (label, len(registered)))
        for name in sorted(registered):
            self.say("  - %s" % name)

    @staticmethod
    def _tick(ok) -> str:
        """Renders a result as a tick or a cross."""
        return "✓" if ok else "✗"
