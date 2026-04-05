# Claude Chatlog Skill

为 Claude Code 自动记录对话内容的轻量级 Skill。

---

## 快速安装

```bash
# 一键安装
./install.sh
```

---

## 目录结构

```
claude-chatlog-skill/
├── skill.yaml              # Skill 配置
├── install.sh              # 安装脚本
├── README.md               # 本文件
└── scripts/
    ├── chat_logger.py      # 日志记录
    └── update_index.py     # 索引生成
```

安装后：

```
~/.claude/skills/chatlog/
├── skill.yaml
├── scripts/
└── chatlog/                # 日志存储
```

---

## 使用方法

### Skill 命令

```
/skill chatlog init "会议记录"    # 初始化会话
/skill chatlog check              # 检查中断
/skill chatlog index              # 生成索引
/skill chatlog complete           # 标记完成
```

### 查看日志

```bash
# 最近会话
cat ~/.claude/skills/chatlog/chatlog/index/recent.md

# 完整对话
cat ~/.claude/skills/chatlog/chatlog/sessions/*/transcript.md
```

---

## 手动安装

```bash
# 1. 创建目录
mkdir -p ~/.claude/skills/chatlog/scripts

# 2. 复制文件
cp skill.yaml ~/.claude/skills/chatlog/
cp scripts/*.py ~/.claude/skills/chatlog/scripts/
chmod +x ~/.claude/skills/chatlog/scripts/*.py
```

---

## 可选配置

**注意**: Claude Code 的 hooks 配置可能因版本而异。如果 hooks 导致错误，请删除 hooks 配置，改用手动方式。

如果 hooks 可用，编辑 `~/.claude/settings.json` 添加：

```json
{
  "hooks": {
    "before-everything": "python3 ~/.claude/skills/chatlog/scripts/chat_logger.py --check-interrupt 2>/dev/null || true"
  }
}
```

如果报错，请删除 hooks 配置，每次会话手动运行 `/skill chatlog check`。

---

## 日志位置

`~/.claude/skills/chatlog/chatlog/`

可通过环境变量 `CHATLOG_ROOT` 自定义。

---

## 许可证

MIT License
