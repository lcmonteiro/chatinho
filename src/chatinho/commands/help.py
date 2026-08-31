"""Help command for chatinho."""

import logging

from ..chat_hooks import HookExecute, command, require

logger = logging.getLogger(__name__)


@command("help", "Mostra esta ajuda")
@require(HookExecute)
class HelpCommand:
    """Lists the commands the chat has registered."""

    def execute(self, chat_instance=None, **kwargs) -> str:
        """Returns one line per registered command.

        Args:
            chat_instance: The session, for reading its commands.
            **kwargs: Ignored.

        Returns:
            str: The help text.
        """
        logger.debug("Executing help command")
        commands = getattr(chat_instance, "commands", None)
        if not commands:
            return "Nenhum comando registado."
        lines = ["Comandos disponíveis:"]
        for name, cmd in sorted(commands.items()):
            lines.append("  /%s - %s" % (name, getattr(cmd, "description", "")))
        return "\n".join(lines)
