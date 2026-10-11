from openai import OpenAI
from utils.ai_utils import generate_text, article_length_instruction
from utils.file_utils import (
    save_markdown,
    validate_theme,
    load_markdown,
    list_markdown,
)


def run(theme=None, *, session=None):

    if theme is None:
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
            index = int(choice)
            if not 1 <= index <= len(themes):
                raise ValueError
            theme = themes[index - 1]

        except (ValueError, IndexError):
            print("無効な番号です。")
            return

    theme = validate_theme(theme)

    # 調査結果を読み込む
    research_content = load_markdown("research", theme)

    # ブログ生成
    content = generate_text(
        OpenAI, f"""
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

・{article_length_instruction("blog")}
・Markdown形式で出力してください。
・記事タイトルは保存側が付与するため、# タイトルは出力しないでください。
・本文の主要見出しは ##、小見出しは ### を使用してください。
・見出しを ** で囲まないでください。
・コードブロック（```）で囲まないでください。
・そのまま .md ファイルとして保存できる形式で出力してください。

以下の形式で出力してください。

## 導入

## 本文

## まとめ
""", session=session, stage="blog"
    )
    if content is None:
        return

    print("\n========================\n")
    print(content)
    print("\n========================")

    save_markdown("blog", theme, content)
