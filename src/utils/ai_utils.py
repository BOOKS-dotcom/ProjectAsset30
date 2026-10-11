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


STAGE_LABELS = {"research": "Research AI", "blog": "Blog AI", "note": "Note AI"}


def stage_settings(stage=None):
    validate_settings()
    if stage is None:
        return {"max_output_tokens": config.MAX_OUTPUT_TOKENS,
                "reasoning_effort": config.REASONING_EFFORT}
    if stage not in STAGE_LABELS:
        raise GenerationError("生成段階の設定を確認してください。")
    if not isinstance(config.STAGE_SETTINGS, dict):
        raise GenerationError("段階別設定を確認してください。")
    settings = config.STAGE_SETTINGS.get(stage, {})
    if not isinstance(settings, dict):
        raise GenerationError("段階別設定を確認してください。")
    limit = settings.get("max_output_tokens")
    characters = settings.get("characters", ())
    if (type(limit) is not int or not 0 < limit <= 128000
            or settings.get("reasoning_effort") not in ("none", "low", "medium", "high", "xhigh")
            or not isinstance(characters, (tuple, list)) or len(characters) != 2
            or any(type(v) is not int or v <= 0 for v in characters)
            or characters[0] > characters[1]):
        raise GenerationError("段階別の出力・文字数・推論設定を確認してください。")
    return dict(settings)


def article_length_instruction(stage):
    low, high = stage_settings(stage)["characters"]
    return (f"本文は{low}～{high}文字を目安に、指定された全セクションを簡潔に完成させてください。"
            "主要ポイントは3点以内、具体例は1つまでとし、同じ説明を繰り返さないでください。"
            "文字数は目安であり、必要な注意点と結論を省略しないでください。")


def estimate_usd(input_allowance, calls=1, *, stages=None):
    validate_settings()
    input_price, output_price = config.MODEL_PRICES[config.MODEL]
    output_allowance = (sum(stage_settings(stage)["max_output_tokens"] for stage in stages)
                        if stages is not None else calls * config.MAX_OUTPUT_TOKENS)
    return (input_allowance * input_price + output_allowance * output_price) / 1_000_000


def confirm_cost(input_allowance, calls=1, *, stages=None):
    if stages is not None:
        stages = tuple(stages)
        calls = len(stages)
    estimate = estimate_usd(input_allowance, calls, stages=stages)
    print(f"\nモデル：{config.MODEL} / 最大{calls}回")
    print(f"保守的な費用概算：${estimate:.4f}（約{estimate * config.USD_TO_JPY:.1f}円）")
    if stages is None:
        print(f"出力上限：1回{config.MAX_OUTPUT_TOKENS}トークン（推論を含む）")
    else:
        for stage in stages:
            settings = stage_settings(stage)
            print(f"{STAGE_LABELS[stage]}：出力上限{settings['max_output_tokens']}トークン（推論を含む）／推論{settings['reasoning_effort']}")
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
        # 使用量の欠落・不正値を0円と扱わず、生成結果とは独立して扱う。
        counts = (getattr(usage, "input_tokens", None),
                  getattr(usage, "output_tokens", None))
        if any(type(value) is not int or value < 0 for value in counts):
            self.unknown_usage = True
            return
        self.usages.append(counts)

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


def generate_text(client_factory, prompt, *, session=None, stage=None):
    settings = stage_settings(stage)
    input_size = len(prompt.encode("utf-8"))
    if input_size > config.MAX_INPUT_BYTES:
        raise GenerationError("入力が上限を超えています。テーマや元記事を短くしてください。")
    own_session = session is None
    if own_session:
        if not confirm_cost(input_size, stages=(stage,) if stage else None):
            return None
        session = CostSession()
    request_started = False
    usage_processed = False
    try:
        with client_factory(max_retries=0, timeout=120.0) as client:
            # クライアント初期化だけの失敗はAPI呼び出しに数えない。
            session.attempts += 1
            request_started = True
            response = client.responses.create(
                model=config.MODEL, input=prompt,
                max_output_tokens=settings["max_output_tokens"],
                reasoning={"effort": settings["reasoning_effort"]},
                service_tier="default",
            )
            # 終了処理や記事の検証より先に、受信できた使用量を確保する。
            session.record(getattr(response, "usage", None))
            usage_processed = True
        if response.status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None)
            if not isinstance(reason, str):
                reason = None
            reasons = {"max_output_tokens": "出力上限に到達", "content_filter": "コンテンツフィルターによる停止"}
            label = STAGE_LABELS.get(stage, "生成")
            print(f"\n{label}：未完了。停止理由：{reasons.get(reason, '取得できない／未対応の停止理由')}。")
            counts = (getattr(getattr(response, "usage", None), "input_tokens", None),
                      getattr(getattr(response, "usage", None), "output_tokens", None))
            if all(type(v) is int and v >= 0 for v in counts):
                price = sum(v*p for v,p in zip(counts, config.MODEL_PRICES[config.MODEL])) / 1_000_000
                print(f"使用量：入力{counts[0]}／出力{counts[1]}トークン（推論を含む）。")
                output_details = getattr(getattr(response, "usage", None), "output_tokens_details", None)
                reasoning_tokens = getattr(output_details, "reasoning_tokens", None)
                if type(reasoning_tokens) is int and 0 <= reasoning_tokens <= counts[1]:
                    print(f"出力のうち推論：{reasoning_tokens}トークン。")
                else:
                    print("推論トークンの内訳は取得できませんでした。")
                print(f"この呼び出しの推定費用：${price:.5f}（約{price*config.USD_TO_JPY:.2f}円）。")
                print("税・手数料・割引は含みません。実請求額の上限保証ではありません。")
            else:
                print("使用トークン数と費用を計算できません。請求画面を確認してください。")
            print("未完了の記事は保存せず、次のAIには渡しません。再試行は行いません。")
        if (response.status != "completed" or
                not isinstance(response.output_text, str) or not response.output_text.strip()):
            raise GenerationError("生成が未完了または空でした。保存せず停止しました。出力上限を確認してください。")
        return response.output_text
    except Exception:
        if request_started and not usage_processed:
            session.unknown_usage = True
        raise
    finally:
        if own_session:
            session.show_total()
