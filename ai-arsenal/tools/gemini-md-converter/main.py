#!/usr/bin/env python3
"""
Gemini 对话链接转 Markdown 工具
主入口点
"""

import argparse
import sys
import os

# 添加当前目录到路径，以便导入模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gemini_to_md import main as gemini_main

def main():
    parser = argparse.ArgumentParser(
        description="将 Gemini 对话链接转换为 Markdown 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s <gemini_conversation_url>
        """
    )

    parser.add_argument(
        'url',
        nargs='?',
        help='Gemini 对话链接'
    )

    parser.add_argument(
        '-o', '--output',
        dest='output_file',
        help='指定输出文件名 (默认: gemini_conversation.md)'
    )

    args = parser.parse_args()

    if not args.url:
        print("错误: 请提供 Gemini 对话链接")
        print("\n使用方法: python main.py <gemini_conversation_url>")
        sys.exit(1)

    # 设置参数以便在原主函数中使用
    sys.argv = ['gemini_to_md.py', args.url]
    gemini_main()

if __name__ == "__main__":
    main()