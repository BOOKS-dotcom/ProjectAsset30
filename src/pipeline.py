from agents.research_ai import run as research_run
from agents.blog_ai import run as blog_run
from agents.note_ai import run as note_run
from utils.file_utils import validate_theme
from utils.ai_utils import CostSession, confirm_cost
import config


def run(theme: str):
    """費用確認後、同じテーマで順次生成・保存する。"""
    theme = validate_theme(theme)
    if not confirm_cost(config.MAX_INPUT_BYTES * 3, stages=("research", "blog", "note")):
        return
    session = CostSession()
    try:
        for label, runner in (("Research AI", research_run),
                              ("Blog AI", blog_run), ("Note AI", note_run)):
            print(f"\n{label} を実行します。")
            runner(theme, session=session)
        print("\n自動実行が完了しました。")
    finally:
        session.show_total()
