# ProjectAsset30
-Week1 Started
## 実行方法

Python環境で `pip install -r requirements.txt` を実行し、環境変数
`OPENAI_API_KEY` を設定してください。キーをソースやMarkdownに記載しないでください。
モデルは `src/config.py` の既存設定を使用します。

```sh
python src/manager.py
```

既存のメニュー1～3は手動実行です。メニュー6「自動実行」を選び、調査テーマを
1回入力すると、Research AI → Blog AI → Note AI の順に実行します。
各段階で `data/research/<テーマ>.md`、`data/blog/<テーマ>.md`、
`data/note/<テーマ>.md` にUTF-8で保存し、次のAIは直前に保存された記事を読み込みます。
同じテーマの既存ファイルは従来どおり上書きします。
空のテーマ、パス区切り、Windowsで使用できないファイル名などは拒否します。

API呼び出しや保存に失敗すると後続を停止してメニューに戻ります。
保存済みの結果は残ります（全段階を巻き戻す機能や自動再試行はありません）。
既存の `src/main.py` の単独リサーチ実行も変更していません。

## テスト

```sh
python -m unittest discover -s tests -v
```

API境界をモックし、一時ディレクトリへ実際にMarkdownを保存します。
APIキー・外部通信・API利用料金は不要です。
