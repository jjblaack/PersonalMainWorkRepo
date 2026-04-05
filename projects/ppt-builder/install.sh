#!/bin/bash

# 安装脚本用于设置PPT构建器的依赖

echo "正在安装PPT构建器依赖..."

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt &>/dev/null; then
        echo "检测到Ubuntu/Debian，正在安装依赖..."
        sudo apt update
        sudo apt install -y pandoc texlive-full
    elif command -v yum &>/dev/null; then
        echo "检测到CentOS/RHEL，正在安装依赖..."
        sudo yum install -y pandoc texlive-scheme-full
    else
        echo "请手动安装pandoc和texlive-full"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command -v brew &>/dev/null; then
        echo "检测到Homebrew，正在安装依赖..."
        brew install pandoc
        # 询问用户是否需要LaTeX支持
        read -p "是否需要PDF输出支持？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "正在安装LaTeX..."
            # 提供两种选择：完整版或基础版
            echo "选择LaTeX版本:"
            echo "1) basictex (较小，约100MB)"
            echo "2) mactex-no-gui (完整版，约4GB)"
            read -p "请输入选择 (1 or 2): " choice
            if [ "$choice" = "1" ]; then
                brew install --cask basictex
            else
                brew install --cask mactex-no-gui
            fi
        fi
    else
        echo "请先安装Homebrew，然后运行此脚本"
        echo "安装Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi
else
    echo "请手动安装pandoc"
    echo "Windows用户请参阅: https://pandoc.org/installing.html"
fi

echo "依赖安装完成！"
echo ""
echo "要测试安装是否成功，请运行:"
echo "  pandoc --version"
echo ""
echo "要开始使用，请参阅USAGE.md文档"