#!/usr/bin/env python3
"""
Claude Chatlog - 索引生成器

用法:
    python update_index.py
    python update_index.py --type date
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

CHATLOG_ROOT = Path(os.environ.get("CHATLOG_ROOT", Path(__file__).parent.parent / "chatlog"))
SESSIONS_DIR = CHATLOG_ROOT / "sessions"
INDEX_DIR = CHATLOG_ROOT / "index"


def ensure_dirs():
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def scan_sessions():
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for session_dir in sorted(SESSIONS_DIR.iterdir()):
        if not session_dir.is_dir():
            continue
        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            continue
        metadata = json.loads(metadata_file.read_text())
        sessions.append({"session_id": session_dir.name, "metadata": metadata, "path": session_dir})
    return sessions


def categorize_topic(topic: str) -> str:
    if not topic:
        return "未分类"
    categories = {
        "学习": ["考研", "软考", "考试", "学习"],
        "技术": ["编程", "代码", "Python", "AI", "开发", "工具"],
        "工作": ["工作", "项目", "需求", "产品"],
    }
    for cat, kws in categories.items():
        for kw in kws:
            if kw.lower() in topic.lower():
                return cat
    return "其他"


def generate_date_index(sessions):
    lines = ["# 会话索引 - 按日期\n\n", f"> 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"]
    by_date = defaultdict(list)
    for s in sessions:
        by_date[s["session_id"][:10]].append(s)
    for date in sorted(by_date.keys(), reverse=True):
        lines.append(f"## {date}\n\n")
        for s in sorted(by_date[date], key=lambda x: x["session_id"], reverse=True):
            icon = "✓" if s["metadata"].get("status") == "completed" else "○"
            lines.append(f"- {icon} [{s['session_id']}]({s['path']}/transcript.md) - {s['metadata'].get('topic', '无主题')}\n")
        lines.append("\n")
    return "".join(lines)


def generate_topic_index(sessions):
    lines = ["# 会话索引 - 按主题\n\n", f"> 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"]
    by_cat = defaultdict(list)
    for s in sessions:
        cat = categorize_topic(s["metadata"].get("topic", ""))
        by_cat[cat].append(s)
    for cat in sorted(by_cat.keys()):
        lines.append(f"## {cat}\n\n")
        for s in sorted(by_cat[cat], key=lambda x: x["session_id"], reverse=True):
            icon = "✓" if s["metadata"].get("status") == "completed" else "○"
            topic = s["metadata"].get("topic", "") or s["session_id"]
            lines.append(f"- {icon} [{topic}]({s['path']}/transcript.md)\n")
        lines.append("\n")
    return "".join(lines)


def generate_recent_summary(sessions, n=10):
    lines = ["# 最近会话\n\n", f"> 最近 {n} 条 | 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"]
    sorted_sessions = sorted(sessions, key=lambda x: x["metadata"].get("updated_at", x["metadata"].get("created_at", "")), reverse=True)[:n]
    for s in sorted_sessions:
        m = s["metadata"]
        icon = "✓" if m.get("status") == "completed" else "○"
        lines.append(f"## {icon} {s['session_id']}\n\n")
        lines.append(f"- 主题：{m.get('topic', '无')}\n")
        lines.append(f"- 时间：{m.get('created_at', '')[:16]}\n")
        lines.append(f"- 消息数：{len(m.get('messages', []))}\n\n")
    return "".join(lines)


def update_all():
    ensure_dirs()
    sessions = scan_sessions()
    if not sessions:
        print("没有会话")
        return
    (INDEX_DIR / "by_date.md").write_text(generate_date_index(sessions))
    (INDEX_DIR / "by_topic.md").write_text(generate_topic_index(sessions))
    (INDEX_DIR / "recent.md").write_text(generate_recent_summary(sessions))
    print(f"✓ 索引已更新 ({len(sessions)} 个会话)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="索引生成器")
    parser.add_argument("--type", choices=["date", "topic", "recent", "all"], default="all")
    args = parser.parse_args()
    sessions = scan_sessions()
    if args.type == "date":
        print(generate_date_index(sessions))
    elif args.type == "topic":
        print(generate_topic_index(sessions))
    elif args.type == "recent":
        print(generate_recent_summary(sessions))
    else:
        update_all()


if __name__ == "__main__":
    main()
