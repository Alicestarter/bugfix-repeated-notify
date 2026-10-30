"""Tests for issue event merging and notification filtering."""

import asyncio
from types import SimpleNamespace

from src.formatters.issues_formatter import (
    format_issue_message,
    format_issue_update_message,
)
from src.handlers.issues_handler import (
    IssueNotifier,
    IssueSnapshot,
    _refresh_snapshot,
    snapshot_from_event,
)


def make_event(
    action: str,
    labels: list[str] | None = None,
    issue_type: str | None = None,
    assignees: list[str] | None = None,
    fields: list[dict] | None = None,
    extra: dict | None = None,
) -> dict:
    issue = {
        "number": 42,
        "title": "Bug report",
        "html_url": "https://github.com/acme/repo/issues/42",
        "labels": [{"name": label} for label in (labels or [])],
        "type": {"name": issue_type} if issue_type else None,
        "issue_field_values": fields or [],
    }
    if assignees is not None:
        issue["assignees"] = [{"login": login} for login in assignees]
    data = {
        "action": action,
        "issue": issue,
        "repository": {"full_name": "acme/repo"},
        "sender": {"login": "alice"},
    }
    if extra:
        data.update(extra)
    return data


class FakePlugin:
    def __init__(self, notify_issue_updates: bool = False):
        self.cfg = SimpleNamespace(notify_issue_updates=notify_issue_updates)
        self.sent: list[tuple[str, str]] = []

    async def dispatch_message(self, message: str, data: dict, event_type: str):
        self.sent.append((message, event_type))


def test_snapshot_extracts_labels_type_and_fields():
    data = make_event(
        "opened",
        labels=["bug", "priority:high"],
        issue_type="Bug",
        fields=[
            {
                "issue_field_name": "Due date",
                "data_type": "date",
                "value": "2026-11-01",
            },
            {
                "issue_field_name": "Severity",
                "data_type": "single_select",
                "value": "high",
                "single_select_option": {"id": 1, "name": "High", "color": "red"},
            },
        ],
    )

    snapshot = snapshot_from_event(data)

    assert snapshot.repo_name == "acme/repo"
    assert snapshot.issue_number == 42
    assert snapshot.labels == ["bug", "priority:high"]
    assert snapshot.issue_type == "Bug"
    assert snapshot.fields == {"Due date": "2026-11-01", "Severity": "High"}


def test_refresh_snapshot_applies_event_only_attribute():
    snapshot = IssueSnapshot(repo_name="acme/repo", issue_number=42)
    data = {
        "action": "labeled",
        "issue": {},
        "repository": {"full_name": "acme/repo"},
        "sender": {"login": "alice"},
        "label": {"name": "bug"},
    }

    _refresh_snapshot(snapshot, data)

    assert snapshot.labels == ["bug"]


def test_refresh_snapshot_removes_field():
    snapshot = IssueSnapshot(
        repo_name="acme/repo",
        issue_number=42,
        fields={"Due date": "2026-11-01"},
    )
    data = {
        "action": "field_removed",
        "issue": {},
        "repository": {"full_name": "acme/repo"},
        "sender": {"login": "alice"},
        "issue_field": {"name": "Due date"},
    }

    _refresh_snapshot(snapshot, data)

    assert snapshot.fields == {}


def test_snapshot_extracts_assignees():
    data = make_event("opened", assignees=["alice", "bob"])

    snapshot = snapshot_from_event(data)

    assert snapshot.assignees == ["alice", "bob"]


def test_refresh_snapshot_merges_assigned_event():
    snapshot = IssueSnapshot(repo_name="acme/repo", issue_number=42)
    data = {
        "action": "assigned",
        "issue": {},
        "repository": {"full_name": "acme/repo"},
        "sender": {"login": "carol"},
        "assignee": {"login": "alice"},
    }

    _refresh_snapshot(snapshot, data)

    assert snapshot.assignees == ["alice"]


def test_refresh_snapshot_removes_unassigned():
    snapshot = IssueSnapshot(
        repo_name="acme/repo",
        issue_number=42,
        assignees=["alice"],
    )
    data = make_event("unassigned", extra={"assignee": {"login": "alice"}})

    _refresh_snapshot(snapshot, data)

    assert snapshot.assignees == []


def test_creation_message_includes_assignees():
    message = format_issue_message(
        action="opened",
        author_name="alice",
        repo_name="acme/repo",
        issue_number=42,
        title="Bug report",
        issue_url="https://github.com/acme/repo/issues/42",
        assignees=["alice", "bob"],
    )

    assert "👥 Assigned: alice, bob" in message


