#!/bin/bash
# secret-scan.sh — PreToolUse/Bash hook
# 拦截包含 secret 模式的 bash 命令
# stdin: Claude Code hook 协议 JSON；关键字段 tool_input.command

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | /usr/bin/python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# secret 模式（只在命令字面值里查，不对环境变量引用误报）
PATTERNS=(
  'sk-[a-zA-Z0-9]{20,}'                    # OpenAI / Anthropic style
  'sk-ant-[a-zA-Z0-9_-]{20,}'              # Anthropic
  'AKIA[0-9A-Z]{16}'                        # AWS Access Key
  'ghp_[a-zA-Z0-9]{30,}'                    # GitHub PAT
  'xox[baprs]-[a-zA-Z0-9-]{10,}'            # Slack token
  '-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'   # Private key blob
  '(password|passwd|pwd)=[^$][^ ]{4,}'      # 明文密码赋值（排除 =$VAR 引用）
  '(api[_-]?key|secret|token)=[^$][a-zA-Z0-9]{16,}'  # 硬编码密钥
)

for pat in "${PATTERNS[@]}"; do
  # 用 -e 显式声明 pattern，避免 BSD grep 把 "-----BEGIN..." 当选项解析
  if echo "$COMMAND" | /usr/bin/grep -qE -e "$pat"; then
    /bin/cat >&2 <<EOF
ERROR [pre-bash:secret-scan] 检测到疑似 secret 模式
匹配模式：$pat
命令片段：$(echo "$COMMAND" | head -c 200)...
修复建议：
  - 把 secret 放进环境变量（export XXX 或 .env 文件 + 加 .gitignore）
  - 命令里用 \$XXX 引用，不要写字面值
  - 如果确认是误报（例如示例文档），请向用户说明并请求豁免
EOF
    exit 2
  fi
done

exit 0
