"""Repository event handler."""

from astrbot.api import logger

from ..formatters.repository_formatter import format_repository_message


async def handle_repository_event(data: dict, context) -> str | None:
    """Handle repository lifecycle and settings events from GitHub."""
    try:
        return format_repository_message(
            action=data.get("action", "unknown"),
            author_name=(data.get("sender") or {}).get("login", "Unknown"),
            repository=data.get("repository") or {},
            changes=data.get("changes") or {},
        )
    except Exception as e:
        logger.error(f"GitHub Webhook: Error handling repository event: {e}")
        return None