def test_creation_message_includes_metadata():
    message = format_issue_message(
        action="opened",
        author_name="alice",
        repo_name="acme/repo",
        issue_number=42,
        title="Bug report",
        issue_url="https://github.com/acme/repo/issues/42",
        labels=["bug", "priority:high"],
        issue_type="Bug",
        fields={"Due date": "2026-11-01"},
    )

    assert "🏷️ Labels: bug, priority:high" in message
    assert "🧩 Type: Bug" in message
    assert "🔖 Due date: 2026-11-01" in message


def test_update_message_includes_detail():
    message = format_issue_update_message(
        action="labeled",
        author_name="alice",
        repo_name="acme/repo",
        issue_number=42,
        title="Bug report",
        issue_url="https://github.com/acme/repo/issues/42",
        detail="Label: bug",
    )

    assert "added label" in message
    assert "🔖 Label: bug" in message


def test_creation_burst_is_merged_into_one_message():
    async def scenario():
        plugin = FakePlugin()
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)

        assert await notifier.handle(make_event("opened", labels=["bug"])) is None
        assert (
            await notifier.handle(
                make_event(
                    "labeled",
                    labels=["bug", "priority:high"],
                    extra={"label": {"name": "priority:high"}},
                )
            )
            is None
        )
        assert (
            await notifier.handle(
                make_event(
                    "assigned",
                    labels=["bug", "priority:high"],
                    extra={"assignee": {"login": "alice"}},
                )
            )
            is None
        )
        assert (
            await notifier.handle(
                make_event(
                    "field_added",
                    labels=["bug", "priority:high"],
                    fields=[
                        {
                            "issue_field_name": "Due date",
                            "data_type": "date",
                            "value": "2026-11-01",
                        }
                    ],
                    extra={
                        "issue_field": {"name": "Due date"},
                        "issue_field_value": {"value": "2026-11-01"},
                    },
                )
            )
            is None
        )

        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, event_type = sent[0]
    assert event_type == "issues"
    assert "opened issue" in message
    assert "Labels: bug, priority:high" in message
    assert "Assigned: alice" in message
    assert "Due date: 2026-11-01" in message


def test_attribute_only_burst_suppressed_by_default():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=False)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert (
            await notifier.handle(
                make_event("labeled", labels=["bug"], extra={"label": {"name": "bug"}})
            )
            is None
        )
        await asyncio.sleep(0.1)
        return plugin.sent

    assert asyncio.run(scenario()) == []


def test_standalone_attribute_change_notified_when_enabled():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=True)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert (
            await notifier.handle(
                make_event("labeled", labels=["bug"], extra={"label": {"name": "bug"}})
            )
            is None
        )
        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, _ = sent[0]
    assert "added label" in message
    assert "🔖 Label added: bug" in message


def test_standalone_assigned_notified_when_enabled():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=True)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert (
            await notifier.handle(
                make_event("assigned", extra={"assignee": {"login": "alice"}})
            )
            is None
        )
        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, _ = sent[0]
    assert "assigned issue" in message
    assert "🔖 Assignee: alice" in message


def test_non_attribute_action_notified_after_quiet_window():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=False)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert await notifier.handle(make_event("closed")) is None
        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, _ = sent[0]
    assert "closed issue" in message


def test_multiple_attribute_actions_merged_into_one_update():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=True)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert (
            await notifier.handle(
                make_event("labeled", labels=["bug"], extra={"label": {"name": "bug"}})
            )
            is None
        )
        assert (
            await notifier.handle(
                make_event("assigned", extra={"assignee": {"login": "alice"}})
            )
            is None
        )
        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, _ = sent[0]
    assert "GitHub Issue Updated" in message
    assert "🔹 Label added: bug" in message
    assert "🔹 Assignee: alice" in message


def test_mixed_actions_merged_even_when_updates_disabled():
    async def scenario():
        plugin = FakePlugin(notify_issue_updates=False)
        notifier = IssueNotifier(plugin, quiet_seconds=0.02, max_wait_seconds=0.2)
        assert (
            await notifier.handle(
                make_event("labeled", labels=["bug"], extra={"label": {"name": "bug"}})
            )
            is None
        )
        assert await notifier.handle(make_event("closed")) is None
        await asyncio.sleep(0.1)
        return plugin.sent

    sent = asyncio.run(scenario())

    assert len(sent) == 1
    message, _ = sent[0]
    assert "🔹 closed" in message
    assert "🔹 Label added: bug" in message
