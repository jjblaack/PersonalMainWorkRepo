#!/usr/bin/env python3
"""
Claude Chatlog - 对话日志记录器

用法:
    python chat_logger.py --init "会话主题"
    python chat_logger.py --user "用户输入"
    python chat_logger.py --ai "AI 回复"
    python chat_logger.py --complete
    python chat_logger.py --check-interrupt
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 日志根目录（支持环境变量覆盖）
CHATLOG_ROOT = Path(os.environ.get("CHATLOG_ROOT", Path(__file__).parent.parent / "chatlog"))
SESSIONS_DIR = CHATLOG_ROOT / "sessions"
INDEX_DIR = CHATLOG_ROOT / "index"
INCOMPLETE_MARKER = CHATLOG_ROOT / ".incomplete_session"

SESSION_ID = os.environ.get("CHATLOG_SESSION_ID")


def ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def generate_session_id(topic: str = None) -> str:
    now = datetime.now()
    date_prefix = now.strftime("%Y-%m-%d_%H%M")
    if topic:
        topic_clean = "".join(topic.split())[:15]
        return f"{date_prefix}-{topic_clean}" if topic_clean else f"{date_prefix}-session"
    import random
    return f"{date_prefix}-{random.randint(1000, 9999)}"


def get_or_create_session() -> str:
    global SESSION_ID
    if SESSION_ID:
        return SESSION_ID
    if INCOMPLETE_MARKER.exists():
        SESSION_ID = INCOMPLETE_MARKER.read_text().strip()
        return SESSION_ID
    SESSION_ID = generate_session_id("auto-session")
    session_dir = SESSIONS_DIR / SESSION_ID
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "transcript.md").write_text(f"# 会话记录：{SESSION_ID}\n\n")
    metadata = {
        "session_id": SESSION_ID,
        "topic": "auto-session",
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "messages": []
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    INCOMPLETE_MARKER.write_text(SESSION_ID)
    return SESSION_ID


def get_current_session_dir() -> Path:
    global SESSION_ID
    if not SESSION_ID and INCOMPLETE_MARKER.exists():
        SESSION_ID = INCOMPLETE_MARKER.read_text().strip()
    if not SESSION_ID:
        raise ValueError("SESSION_ID 未设置")
    return SESSIONS_DIR / SESSION_ID


def init_session(topic: str = None):
    ensure_dirs()
    if INCOMPLETE_MARKER.exists():
        old = INCOMPLETE_MARKER.read_text().strip()
        print(f"⚠️ 发现上次中断的会话：{old}")
    session_id = generate_session_id(topic)
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "transcript.md").write_text(f"# 会话记录：{session_id}\n\n")
    metadata = {
        "session_id": session_id,
        "topic": topic,
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "messages": []
    }
    (session_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    INCOMPLETE_MARKER.write_text(session_id)
    print(f"export CHATLOG_SESSION_ID=\"{session_id}\"")
    print(f"✓ 会话已初始化：{session_id}")


def save_user_message(content: str):
    get_or_create_session()
    session_dir = get_current_session_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(session_dir / "transcript.md", "a", encoding="utf-8") as f:
        f.write(f"\n---\n\n## 用户 @ {timestamp}\n\n{content}\n")
    metadata = json.loads((session_dir / "metadata.json").read_text())
    metadata["messages"].append({"role": "user", "content": content, "timestamp": timestamp})
    metadata["updated_at"] = datetime.now().isoformat()
    (session_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"✓ 用户输入已记录 ({len(content)} 字)")


def save_ai_response(content: str):
    global SESSION_ID
    if not SESSION_ID and INCOMPLETE_MARKER.exists():
        SESSION_ID = INCOMPLETE_MARKER.read_text().strip()
    elif not SESSION_ID:
        print("⚠️ 未找到活动会话，跳过记录")
        return
    session_dir = get_current_session_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(session_dir / "transcript.md", "a", encoding="utf-8") as f:
        f.write(f"\n---\n\n## AI @ {timestamp}\n\n{content}\n")
    metadata = json.loads((session_dir / "metadata.json").read_text())
    metadata["messages"].append({"role": "assistant", "content": content, "timestamp": timestamp})
    metadata["updated_at"] = datetime.now().isoformat()
    (session_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"✓ AI 回复已记录 ({len(content)} 字)")


def complete_session():
    if not SESSION_ID:
        print("⚠️ 未找到活动会话")
        return
    session_dir = SESSIONS_DIR / SESSION_ID
    metadata = json.loads((session_dir / "metadata.json").read_text())
    metadata["status"] = "completed"
    metadata["completed_at"] = datetime.now().isoformat()
    (session_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    if INCOMPLETE_MARKER.exists() and INCOMPLETE_MARKER.read_text().strip() == SESSION_ID:
        INCOMPLETE_MARKER.unlink()
    print(f"✓ 会话已完成：{SESSION_ID}")


def check_interrupt():
    if INCOMPLETE_MARKER.exists():
        old = INCOMPLETE_MARKER.read_text().strip()
        print(f"⚠️ 发现中断的会话：{old}")
    else:
        print("✓ 没有中断的会话")
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Claude Chatlog - 对话日志记录器")
    parser.add_argument("--init", type=str, help="初始化新会话")
    parser.add_argument("--user", type=str, help="保存用户输入")
    parser.add_argument("--ai", type=str, help="保存 AI 回复")
    parser.add_argument("--complete", action="store_true", help="标记会话完成")
    parser.add_argument("--check-interrupt", action="store_true", help="检查中断会话")
    args = parser.parse_args()

    global SESSION_ID
    SESSION_ID = os.environ.get("CHATLOG_SESSION_ID")

    if args.init:
        init_session(args.init)
    elif args.user:
        save_user_message(args.user)
    elif args.ai:
        save_ai_response(args.ai)
    elif args.complete:
        complete_session()
    elif args.check_interrupt:
        check_interrupt()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
