from agents.research_ai import run

print("======================")
print(" Project Asset30")
print("======================")
print("1. Research AI")
print("0. 終了")

choice = input("番号を入力してください：")

if choice == "1":
    run()
elif choice == "0":
    print("終了します。")
else:
    print("無効な番号です。")