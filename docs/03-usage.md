# 使用示例

本文档展示各种 GitHub 事件的消息格式示例。

## Push 事件

### 消息格式（使用默认模板）

```
📦 GitHub Push Event
👤 username pushed to owner/repo
🌿 Branch: main
💬 Fix webhook message sending issue
🔗 Commit: abc1234
📎 https://github.com/owner/repo/commit/abc1234
```

### LLM 生成示例

```
📦 新代码推送
TatsukiMengChen 向 astrbot_plugin_github_webhook 推送了代码

💬 修复 webhook 消息发送问题
🌿 分支：main
🔗 https://github.com/owner/repo/commit/abc1234
```

## Issues 事件

### Issue 打开

创建 Issue 时，GitHub 会先后发送 `opened`、`labeled`、`typed`、`assigned`、`field_added` 等多个事件。插件会把这些事件合并成一条创建通知。

**默认模板**：
```
🆕 GitHub Issue Event
👤 username opened issue in owner/repo
📋 Issue #42: Bug report
🏷️ Labels: bug, priority:high
🧩 Type: Bug
👥 Assigned: alice
🔖 Due date: 2026-11-01
📎 https://github.com/owner/repo/issues/42
```

> 标签、类型、负责人、自定义字段只有在创建时携带才会显示；没有对应内容的行会自动省略。

**LLM 生成**：
```
🆕 新问题报告
TatsukiMengChen 在 owner/repo 创建了新问题

📋 #42: Bug report
📎 https://github.com/owner/repo/issues/42
```

### 事件合并规则

同一 Issue 的 `issues` 事件会在安静窗口（2 秒，最长等待 8 秒）内合并为一条通知：

- 窗口内包含 `opened`：发送一条创建通知，带上标签、类型、负责人和自定义字段
- 窗口内包含 `closed`、`reopened`、`edited` 等主要动作：无论 `notify_issue_updates` 是否开启都会发送
- 窗口内只有标签、类型、负责人、字段等属性变更：由 `notify_issue_updates` 决定是否发送
- 窗口内有多个动作时，会以 `🔹` 列表合并展示：

```
📝 GitHub Issue Updated
👤 username updated issue in owner/repo
📋 Issue #42: Bug report
🔹 Label added: bug
🔹 Assignee: alice
📎 https://github.com/owner/repo/issues/42
```

### Issue 关闭

**默认模板**：
```
✅ GitHub Issue Event
👤 username closed issue in owner/repo
📋 Issue #42: Bug report
📎 https://github.com/owner/repo/issues/42
```

### Issue 重新打开

```
🔄 GitHub Issue Event
👤 username reopened issue in owner/repo
📋 Issue #42: Bug report
📎 https://github.com/owner/repo/issues/42
```

### Issue 属性变更

开启 `notify_issue_updates` 后，创建完成后的属性变更（包括指派/取消指派负责人）也会通知；窗口内有多项变更时合并为一条：

```
📝 GitHub Issue Updated
👤 username added label on owner/repo
📋 Issue #42: Bug report
🔖 Label added: bug
📎 https://github.com/owner/repo/issues/42
```

## Pull Request 事件

### PR 打开

**默认模板**：
```
🆕 GitHub Pull Request Event
👤 username opened PR in owner/repo
📋 PR #10: Add new feature
🌿 feature → main
📎 https://github.com/owner/repo/pull/10
```

**LLM 生成**：
```
🔀 新拉取请求
TatsukiMengChen 在 owner/repo 提交了 PR

📋 #10: Add new feature
🌿 feature → main
📎 https://github.com/owner/repo/pull/10
```

### PR 合并

**默认模板**：
```
✅ GitHub Pull Request Event
👤 username closed PR in owner/repo
📋 PR #10: Add new feature
🌿 feature → main
📎 https://github.com/owner/repo/pull/10
```

### PR 重新打开

```
🔄 GitHub Pull Request Event
👤 username reopened PR in owner/repo
📋 PR #10: Add new feature
🌿 feature → main
📎 https://github.com/owner/repo/pull/10
```

## Ping 事件

GitHub 在配置 Webhook 时会自动发送 Ping 事件，插件会自动响应：

```
[INFO] GitHub Webhook: Received event type: ping
```

## 自定义消息

### 使用 LLM 生成

配置 `enable_agent = true` 后，插件会使用 LLM 生成个性化消息。

1. 在 AstrBot WebUI 中配置好 LLM Provider
2. 在插件配置中启用 `enable_agent`
3. （可选）配置 `agent_system_prompt` 自定义消息风格
4. （可选）配置 `llm_provider_id` 指定使用的模型

查看 [配置文档](02-configuration.md) 了解 LLM 相关配置详情。

### 使用 Prompt 示例

在 `prompts/` 目录中提供了预置的系统提示词：

- [默认 Prompt](../prompts/default.md) - 通用 GitHub 事件消息生成提示词

使用方法：
1. 打开 Prompt 文件
2. 复制提示词内容
3. 粘贴到插件配置的 `agent_system_prompt` 字段

## 相关文档

- [配置说明](02-configuration.md) - 了解如何配置消息生成方式
- [故障排查](05-troubleshooting.md) - LLM 相关问题排查
