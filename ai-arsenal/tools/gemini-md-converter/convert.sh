#!/bin/bash

# Gemini 对话转 Markdown 工具使用脚本

echo "==========================================="
echo "Gemini 对话转 Markdown 工具"
echo "==========================================="

if [ $# -eq 0 ]; then
    echo "用法: $0 <gemini_share_url>"
    echo "示例: $0 https://gemini.google.com/share/abc123"
    exit 1
fi

URL=$1

echo "正在转换链接: $URL"
echo "==========================================="

# 运行转换脚本
python gemini_to_md.py "$URL"

echo "==========================================="
echo "转换完成！"
echo "请查看生成的 Markdown 文件。"