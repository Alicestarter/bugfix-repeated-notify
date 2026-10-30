"""Repository notifications through formatting, handling and the HTTP endpoint."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from src.core.plugin import GitHubWebhookPlugin
from src.formatters.repository_formatter import format_repository_message
from src.handlers.repository_handler import handle_repository_event


ACTIONS = {
    "created": "created repository",
    "deleted": "deleted repository",
    "renamed": "renamed repository",
    "archived": "archived repository",
    "unarchived": "unarchived repository",
    "edited": "edited repository settings for",
    "publicized": "made repository public:",
    "privatized": "made repository private:",
}


@pytest.fixture
def payload():
    return {
        "action": "created",
        "sender": {"login": "octocat"},
        "repository": {
            "name": "new-repo",
            "full_name": "owner/new-repo",
            "html_url": "https://github.com/owner/new-repo",
            "description": "New description",
            "homepage": None,
            "has_issues": False,
        },
    }


@pytest.mark.parametrize("action, description", ACTIONS.items())
def test_supported_actions(payload, action, description):
    payload["action"] = action
    message = asyncio.run(handle_repository_event(payload, None))

    assert "GitHub Repository Event" in message
    assert f"octocat {description} owner/new-repo" in message
    assert "https://github.com/owner/new-repo" in message


def test_renamed_repository_includes_old_and_new_names(payload):
    payload.update(action="renamed", changes={"name": {"from": "old-repo"}})

    message = asyncio.run(handle_repository_event(payload, None))

    assert "name: old-repo → new-repo" in message
    assert "owner/new-repo" in message


def test_edited_repository_includes_changes_and_empty_values(payload):
    payload.update(action="edited", changes={
        "description": {"from": "Old description"},
        "homepage": {"from": "https://example.com"},
        "has_issues": {"from": True},
        "future_field": {"from": "old"},
        "missing_from": {},
        "invalid": None,
    })

    message = asyncio.run(handle_repository_event(payload, None))

    assert "description: Old description → New description" in message
    assert "homepage: https://example.com → (empty)" in message
    assert "has_issues: true → false" in message
    assert "future_field: old → (unknown)" in message
    assert "missing_from" not in message
    assert "invalid" not in message


def test_edited_repository_handles_previously_empty_description(payload):
    payload.update(action="edited", changes={"description": {"from": None}})
    message = asyncio.run(handle_repository_event(payload, None))
    assert "description: (empty) → New description" in message


@pytest.mark.parametrize("action", ACTIONS)
def test_optional_payload_fields_can_be_missing(action):
    message = asyncio.run(handle_repository_event({"action": action}, None))
    assert "GitHub Repository Event" in message
    assert "Unknown" in message
    assert "None" not in message


def test_repository_name_fallback():
    message = format_repository_message("deleted", "octocat", {"name": "repo"})
    assert "deleted repository repo" in message
    assert "📎" not in message


@pytest.mark.parametrize("action", ["transferred", "unknown", "", None])
def test_unsupported_actions_are_ignored(payload, action):
    payload["action"] = action
    assert asyncio.run(handle_repository_event(payload, None)) is None


@pytest.mark.parametrize("action", [*ACTIONS, "transferred", None])
@pytest.mark.parametrize("enable_agent", [False, True])
def test_repository_webhook_dispatch(payload, action, enable_agent):
    async def run():
        context = SimpleNamespace(
            send_message=AsyncMock(return_value=True),
            llm_generate=AsyncMock(return_value=SimpleNamespace(
                completion_text="Repository notification from LLM"
            )),
        )
        plugin = GitHubWebhookPlugin(context, {
            "port": 8080,
            "target_umo": "test:GroupMessage:123456",
            "webhook_secret": "",
            "rate_limit": 0,
            "enable_agent": enable_agent,
            "llm_provider_id": "test-provider",
            "agent_timeout": 60,
            "agent_system_prompt": "",
        })
        if action is None:
            payload.pop("action")
        else:
            payload["action"] = action
        if action == "renamed":
            payload["changes"] = {"name": {"from": "old-repo"}}
        elif action == "edited":
            payload["changes"] = {"description": {"from": "Old description"}}
        expected_message = await handle_repository_event(payload, context)

        async with TestClient(TestServer(plugin.app)) as client:
            response = await client.post(
                "/webhook", json=payload, headers={"X-GitHub-Event": "repository"}
            )
            assert response.status == 200
            assert await response.text() == "OK"

        if action not in ACTIONS:
            context.send_message.assert_not_awaited()
            context.llm_generate.assert_not_awaited()
            return

        context.send_message.assert_awaited_once()
        target, chain = context.send_message.await_args.args
        assert target == "test:GroupMessage:123456"
        if enable_agent:
            context.llm_generate.assert_awaited_once()
            assert expected_message in context.llm_generate.await_args.kwargs["prompt"]
            assert chain[0].text == "Repository notification from LLM"
        else:
            context.llm_generate.assert_not_awaited()
            assert chain[0].text == expected_message

    asyncio.run(run())
