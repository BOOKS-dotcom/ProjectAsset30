from agents.research_ai import run as research_run
from agents.blog_ai import run as blog_run
from agents.note_ai import run as note_run
from utils.file_utils import validate_theme


def run(theme: str):
    """同じテーマで順次生成・保存する。失敗時は後続を実行しない。"""
    theme = validate_theme(theme)
    for label, runner in (("Research AI", research_run),
                          ("Blog AI", blog_run), ("Note AI", note_run)):
        print(f"\n{label} を実行します。")
        runner(theme)
    print("\n自動実行が完了しました。")
