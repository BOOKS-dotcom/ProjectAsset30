from agents.research_ai import run as research_run
from agents.blog_ai import run as blog_run

while True:
    print("\n======================")
    print("   Project Asset30")
    print("======================")
    print("1. Research AI")
    print("2. Blog AI")
    print("3. Note AI（準備中）")
    print("4. YouTube AI（準備中）")
    print("5. Translation AI（準備中）")
    print("0. 終了")

    choice = input("番号を入力してください：")

    if choice == "1":
       research_run()

    elif choice == "2":
       blog_run()

    elif choice in ["3", "4", "5"]:
        print("現在開発中です")

    elif choice == "0":
        print("Project Asset30 を終了します。")
        break

    else:
        print("無効な番号です。")