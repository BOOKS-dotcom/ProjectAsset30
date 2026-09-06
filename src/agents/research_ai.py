from openai import OpenAI
from pathlib import Path

client = OpenAI()


def run():
    theme = input("調査テーマを入力してください：")

    response = client.responses.create(
        model="gpt-5.5",
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

    project_root = Path(__file__).resolve().parent.parent.parent
    research_dir = project_root / "data" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)

    file_path = research_dir / f"{theme}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# {theme}\n\n")
        f.write(response.output_text)

    print(f"\n調査結果を保存しました：{file_path}")