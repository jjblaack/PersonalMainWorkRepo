#!/bin/bash
# gotchas-prompt.sh — Stop hook
# Session 结束时弹 osascript 对话框，让用户决定是否沉淀本次踩坑
# 输入留空 = skip；输入内容 = 追加到 ~/.claude/skills/gotchas/SKILL.md

set -euo pipefail

GOTCHAS_FILE="$HOME/.claude/skills/gotchas/SKILL.md"
mkdir -p "$(dirname "$GOTCHAS_FILE")"

# 读走 stdin 避免某些 shell 环境下阻塞
cat > /dev/null 2>&1 || true

# 用 osascript 弹对话框。超时 30 秒自动跳过。
RESULT=$(/usr/bin/osascript <<'APPLESCRIPT' 2>/dev/null || echo ""
with timeout of 30 seconds
  try
    set dlg to display dialog "本次 session 有什么坑/教训要沉淀到 gotchas？

• 留空 + OK   = skip
• 输入内容 + OK = 追加到 ~/.claude/skills/gotchas/SKILL.md
• Cancel       = skip" default answer "" with title "Harness · Gotchas 沉淀" buttons {"Cancel","OK"} default button "OK"
    set theText to text returned of dlg
    return theText
  on error
    return ""
  end try
end timeout
APPLESCRIPT
)

# 去掉首尾空白
TEXT=$(echo "$RESULT" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

if [ -z "$TEXT" ]; then
  exit 0
fi

# 初始化文件（如果还没有）
if [ ! -f "$GOTCHAS_FILE" ]; then
  cat > "$GOTCHAS_FILE" <<'INIT'
---
name: gotchas
description: 沉淀使用 Claude Code 过程中踩过的坑、总结的教训、反复出现的问题模式。Agent 遇到类似任务时应主动读取此 skill 避免重蹈覆辙。
---

# Gotchas · 踩坑沉淀

> 本文件由 `~/.claude/hooks/gotchas-prompt.sh` 在 session 结束时追加。
> 每条记录带日期，方便后续复盘和清理。
> 按月审查：过时的坑应主动删除（过时的指令比没有指令更危险）。

INIT
fi

# 追加一条
DATE=$(date +"%Y-%m-%d %H:%M")
{
  echo ""
  echo "## $DATE"
  echo ""
  echo "$TEXT"
} >> "$GOTCHAS_FILE"

# 通知一下
/usr/bin/osascript -e 'display notification "Gotcha 已沉淀到 ~/.claude/skills/gotchas/" with title "Harness"' 2>/dev/null || true

exit 0
