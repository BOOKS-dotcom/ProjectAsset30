from openai import OpenAI
from utils.ai_utils import generate_text
from utils.file_utils import save_markdown, validate_theme


def run(theme=None, *, session=None):
    if theme is None:
        theme = input("調査テーマを入力してください：")
    theme = validate_theme(theme)

    content = generate_text(
        OpenAI, f"""
あなたは優秀なリサーチAIです。

以下のテーマについて調査してください。

テーマ：
{theme}

以下のルールを守ってください。

・Markdown形式で出力してください。
・記事タイトルは保存側が付与するため、# タイトルは出力しないでください。
・本文の主要見出しは ##、小見出しは ### を使用してください。
・見出しを ** で囲まないでください。
・コードブロックでMarkdownを囲まないでください。
・そのまま .md ファイルとして保存できる形式で出力してください。

以下の形式で回答してください。

## 概要

## 重要ポイント

## 今後注目すべき点
""", session=session
    )
    if content is None:
        return

    print("\n========================\n")
    print(content)
    print("\n========================")

    save_markdown("research", theme, content)
