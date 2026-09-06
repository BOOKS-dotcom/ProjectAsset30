from openai import OpenAI
from config import MODEL
from utils.file_utils import save_markdown

client = OpenAI()


def run():

    theme = input("ブログ化するテーマを入力してください：")

    response = client.responses.create(
        model=MODEL,
        input=f"""
あなたはプロのブログライターです。

以下のテーマについて、SEOを意識したブログ記事を書いてください。

テーマ
{theme}

以下の形式で出力してください。

# タイトル

## 導入

## 本文

## まとめ
"""
    )

    print("\n========================\n")
    print(response.output_text)
    print("\n========================")

    save_markdown("blog", theme, response.output_text)