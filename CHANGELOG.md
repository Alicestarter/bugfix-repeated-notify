# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [0.4.2] - 2026-10-30

### 修复
- 创建带有标签、类型或自定义字段的 Issue 时，`opened`、`labeled`、`typed`、`field_added` 等事件被逐条转发，导致群内出现多条重复通知
- 创建过程中的属性事件现在会合并进同一条创建消息，并尽量带上标签、类型和自定义字段

### 新增
- 配置项 `notify_issue_updates`，控制创建完成后的独立属性变更是否通知（默认关闭）

## [0.4.1] - 2026-02-06

### 修复
- **#2**: 修复 `metadata.yaml` (`astrbot_plugin_github_webhook`) 与 `main.py` 的 `@register` 装饰器 (`github_webhook`) 之间的插件注册 ID 不匹配问题
- 该不匹配导致 AstrBot 注册了两个独立的插件，创建了一个无法正常卸载的空白/损坏的重复插件条目

### 更改
- 统一所有配置文件中的插件 ID 为 `astrbot_plugin_github_webhook`

## [0.4.0] - 2026-01-26

### 新增
- LLM 智能消息生成支持，支持自定义提示词
- 请求速率限制配置，防止消息轰炸
- Webhook 签名验证，增强安全性
- 全面的错误处理和日志记录
- 支持 Push、Issues 和 Pull Request 事件

### 更改
- 改进消息格式化，提升可读性
- 增强配置验证

## [0.3.0] - 2026-01-21

### 新增
- GitHub Webhook 插件首次发布
- 基础 Webhook 服务器实现
- 支持 GitHub Push、Issues 和 Pull Request 事件
- Webhook 服务器配置（端口、target_umo）
- 基础消息转发到聊天平台
