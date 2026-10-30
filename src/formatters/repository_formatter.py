"""Repository event formatter."""

import json


REPOSITORY_ACTIONS = {
    "created": ("🆕", "created repository"),
    "deleted": ("🗑️", "deleted repository"),
    "renamed": ("✏️", "renamed repository"),
    "archived": ("📦", "archived repository"),
    "unarchived": ("🔄", "unarchived repository"),
    "edited": ("📝", "edited repository settings for"),
    "publicized": ("🌐", "made repository public:"),
    "privatized": ("🔒", "made repository private:"),
}


def _format_value(value) -> str:
    """Keep empty values and boolean settings readable in change summaries."""
    if value is None or value == "":
        return "(empty)"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def format_repository_message(
    action: str,
    author_name: str,
    repository: dict,
    changes: dict | None = None,
) -> str | None:
    """Format supported repository actions, including available field changes."""
    if action not in REPOSITORY_ACTIONS:
        return None

    emoji, description = REPOSITORY_ACTIONS[action]
    repo_name = repository.get("full_name") or repository.get("name") or "Unknown"
    lines = [
        f"{emoji} GitHub Repository Event",
        f"👤 {author_name} {description} {repo_name}",
    ]

    if action in {"renamed", "edited"}:
        for field, change in (changes or {}).items():
            if not isinstance(change, dict) or "from" not in change:
                continue
            old_value = _format_value(change["from"])
            new_value = (
                _format_value(repository[field])
                if field in repository
                else "(unknown)"
            )
            lines.append(f"📝 {field}: {old_value} → {new_value}")

    if repository.get("html_url"):
        lines.append(f"📎 {repository['html_url']}")

    return "\n".join(lines)
