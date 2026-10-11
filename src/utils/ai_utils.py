from dataclasses import dataclass, field
import math
import config


class GenerationError(RuntimeError):
    """機密情報を含まない、利用者に表示できる生成エラー。"""


def validate_settings():
    if config.MODEL not in config.MODEL_PRICES:
        raise GenerationError("モデルの料金設定がありません。config.pyを確認してください。")
    for value in (config.MAX_OUTPUT_TOKENS, config.MAX_INPUT_BYTES):
        if type(value) is not int or value <= 0:
            raise GenerationError("入力・出力の上限は正の整数にしてください。")
    if config.MAX_OUTPUT_TOKENS > 128000:
        raise GenerationError("出力上限がモデルの対応範囲を超えています。")
    values = (*config.MODEL_PRICES[config.MODEL], config.USD_TO_JPY)
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise GenerationError("料金・換算レートは正の有限値にしてください。")
    if config.REASONING_EFFORT not in ("none", "low", "medium", "high", "xhigh"):
        raise GenerationError("推論設定を確認してください。")


def estimate_usd(input_allowance, calls=1):
    validate_settings()
    input_price, output_price = config.MODEL_PRICES[config.MODEL]
    return (input_allowance * input_price +
            calls * config.MAX_OUTPUT_TOKENS * output_price) / 1_000_000


def confirm_cost(input_allowance, calls=1):
    estimate = estimate_usd(input_allowance, calls)
    print(f"\nモデル：{config.MODEL} / 最大{calls}回")
    print(f"保守的な費用概算：${estimate:.4f}（約{estimate * config.USD_TO_JPY:.1f}円）")
    print(f"出力上限：1回{config.MAX_OUTPUT_TOKENS}トークン（推論を含む）")
    print(f"円換算は1ドル={config.USD_TO_JPY:g}円の仮定です。")
    print("入力のUTF-8バイト数をトークン数の目安にした概算です。実請求の上限保証ではありません。")
    if input("この費用目安で実行しますか？ [y/N]：").strip().lower() != "y":
        print("実行をキャンセルしました。")
        return False
    return True


@dataclass
class CostSession:
    usages: list = field(default_factory=list)
    attempts: int = 0
    unknown_usage: bool = False

    def record(self, usage):
        if usage is None:
            self.unknown_usage = True
            return
        self.usages.append((usage.input_tokens, usage.output_tokens))

    def show_total(self):
        if not self.attempts:
            return
        input_price, output_price = config.MODEL_PRICES[config.MODEL]
        total = sum(i * input_price + o * output_price for i, o in self.usages) / 1_000_000
        if self.usages:
            print(f"\n取得できた使用量による費用：${total:.4f}（約{total * config.USD_TO_JPY:.1f}円）")
            print("キャッシュ割引・税・手数料は含みません。請求画面の金額を確認してください。")
        else:
            print("\n使用量を取得できず、費用を計算できませんでした。請求画面を確認してください。")
        if self.unknown_usage:
            print("使用量が取得できない呼び出しがあります。上記の金額には含まれません。")


def generate_text(client_factory, prompt, *, session=None):
    validate_settings()
    input_size = len(prompt.encode("utf-8"))
    if input_size > config.MAX_INPUT_BYTES:
        raise GenerationError("入力が上限を超えています。テーマや元記事を短くしてください。")
    own_session = session is None
    if own_session:
        if not confirm_cost(input_size):
            return None
        session = CostSession()
    session.attempts += 1
    try:
        with client_factory(max_retries=0, timeout=120.0) as client:
            response = client.responses.create(
                model=config.MODEL, input=prompt,
                max_output_tokens=config.MAX_OUTPUT_TOKENS,
                reasoning={"effort": config.REASONING_EFFORT},
                service_tier="default",
            )
        session.record(response.usage)
        if response.status != "completed" or not response.output_text.strip():
            raise GenerationError("生成が未完了または空でした。保存せず停止しました。出力上限を確認してください。")
        return response.output_text
    except Exception:
        if len(session.usages) < session.attempts:
            session.unknown_usage = True
        raise
    finally:
        if own_session:
            session.show_total()
