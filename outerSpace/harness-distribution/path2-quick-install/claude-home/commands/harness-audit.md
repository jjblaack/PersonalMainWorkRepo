---
description: 月度 Harness 安全扫描。检查 settings.json 权限、hook 脚本注入风险、CLAUDE.md 泄密、skill/agent 里的敏感信息。
---

# /harness-audit · Harness 安全扫描

## 什么时候跑

- 每月一次（固定）
- 改动 hook / settings / agent / skill 后
- 准备把配置分享给他人或上传仓库前

## 扫描项

### 1. settings.json 权限审查
- Read `~/.claude/settings.json`
- 检查：
  - [ ] 权限配置是否过于宽松（有无默认允许危险操作）
  - [ ] hook 脚本路径是否存在且合法（避免劫持风险）
  - [ ] model 字段是否意外被改

### 2. hook 脚本安全审查
- Read `~/.claude/hooks/*.sh`
- 检查：
  - [ ] 是否有 shell 注入风险（使用了不带引号的变量展开）
  - [ ] 是否 `set -euo pipefail`
  - [ ] 是否从不可信源（stdin、外部文件）读取后直接 eval
  - [ ] 模式列表是否过期（新类型 secret / 新高危命令）

### 3. CLAUDE.md 泄密检查
- Read `~/.claude/CLAUDE.md`
- 检查：
  - [ ] 有无硬编码 secret / 内部 URL / 敏感路径
  - [ ] 有无泄密团队内部决策细节
  - [ ] 有无"外部看到会尴尬"的表述

### 4. skill / agent 里的敏感信息
- Grep `~/.claude/skills/ ~/.claude/agents/` 检查：
  - [ ] 是否包含 API key 模式（`sk-`, `AKIA`, `ghp_` 等）
  - [ ] 是否包含内部 URL / 内部服务地址
  - [ ] 是否包含真实用户数据示例

Grep 建议：
```
grep -rE "(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{30,}|password\s*=\s*[^$])" ~/.claude/skills ~/.claude/agents ~/.claude/commands
```

### 5. gotchas 文件泄密
- Read `~/.claude/skills/gotchas/SKILL.md`
- gotchas 由人随手写，最容易不小心粘贴 secret
- 特别检查近期追加条目

### 6. backup 完整性
- ls `~/.claude/backups/`
- 至少保留 3 份最近备份
- 备份本身不应该上传到任何公共位置

## 输出

一份 `audit-YYYY-MM.md`，放在 `~/.claude/audits/`（不存在就创建）：
- 发现的问题（按严重度）
- 建议动作
- 已处置记录

**发现 Critical 问题（泄露 secret / 注入风险）立即处理，不要拖到下次。**
