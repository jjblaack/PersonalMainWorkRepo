#!/bin/bash
# dangerous-command.sh — PreToolUse/Bash hook
# 检测到高风险命令时，弹 osascript 对话框把决策权交回给用户：
#   - 用户点"允许"         → exit 0（放行）
#   - 用户点"拒绝"/关闭/超时 → exit 2（拦截）
# 默认值是"拒绝"——用户没看清就回车的话选安全的一边。

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | /usr/bin/python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")
CWD=$(echo "$INPUT" | /usr/bin/python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('cwd',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# 高风险命令模式
DANGEROUS=(
  'rm[[:space:]]+-[a-zA-Z]*[rR]'                       # 任何递归删除：rm -r / -rf / -Rf / -frv
  'rm[[:space:]]+-[a-zA-Z]*f[[:space:]]+/'             # rm -f 绝对路径
  'rm[[:space:]]+-[a-zA-Z]*f[[:space:]]+~'             # rm -f 家目录
  'rm[[:space:]]+-[a-zA-Z]*f[[:space:]]+\*'            # rm -f *（通配删当前目录全部）
  'git[[:space:]]+push.*--force'                       # git push --force
  'git[[:space:]]+push.*[[:space:]]-f([[:space:]]|$)'  # git push -f
  'git[[:space:]]+reset[[:space:]]+--hard'             # git reset --hard
  'git[[:space:]]+clean[[:space:]]+-[a-zA-Z]*[fdx]'    # git clean -fd / -fdx
  'git[[:space:]]+branch[[:space:]]+-D'                # 强制删分支
  'DROP[[:space:]]+TABLE'                              # SQL drop
  'DROP[[:space:]]+DATABASE'                           # SQL drop
  'TRUNCATE[[:space:]]+TABLE'                          # SQL truncate
  'DELETE[[:space:]]+FROM[[:space:]]+[a-zA-Z_]+[[:space:]]*;'  # 无 WHERE 的 DELETE
  'dd[[:space:]]+if=.*of=/dev/'                        # dd 写块设备
  ':\(\)\{.*:|:&\};:'                                  # fork bomb
  'chmod[[:space:]]+-R[[:space:]]+777'                 # 递归 777
  'curl[^|]*\|[[:space:]]*(bash|sh|zsh)'               # curl | bash
  'wget[^|]*\|[[:space:]]*(bash|sh|zsh)'               # wget | bash
)

# AppleScript 字符串转义：\ → \\，" → \"，把换行压成空格避免 display dialog 解析异常
applescript_escape() {
  /usr/bin/python3 -c 'import sys; s=sys.stdin.read().replace("\n"," "); print(s.replace("\\","\\\\").replace("\"","\\\""), end="")'
}

for pat in "${DANGEROUS[@]}"; do
  if echo "$COMMAND" | /usr/bin/grep -qE -e "$pat"; then
    SAFE_CMD=$(printf '%s' "$COMMAND" | applescript_escape)
    SAFE_PAT=$(printf '%s' "$pat"     | applescript_escape)
    SAFE_CWD=$(printf '%s' "$CWD"     | applescript_escape)

    RESPONSE=$(/usr/bin/osascript <<OSA 2>/dev/null || echo "DENY"
try
  set theResponse to display dialog "检测到高风险命令，请核对绝对路径后决定是否放行。

命令：
$SAFE_CMD

匹配模式：$SAFE_PAT
工作目录：$SAFE_CWD" buttons {"拒绝", "允许"} default button "拒绝" with title "Claude Code · 危险命令确认" with icon caution giving up after 60
  if gave up of theResponse is true then
    return "DENY"
  end if
  return button returned of theResponse
on error
  return "DENY"
end try
OSA
)

    if [ "$RESPONSE" = "允许" ]; then
      /bin/cat >&2 <<EOF
NOTE [pre-bash:dangerous-command] 用户已在弹窗中允许执行
匹配模式：$pat
命令内容：$COMMAND
EOF
      exit 0
    else
      /bin/cat >&2 <<EOF
ERROR [pre-bash:dangerous-command] 用户已在弹窗中拒绝执行（或超时/关闭窗口）
匹配模式：$pat
命令内容：$COMMAND
处置建议：
  1. 向用户解释缘由或换可逆方案（git stash / 备份后再删 等）
  2. 确实必要时，请用户明确授权后重新发起
EOF
      exit 2
    fi
  fi
done

exit 0
