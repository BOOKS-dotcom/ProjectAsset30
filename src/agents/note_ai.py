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
        # ブログ記事一覧を取得
        themes = list_markdown("blog")

        if not themes:
            print("ブログ記事がありません。")
            print("先に Blog AI を実行してください。")
            return

        print("\n========================")
        print("     ブログ記事一覧")
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

    # ブログ記事を読み込む
    blog_content = load_markdown("blog", theme)

    # Note記事を生成
    content = generate_text(
        OpenAI, f"""
あなたはnote.com向けの記事を作成するプロのライターです。

以下はBlog AIが作成したブログ記事です。

この内容をもとに、
note.comで読みやすく、最後まで読んでもらいやすい記事に
再構成してください。

-------------------------

{blog_content}

-------------------------

以下のルールを守ってください。

・ブログ記事をそのままコピーするのではなく、note向けに再構成してください。
・初心者にも分かりやすい文章にしてください。
・読者が「自分にも関係がある」と感じられる導入にしてください。
・適度に改行してください。
・見出しを使って読みやすくしてください。
・専門用語には簡単な説明を入れてください。
・読者にとって役立つ具体例を入れてください。
・最後に内容を簡潔にまとめてください。
・{article_length_instruction("note")}
・Markdown形式で出力してください。
・記事タイトルは保存側が付与するため、# タイトルは出力しないでください。
・本文の主要見出しは ##、小見出しは ### を使用してください。
・見出しを ** で囲まないでください。
・コードブロック（```）で囲まないでください。
・そのまま .md ファイルとして保存できる形式で出力してください。

以下の形式を基本としてください。

## 導入

## 本文

### ポイント1

### ポイント2

### ポイント3

## まとめ
""", session=session, stage="note"
    )
    if content is None:
        return

    print("\n========================\n")
    print(content)
    print("\n========================")

    # Note記事を保存
    save_markdown("note", theme, content)
