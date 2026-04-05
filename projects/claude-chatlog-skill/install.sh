# 安装脚本 - Claude Chatlog Skill

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/chatlog"

echo "安装 Claude Chatlog Skill..."

# 创建 Skill 目录
mkdir -p "$SKILL_DIR/scripts"

# 复制脚本
cp "$SCRIPT_DIR/scripts/"*.py "$SKILL_DIR/scripts/"
chmod +x "$SKILL_DIR/scripts/"*.py

# 复制 skill.yaml
cp "$SCRIPT_DIR/skill.yaml" "$SKILL_DIR/"

# 创建日志目录
mkdir -p "$SKILL_DIR/chatlog/sessions"
mkdir -p "$SKILL_DIR/chatlog/index"

echo ""
echo "✓ Skill 已安装到：$SKILL_DIR"
echo ""
echo "使用方法:"
echo "  /skill chatlog init \"主题\"    # 初始化会话"
echo "  /skill chatlog index            # 生成索引"
echo "  /skill chatlog check            # 检查中断"
echo ""
echo "可选：在 ~/.claude/settings.json 中添加 hooks:"
echo '  {'
echo '    "hooks": {'
echo '      "before-everything": "python3 ~/.claude/skills/chatlog/scripts/chat_logger.py --check-interrupt 2>/dev/null || true"'
echo '    }'
echo '  }'
