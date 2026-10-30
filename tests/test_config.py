"""Tests for GitHub Webhook plugin."""

from src.core.config import PluginConfig
from src.core.constants import DEFAULT_PORT


def test_config_default_values():
    """测试配置类的默认值"""
    config_data = {
        "port": DEFAULT_PORT,
        "target_umo": "",
        "webhook_secret": "",
        "rate_limit": 10,
        "notify_issue_updates": False,
        "enable_agent": False,
        "llm_provider_id": "",
        "agent_timeout": 60,
        "agent_system_prompt": "",
        "github_token": "",
    }
    plugin_config = PluginConfig(config_data)

    assert plugin_config.port == DEFAULT_PORT
    assert plugin_config.rate_limit == 10
    assert plugin_config.notify_issue_updates == False
    assert plugin_config.enable_agent == False


def test_config_with_custom_values():
    """测试配置类的自定义值"""
    config_data = {
        "port": 9000,
        "target_umo": "test:GroupMessage:123456",
        "webhook_secret": "test_secret",
        "rate_limit": 20,
        "notify_issue_updates": True,
        "enable_agent": True,
        "llm_provider_id": "test_provider",
        "agent_timeout": 90,
        "agent_system_prompt": "Custom prompt",
        "github_token": "ghp_test",
    }
    plugin_config = PluginConfig(config_data)

    assert plugin_config.port == 9000
    assert plugin_config.target_umo == "test:GroupMessage:123456"
    assert plugin_config.webhook_secret == "test_secret"
    assert plugin_config.enable_agent == True

