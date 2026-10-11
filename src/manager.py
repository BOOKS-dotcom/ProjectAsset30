from agents.research_ai import run as research_run
from agents.blog_ai import run as blog_run
from agents.note_ai import run as note_run
from pipeline import run as pipeline_run


def main():
    while True:
        print("\n======================")
        print("   Project Asset30")
        print("======================")
        print("1. Research AI")
        print("2. Blog AI")
        print("3. Note AI")
        print("4. YouTube AI（準備中）")
        print("5. Translation AI（準備中）")
        print("6. 自動実行（Research → Blog → Note）")
        print("0. 終了")

        choice = input("番号を入力してください：")

        if choice == "1":
            research_run()

        elif choice == "2":
            blog_run()

        elif choice == "3":
            note_run()

        elif choice == "6":
            theme = input("調査テーマを入力してください：")
            try:
                pipeline_run(theme)
            except Exception:
                # API例外には機密情報が含まれる可能性があるため表示しない。
                print("自動実行を停止しました。テーマ、API設定、接続、保存先を確認してください。保存済みの結果は残ります。")

        elif choice in ["4", "5"]:
            print("現在開発中です")

        elif choice == "0":
            print("Project Asset30 を終了します。")
            break

        else:
            print("無効な番号です。")

if __name__ == "__main__":
    main()
