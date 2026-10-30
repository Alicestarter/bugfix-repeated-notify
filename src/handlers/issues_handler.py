"""Issues event handler.

GitHub emits several ``issues`` events when an issue is created with labels,
a type, or custom field values: ``opened`` is followed by ``labeled``,
``typed``, ``field_added`` and friends. Forwarding each one produces a burst of
near-identical notifications, so creation-time attribute events are buffered
and merged into the single creation message.

Attribute changes made after the creation burst are controlled by the
``notify_issue_updates`` config option.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from astrbot.api import logger

from ..formatters.issues_formatter import (
    format_issue_message,
    format_issue_update_message,
)

CREATION_ACTION = "opened"

# Attribute actions that GitHub emits alongside ``opened`` when an issue is
# created with pre-set metadata.
ATTRIBUTE_ACTIONS = frozenset(
    {
        "labeled",
        "unlabeled",
        "typed",
        "untyped",
        "field_added",
        "field_removed",
    }
)

# How long to wait for the rest of a creation burst after the last event.
DEFAULT_QUIET_SECONDS = 2.0
# Upper bound so a continuous stream of attribute events cannot delay forever.
DEFAULT_MAX_WAIT_SECONDS = 8.0


@dataclass
class IssueSnapshot:
    """The parts of an issue that are rendered in a creation notification."""

    repo_name: str = "Unknown"
    issue_number: int = 0
    title: str = "No title"
    issue_url: str = ""
    author_name: str = "Unknown"
    labels: list[str] = field(default_factory=list)
    issue_type: str | None = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class _PendingCreation:
    snapshot: IssueSnapshot
    data: dict[str, Any]
    first_seen: float
    last_seen: float
    task: asyncio.Task | None = None


def _label_name(label: Any) -> str | None:
    if isinstance(label, dict):
        name = label.get("name")
        return str(name) if name else None
    if isinstance(label, str) and label:
        return label
    return None


def _extract_label_names(issue: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for label in issue.get("labels") or []:
        name = _label_name(label)
        if name and name not in names:
            names.append(name)
    return names


def _extract_type_name(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    if isinstance(value, str) and value:
        return value
    return None


def _format_field_value(value_obj: Any) -> str:
    """Render an ``issue_field_values`` entry as plain text."""
    if not isinstance(value_obj, dict):
        return "" if value_obj is None else str(value_obj)

    single = value_obj.get("single_select_option")
    if isinstance(single, dict) and single.get("name"):
        return str(single["name"])

    multi = value_obj.get("multi_select_options")
    if isinstance(multi, list):
        names = [
            str(option["name"])
            for option in multi
            if isinstance(option, dict) and option.get("name")
        ]
        if names:
            return ", ".join(names)

    value = value_obj.get("value")
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _field_name(value_obj: Any) -> str | None:
    if not isinstance(value_obj, dict):
        return None
    name = value_obj.get("issue_field_name") or value_obj.get("name")
    return str(name) if name else None


def _extract_field_values(issue: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in issue.get("issue_field_values") or []:
        name = _field_name(item)
        if name:
            fields[name] = _format_field_value(item)
    return fields


def snapshot_from_event(data: dict[str, Any]) -> IssueSnapshot:
    """Build a creation snapshot from an ``issues`` webhook payload."""
    issue = data.get("issue") or {}
    repository = data.get("repository") or {}
    sender = data.get("sender") or {}

    return IssueSnapshot(
        repo_name=repository.get("full_name", "Unknown"),
        issue_number=issue.get("number", 0),
        title=issue.get("title", "No title"),
        issue_url=issue.get("html_url", ""),
        author_name=sender.get("login", "Unknown"),
        labels=_extract_label_names(issue),
        issue_type=_extract_type_name(issue.get("type")),
        fields=_extract_field_values(issue),
    )


def _refresh_snapshot(snapshot: IssueSnapshot, data: dict[str, Any]) -> None:
    """Merge an attribute event into a pending creation snapshot."""
    issue = data.get("issue") or {}

    if isinstance(issue, dict):
        if "title" in issue:
            snapshot.title = issue.get("title", snapshot.title)
        if "html_url" in issue:
            snapshot.issue_url = issue.get("html_url", snapshot.issue_url)
        if "labels" in issue:
            snapshot.labels = _extract_label_names(issue)
        if "type" in issue:
            snapshot.issue_type = _extract_type_name(issue.get("type"))
        if "issue_field_values" in issue:
            snapshot.fields = _extract_field_values(issue)

    # Some events only carry the changed object, not the updated issue.
    action = data.get("action")
    if action in {"labeled", "unlabeled"}:
        name = _label_name(data.get("label"))
        if name and action == "labeled" and name not in snapshot.labels:
            snapshot.labels.append(name)
        elif name and action == "unlabeled" and name in snapshot.labels:
            snapshot.labels.remove(name)
    elif action in {"typed", "untyped"}:
        if action == "untyped":
            snapshot.issue_type = None
        else:
            snapshot.issue_type = _extract_type_name(data.get("type")) or snapshot.issue_type
    elif action == "field_added":
        field_obj = data.get("issue_field") or {}
        name = _field_name(field_obj) or _field_name(data.get("issue_field_value"))
        if name:
            snapshot.fields[name] = _format_field_value(data.get("issue_field_value"))
    elif action == "field_removed":
        name = _field_name(data.get("issue_field")) or _field_name(
            data.get("issue_field_value")
        )
        if name:
            snapshot.fields.pop(name, None)


def _issue_key(data: dict[str, Any]) -> str:
    issue = data.get("issue") or {}
    repository = data.get("repository") or {}
    repo_name = repository.get("full_name") or repository.get("id") or "unknown"
    return f"{repo_name}#{issue.get('number', 0)}"


def _update_detail(action: str, data: dict[str, Any]) -> str | None:
    """Short description for a post-creation attribute change notification."""
    if action in {"labeled", "unlabeled"}:
        name = _label_name(data.get("label"))
        return f"Label: {name}" if name else None
    if action == "typed":
        name = _extract_type_name(data.get("type"))
        return f"Type: {name}" if name else None
    if action == "untyped":
        return "Type cleared"
    if action in {"field_added", "field_removed"}:
        name = _field_name(data.get("issue_field")) or _field_name(
            data.get("issue_field_value")
        )
        if action == "field_removed":
            return f"Field cleared: {name}" if name else None
        if not name:
            return None
        value = _format_field_value(data.get("issue_field_value"))
        return f"{name}: {value}" if value else name
    return None


class IssueNotifier:
    """Buffer creation bursts and decide which issue events to forward."""

    def __init__(
        self,
        plugin,
        quiet_seconds: float = DEFAULT_QUIET_SECONDS,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    ):
        self._plugin = plugin
        self._quiet_seconds = quiet_seconds
        self._max_wait_seconds = max_wait_seconds
        self._pending: dict[str, _PendingCreation] = {}
        self._tasks: set[asyncio.Task] = set()

    @property
    def _cfg(self):
        return getattr(self._plugin, "cfg", None)

    def _notify_updates(self) -> bool:
        return bool(getattr(self._cfg, "notify_issue_updates", False))

    async def handle(self, data: dict[str, Any]) -> str | None:
        """Return a message to send now, or ``None`` if buffered/suppressed."""
        action = data.get("action", "unknown")
        issue = data.get("issue") or {}
        key = _issue_key(data)

        if action == CREATION_ACTION:
            self._cancel_pending(key)
            now = time.monotonic()
            pending = _PendingCreation(
                snapshot=snapshot_from_event(data),
                data=data,
                first_seen=now,
                last_seen=now,
            )
            self._pending[key] = pending
            task = asyncio.create_task(self._flush_later(key))
            pending.task = task
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            logger.info(
                f"GitHub Webhook: Buffering issue creation notification for {key}"
            )
            return None

        if action in ATTRIBUTE_ACTIONS:
            pending = self._pending.get(key)
            if pending is not None:
                _refresh_snapshot(pending.snapshot, data)
                pending.last_seen = time.monotonic()
                logger.info(
                    f"GitHub Webhook: Merged '{action}' into pending creation for {key}"
                )
                return None

            if self._notify_updates():
                return format_issue_update_message(
                    action=action,
                    author_name=(data.get("sender") or {}).get("login", "Unknown"),
                    repo_name=(data.get("repository") or {}).get(
                        "full_name", "Unknown"
                    ),
                    issue_number=issue.get("number", 0),
                    title=issue.get("title", "No title"),
                    issue_url=issue.get("html_url", ""),
                    detail=_update_detail(action, data),
                )

            logger.info(
                f"GitHub Webhook: Suppressed standalone '{action}' event for {key} "
                "(notify_issue_updates disabled)"
            )
            return None

        return format_issue_message(
            action=action,
            author_name=(data.get("sender") or {}).get("login", "Unknown"),
            repo_name=(data.get("repository") or {}).get("full_name", "Unknown"),
            issue_number=issue.get("number", 0),
            title=issue.get("title", "No title"),
            issue_url=issue.get("html_url", ""),
        )

    def _cancel_pending(self, key: str) -> None:
        pending = self._pending.pop(key, None)
        if pending is not None and pending.task is not None:
            pending.task.cancel()

    async def _flush_later(self, key: str) -> None:
        try:
            while True:
                await asyncio.sleep(self._quiet_seconds)
                pending = self._pending.get(key)
                if pending is None:
                    return

                now = time.monotonic()
                quiet_elapsed = now - pending.last_seen
                max_elapsed = now - pending.first_seen
                if (
                    quiet_elapsed < self._quiet_seconds
                    and max_elapsed < self._max_wait_seconds
                ):
                    continue

                self._pending.pop(key, None)
                try:
                    await self._send_creation(pending)
                except Exception as e:
                    logger.error(
                        f"GitHub Webhook: Failed to send merged issue notification: {e}",
                        exc_info=True,
                    )
                return
        except asyncio.CancelledError:
            raise

    async def _send_creation(self, pending: _PendingCreation) -> None:
        snapshot = pending.snapshot
        message = format_issue_message(
            action=CREATION_ACTION,
            author_name=snapshot.author_name,
            repo_name=snapshot.repo_name,
            issue_number=snapshot.issue_number,
            title=snapshot.title,
            issue_url=snapshot.issue_url,
            labels=snapshot.labels,
            issue_type=snapshot.issue_type,
            fields=snapshot.fields,
        )
        logger.info(
            f"GitHub Webhook: Sending merged issue creation notification for "
            f"{snapshot.repo_name}#{snapshot.issue_number} "
            f"(labels={len(snapshot.labels)}, type={snapshot.issue_type}, "
            f"fields={len(snapshot.fields)})"
        )
        await self._plugin.dispatch_message(message, pending.data, "issues")

    async def shutdown(self) -> None:
        """Cancel pending buffers and timers without sending them."""
        for key in list(self._pending):
            self._cancel_pending(key)
        for task in list(self._tasks):
            task.cancel()
        self._tasks.clear()
