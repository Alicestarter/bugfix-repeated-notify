"""Fork event formatter."""


def format_fork_message(
    author_name: str,
    source_repo: str,
    fork_repo: str,
    fork_url: str,
) -> str:
    """Format fork event message."""
    return (
        "🍴 GitHub Fork Event\n"
        f"👤 {author_name} forked {source_repo}\n"
        f"📦 New repo: {fork_repo}\n"
        f"📎 {fork_url}"
    )
