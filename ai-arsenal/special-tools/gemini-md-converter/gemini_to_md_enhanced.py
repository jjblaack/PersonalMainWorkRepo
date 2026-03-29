import os
import sys
import json
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def extract_gemini_content_selenium(url):
    """
    使用 Selenium 从 Gemini 对话链接中提取内容（支持 JavaScript 渲染）
    """
    # 设置 Chrome 选项
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # 无头模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    # 设置 WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print("正在加载页面...")
        driver.get(url)

        # 等待页面加载完成
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # 获取页面源码
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 使用配置中的选择器
            config = load_config()
            selectors = config.get('selectors', [])

            conversation_elements = []
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    conversation_elements.extend(elements)

            if not conversation_elements:
                # 备选方案：查找主要内容区域
                main_content = soup.find('main') or soup.find('body')
                if main_content:
                    conversation_elements = main_content.find_all(['div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

            return conversation_elements

        except Exception as e:
            print(f"页面加载过程中出现错误: {e}")
            # 即使等待失败，也尝试获取现有内容
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            main_content = soup.find('main') or soup.find('body')
            if main_content:
                return main_content.find_all(['div', 'p', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            return []

    finally:
        driver.quit()

def extract_gemini_content_static(url):
    """
    使用 requests 从 Gemini 对话链接中提取内容（静态内容）
    """
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # 使用配置中的选择器
        config = load_config()
        selectors = config.get('selectors', [])

        conversation_elements = []
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                conversation_elements.extend(elements)

        if not conversation_elements:
            conversation_elements = soup.find_all(['p', 'div', 'span'])

        return conversation_elements
    except Exception as e:
        print(f"获取网页内容时出现错误: {e}")
        return []

def is_question(text, config):
    """判断文本是否是问题"""
    text_lower = text.lower()

    # 检查问题指示词
    question_indicators = config.get('question_indicators', [])
    for indicator in question_indicators:
        if indicator in text_lower:
            return True

    # 检查是否以问号结尾
    if '?' in text[-20:]:  # 检查文本最后20个字符
        return True

    # 如果文本较短且询问某事，则可能是问题
    if len(text) < 150 and any(indicator in text_lower[:50] for indicator in ['如何', '什么', '怎么', '为何', 'what', 'how', 'why']):
        return True

    return False

def convert_to_markdown(content_elements):
    """
    将提取的内容转换为 Markdown 格式
    """
    markdown_content = []

    # 添加标题
    markdown_content.append("# Gemini 对话记录\n")

    if content_elements:
        config = load_config()

        # 收集所有文本内容，过滤无关内容
        all_texts = []
        for element in content_elements:
            text = element.get_text().strip()
            if text and len(text) > 10:  # 过滤掉过短的文本片段
                # 检查是否应该跳过该文本
                skip_keywords = config.get('skip_keywords', [])
                if not any(keyword in text.lower() for keyword in skip_keywords):
                    all_texts.append(text)

        # 尝试根据内容特征识别问题和答案
        processed_indices = set()

        for i, text in enumerate(all_texts):
            if i in processed_indices:
                continue

            # 检查是否是问题
            if is_question(text, config):
                markdown_content.append(f"\n#### Q: {text}\n")
                processed_indices.add(i)
            else:
                # 如果当前不是问题，检查它是否可能是对前面问题的回答
                markdown_content.append(f"\n#### A: {text}\n")
                processed_indices.add(i)

    if len(markdown_content) <= 1:
        # 如果转换后内容仍然很少，使用备用方案
        markdown_content = ["# Gemini 对话记录\n"]
        config = load_config()
        all_text = []
        for element in content_elements:
            text = element.get_text().strip()
            if text and len(text) > 10:
                skip_keywords = config.get('skip_keywords', [])
                if not any(keyword in text.lower() for keyword in skip_keywords):
                    all_text.append(text)

        # 按顺序添加内容，不过多判断类型
        for i, text in enumerate(all_text):
            markdown_content.append(f"\n#### {'Q' if i % 2 == 0 else 'A'}: {text}\n")

        if len(all_text) == 0:
            markdown_content.append("未能从链接中提取到有意义的内容，请确认链接是否可访问。\n")

    return "\n".join(markdown_content)

def save_to_file(content, filename):
    """
    将 Markdown 内容保存到文件
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Markdown 文件已保存为: {filename}")

def main():
    if len(sys.argv) != 2:
        print("使用方法: python gemini_to_md.py <gemini_conversation_url>")
        sys.exit(1)

    url = sys.argv[1]

    # 验证 URL 格式
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print("错误: 请输入有效的 URL")
        sys.exit(1)

    print("正在获取 Gemini 对话内容...")

    # 首先尝试使用 Selenium 获取内容（支持 JavaScript）
    content_elements = extract_gemini_content_selenium(url)

    # 如果 Selenium 方法没有提取到足够的内容，则回退到静态方法
    if not content_elements or len(content_elements) == 0:
        print("Selenium 方法未获取到足够内容，尝试静态方法...")
        content_elements = extract_gemini_content_static(url)

    if not content_elements:
        print("错误: 无法获取对话内容，请检查链接是否可访问")
        sys.exit(1)

    print("正在转换为 Markdown 格式...")
    markdown_content = convert_to_markdown(content_elements)

    # 生成输出文件名
    filename = "gemini_conversation.md"

    # 检查文件是否存在，如存在则添加数字后缀
    counter = 1
    original_filename = filename
    while os.path.exists(filename):
        name, ext = os.path.splitext(original_filename)
        filename = f"{name}_{counter}{ext}"
        counter += 1

    save_to_file(markdown_content, filename)

if __name__ == "__main__":
    main()