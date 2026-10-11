"""単独リサーチの入口。共通の費用確認・保存履歴を利用する。"""
from agents.research_ai import run
from utils.ai_utils import GenerationError


def main():
    try:
        run()
    except GenerationError as error:
        print(error)
    except Exception:
        print("実行を停止しました。テーマ、API設定、接続、保存先を確認してください。")


if __name__ == "__main__":
    main()
