from openai import OpenAI
from config import MODEL
from utils.file_utils import (
    save_markdown,
    load_markdown,
    list_markdown,
)

client = OpenAI()


def run():

    # 調査済みテーマ一覧を取得
    themes = list_markdown("research")

    if not themes:
        print("調査済みテーマがありません。")
        print("先に Research AI を実行してください。")
        return

    print("\n========================")
    print("     調査済みテーマ")
    print("========================")

    for i, theme in enumerate(themes, start=1):
        print(f"{i}. {theme}")

    print("0. 戻る")

    choice = input("\n番号を入力してください：")

    if choice == "0":
        return

    try:
        theme = themes[int(choice) - 1]

    except (ValueError, IndexError):
        print("無効な番号です。")
        return

    # 調査結果を読み込む
    research_content = load_markdown("research", theme)

    # ブログ生成
    response = client.responses.create(
        model=MODEL,
        input=f"""
あなたはプロのブログライターです。

以下は調査担当AIが作成した調査レポートです。

この内容をもとに、

・初心者にも分かりやすい
・SEOを意識した
・読みやすいブログ記事

を書いてください。

-------------------------

{research_content}

-------------------------

以下のルールを守ってください。

・Markdown形式で出力してください。
・見出しは #、##、### を使用してください。
・見出しを ** で囲まないでください。
・コードブロック（```）で囲まないでください。
・そのまま .md ファイルとして保存できる形式で出力してください。

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