from pathlib import Path
from openai import OpenAI

# OpenAIクライアント作成
client = OpenAI()

# 調査テーマを入力
theme = input("調査テーマを入力してください：")

# AIへ問い合わせ
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

# 結果を画面表示
print("\n========================\n")
print(response.output_text)
print("\n========================")

# プロジェクトルートを取得
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 保存先フォルダ
research_dir = PROJECT_ROOT / "data" / "research"
research_dir.mkdir(parents=True, exist_ok=True)

# 保存ファイル名
file_path = research_dir / f"{theme}.md"

# Markdownファイルとして保存
with open(file_path, "w", encoding="utf-8") as f:
    f.write(f"# {theme}\n\n")
    f.write(response.output_text)

print(f"\n調査結果を保存しました：")
print(file_path)