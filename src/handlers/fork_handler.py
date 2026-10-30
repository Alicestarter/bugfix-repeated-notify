"""Fork event handler."""

from astrbot.api import logger

from ..formatters.fork_formatter import format_fork_message


async def handle_fork_event(data: dict, context):
    """Handle fork event from GitHub webhook."""
    try:
        sender = data.get("sender", {})
        author = sender.get("login", "Unknown")
        source_repo = data.get("repository", {}).get("full_name", "Unknown")
        forkee = data.get("forkee", {})
        fork_repo = forkee.get("full_name", "Unknown")
        fork_url = forkee.get("html_url", f"https://github.com/{fork_repo}")

        return format_fork_message(
            author_name=author,
            source_repo=source_repo,
            fork_repo=fork_repo,
            fork_url=fork_url,
        )
    except Exception as e:
        logger.error(f"GitHub Webhook: Error handling fork event: {e}")
        return None
