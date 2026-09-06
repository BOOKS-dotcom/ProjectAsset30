from openai import OpenAI
from config import MODEL
from utils.file_utils import save_markdown

client = OpenAI()


def run():
    theme = input("調査テーマを入力してください：")

    response = client.responses.create(
        model=MODEL,
        input=f"""
あなたは優秀なリサーチAIです。

以下のテーマについて調査してください。

テーマ：
{theme}

以下の形式で回答してください。

【概要】

【重要ポイント】

【今後注目すべき点】
"""
    )

    print("\n========================\n")
    print(response.output_text)
    print("\n========================")

    save_markdown("research", theme, response.output_text)