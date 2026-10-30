"""Issues event formatter."""


def format_issue_message(
    action: str,
    author_name: str,
    repo_name: str,
    issue_number: int,
    title: str,
    issue_url: str,
    labels: list[str] | None = None,
    issue_type: str | None = None,
    fields: dict[str, str] | None = None,
) -> str:
    """Format issue event message, optionally including issue metadata."""
    action_emoji = {
        "opened": "🆕",
        "closed": "✅",
        "reopened": "🔄",
    }.get(action, "📝")

    lines = [
        f"{action_emoji} GitHub Issue Event",
        f"👤 {author_name} {action} issue in {repo_name}",
        f"📋 Issue #{issue_number}: {title}",
    ]

    if labels:
        lines.append(f"🏷️ Labels: {', '.join(labels)}")
    if issue_type:
        lines.append(f"🧩 Type: {issue_type}")
    for name, value in (fields or {}).items():
        lines.append(f"🔖 {name}: {value}")

    lines.append(f"📎 {issue_url}")
    return "\n".join(lines)


_UPDATE_ACTION_TEXT = {
    "labeled": "added label",
    "unlabeled": "removed label",
    "typed": "set type",
    "untyped": "cleared type",
    "field_added": "updated field",
    "field_removed": "cleared field",
}


def format_issue_update_message(
    action: str,
    author_name: str,
    repo_name: str,
    issue_number: int,
    title: str,
    issue_url: str,
    detail: str | None = None,
) -> str:
    """Format a standalone issue attribute-change message."""
    action_text = _UPDATE_ACTION_TEXT.get(action, action)

    lines = [
        "📝 GitHub Issue Updated",
        f"👤 {author_name} {action_text} on {repo_name}",
        f"📋 Issue #{issue_number}: {title}",
    ]

    if detail:
        lines.append(f"🔖 {detail}")

    lines.append(f"📎 {issue_url}")
    return "\n".join(lines)
