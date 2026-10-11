# モデルと費用管理（標準API料金、2026-10-11確認）
MODEL = "gpt-5.5"
MAX_OUTPUT_TOKENS = 3000  # 推論を含む出力上限
MAX_INPUT_BYTES = 12000  # 大きな元記事はAPI送信前に停止
REASONING_EFFORT = "low"
USD_TO_JPY = 150.0  # 表示用の仮定。実際の為替・税・手数料は含まない
# https://developers.openai.com/api/docs/models/gpt-5.5
MODEL_PRICES = {"gpt-5.5": (5.0, 30.0)}  # 入力・出力 / 100万トークン

# 段階別の本文量の目安。文字数はトークン数ではなく、完了を保証しない。
STAGE_SETTINGS = {
    "research": {"characters": (600, 900), "max_output_tokens": 3000, "reasoning_effort": "none"},
    "blog": {"characters": (900, 1200), "max_output_tokens": 3500, "reasoning_effort": "none"},
    "note": {"characters": (700, 1000), "max_output_tokens": 3000, "reasoning_effort": "none"},
}
