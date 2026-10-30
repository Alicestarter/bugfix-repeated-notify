"""Exercise the actual entry point under an AstrBot-style package namespace."""

import asyncio
import importlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin_package(monkeypatch):
    name = "test_github_webhook_plugin"
    package = ModuleType(name)
    package.__path__ = [str(ROOT)]
    package.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    monkeypatch.setitem(sys.modules, name, package)
    yield name
    for module_name in list(sys.modules):
        if module_name.startswith(name + "."):
            sys.modules.pop(module_name)


def test_entry_point_uses_its_own_src_package(plugin_package):
    search_path = list(sys.path)
    entry = importlib.import_module(plugin_package + ".main")

    assert entry.GitHubWebhookPlugin.__module__ == plugin_package + ".src.core.plugin"
    assert sys.path == search_path


def test_entry_point_does_not_use_another_plugins_src(plugin_package, monkeypatch):
    foreign_src = ModuleType("src")
    monkeypatch.setitem(sys.modules, "src", foreign_src)

    entry = importlib.import_module(plugin_package + ".main")

    assert entry.GitHubWebhookPlugin.__module__ == plugin_package + ".src.core.plugin"
    assert sys.modules["src"] is foreign_src


def test_entry_point_ignores_orphaned_src_namespace(plugin_package, monkeypatch):
    # core/ is a namespace package. If src is unloaded while src.core remains,
    # importlib tries to recalculate its search path using a missing parent.
    spec = importlib.machinery.PathFinder.find_spec("src.core", [str(ROOT / "src")])
    assert spec is not None
    stale_core = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "src.core", stale_core)
    monkeypatch.delitem(sys.modules, "src", raising=False)
    importlib.invalidate_caches()
    with pytest.raises(KeyError, match="src"):
        list(stale_core.__path__)

    entry = importlib.import_module(plugin_package + ".main")

    assert entry.GitHubWebhookPlugin.__module__ == plugin_package + ".src.core.plugin"


def test_entry_point_reimports_after_plugin_modules_are_removed(plugin_package):
    entry = importlib.import_module(plugin_package + ".main")
    original_class = entry.GitHubWebhookPlugin
    for module_name in list(sys.modules):
        if module_name.startswith(plugin_package + "."):
            sys.modules.pop(module_name)
    importlib.invalidate_caches()

    reloaded = importlib.import_module(plugin_package + ".main")

    assert reloaded.GitHubWebhookPlugin is not original_class
    assert reloaded.GitHubWebhookPlugin.__module__ == plugin_package + ".src.core.plugin"


def test_entry_can_construct_plugin_and_reply_to_command(plugin_package):
    entry = importlib.import_module(plugin_package + ".main")
    schema = json.loads((ROOT / "_conf_schema.json").read_text())
    config = {key: item["default"] for key, item in schema.items()}
    context = SimpleNamespace()
    plugin = entry.PluginEntry(context, config)
    event = SimpleNamespace(plain_result=lambda text: text)

    async def run():
        try:
            return [result async for result in plugin.github_forks(event)]
        finally:
            await plugin.terminate()

    replies = asyncio.run(run())

    assert len(replies) == 1
    assert "尚未收到 GitHub 事件" in replies[0]
