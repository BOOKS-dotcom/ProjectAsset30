"""APIを使用しない、公開前の記事点検。事実確認は行わない。"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from uuid import uuid4
from utils import file_utils

NOTICE = "この結果はルールによる文章・形式の点検です。事実関係・正確性・公開適否を保証しません。公開前に出典と内容を人間が確認してください。"
PROFILES = {
    "research": ("Research", 300, 12000, 2),
    "blog": ("Blog", 600, 16000, 3),
    "note": ("Note", 400, 12000, 3),
}


@dataclass(frozen=True)
class Check:
    name: str
    detail: str
    issues: tuple
    suggestions: tuple

    @property
    def passed(self):
        return not self.issues


@dataclass(frozen=True)
class Report:
    folder: str
    theme: str
    character_count: int
    checks: tuple
    source_sha256: str = ""

    @property
    def passed(self):
        return all(check.passed for check in self.checks)


def _parse(content):
    headings, body, problems = [], [], []
    fence = None
    lines = content.splitlines()
    for number, line in enumerate(lines, 1):
        if fence:
            if re.match(r"^ {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*$", line):
                fence = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opening:
            marker = opening.group(1)
            fence = (marker[0], len(marker), number)
            continue
        if re.match(r"^(?: {4}|\t)", line):
            continue  # インデントされたコード
        heading = re.match(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)$", line)
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading.group(2) or "").strip()
            headings.append((len(heading.group(1)), title, number))
            if not title:
                problems.append(f"{number}行目：見出しの内容が空です。")
            continue
        if re.match(r"^ {0,3}#{7,}(?:\s|$)", line):
            problems.append(f"{number}行目：見出しの#は6個までです。")
        if re.match(r"^ {0,3}#{1,6}[^#\s]", line):
            problems.append(f"{number}行目：#の後に空白のない見出し候補があります。")
        if (re.match(r"^ {0,3}(=+|-+)\s*$", line) and body
                and body[-1][0] == number - 1 and body[-1][1].strip()):
            previous_number, title = body.pop()
            headings.append((1 if line.strip().startswith("=") else 2, title.strip(), previous_number))
            continue
        if not line.strip() or re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", line):
            continue
        # Markdownの箇条書き・引用記号やリンクだけを本文と見なさない。
        text = re.sub(r"^\s*(?:>\s*|[-+*]\s+|\d+[.)]\s+)+", "", line)
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
        body.append((number, text))
    if fence:
        problems.append(f"{fence[2]}行目：閉じられていないコードフェンスがあります。")
    prose = "\n".join(text for _, text in body)
    if len(re.findall(r"(?<!\\)\*\*", re.sub(r"`[^`]*`", "", prose))) % 2:
        problems.append("太字記号 ** の対応が取れていない可能性があります。")
    if re.search(r"\[[^]\n]*\]\(\s*\)", prose):
        problems.append("URLが空のMarkdownリンクがあります。")
    return headings, body, problems


def check_article(content, folder, theme):
    if folder not in PROFILES:
        raise ValueError("Research・Blog・Noteから選択してください。")
    theme = file_utils.validate_theme(theme)
    _, minimum, maximum, section_minimum = PROFILES[folder]
    headings, body, markdown_issues = _parse(content)
    prose = "\n".join(text for _, text in body)
    visible = re.sub(r"\[([^]\n]+)\]\([^)]*\)", r"\1", prose)
    visible = re.sub(r"[*_`~]", "", visible)
    count = len(re.sub(r"\s", "", visible))
    length_issues = []
    if count < minimum:
        length_issues.append(f"本文が目安の{minimum}文字未満です（{count}文字）。")
    if count > maximum:
        length_issues.append(f"本文が目安の{maximum}文字を超えています（{count}文字）。")
    heading_issues = []
    titles = sum(level == 1 for level, _, _ in headings)
    sections = sum(level >= 2 for level, _, _ in headings)
    if titles != 1:
        heading_issues.append(f"タイトル見出し（#）は1つを目安にしてください（現在{titles}個）。")
    if sections < section_minimum:
        heading_issues.append(f"本文の見出しが不足しています（現在{sections}個、目安{section_minimum}個以上）。")
    previous = 0
    for level, _, line in headings:
        if level > previous + 1:
            heading_issues.append(f"{line}行目：見出しの階層が飛んでいます。")
        previous = level
    repeated = Counter()
    for _, text in body:
        for sentence in re.split(r"[。！？!?]|(?<=\.)\s+", text):
            normalized = re.sub(r"\s|[*_`~]", "", sentence).strip()
            if len(normalized) >= 20:
                repeated[normalized] += 1
    duplicate_count = sum(times > 1 for times in repeated.values())
    unfinished = []
    for number, text in body + [(line, title) for _, title, line in headings]:
        if re.search(r"ここに入力|ここに記入|本文を入力|タイトルを入力|\b(?:TODO|TBD|FIXME)\b", text, re.IGNORECASE):
            unfinished.append(f"{number}行目：未完成表現の候補があります。")
    def item(name, detail, issues, suggestion):
        return Check(name, detail, tuple(issues), (suggestion,) if issues else ())
    checks = (
        item("文字数", f"本文{count}文字／目安{minimum}～{maximum}文字", length_issues,
             "用途に応じて説明・具体例を補うか、冗長な箇所を整理してください。"),
        item("見出し構成", f"タイトル{titles}個／本文見出し{sections}個", heading_issues,
             "#のタイトルを1つ置き、##や###で段階的に本文を整理してください。"),
        item("本文", "空でない本文の確認", [] if count else ["見出し以外の本文が空です。"],
             "コードや見出しだけでなく、読者向けの説明を追加してください。"),
        item("重複文章", "20文字以上の同一文・同一行を点検", [f"同じ長文の繰り返しが{duplicate_count}種類あります。"] if duplicate_count else [],
             "繰り返しが必要な引用かを確認し、不要な文を削るか書き換えてください。"),
        item("未完成表現", "TODO等の候補を点検", unfinished,
             "仮置きの表現を完成させ、説明・引用として必要な場合は意図を確認してください。"),
        item("Markdown形式", "見出し・コードフェンス・太字・空リンクの基本点検", markdown_issues,
             "指摘箇所の記号を修正し、Markdownプレビューで表示を確認してください。"),
    )
    return Report(folder, theme, count, checks)


def _escape(text):
    # テーマ由来のMarkdown記号やHTMLを報告書の構造として解釈させない。
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|])", r"\\\1", text)


def render_report(report):
    lines = ["# 記事品質チェック", "", f"- 記事：{PROFILES[report.folder][0]} / {_escape(report.theme)}",
             f"- 総合結果：{'合格' if report.passed else '要確認'}（ルール上の判定）",
             "- API料金：0円（API呼び出しなし）", f"- 注意：{NOTICE}"]
    if report.source_sha256:
        lines.append(f"- 点検時の記事SHA-256：{report.source_sha256}")
    lines.extend(["", "## チェック項目", "", "| 項目 | 結果 | 詳細 |", "|---|---|---|"])
    for check in report.checks:
        lines.append(f"| {check.name} | {'合格' if check.passed else '要確認'} | {_escape(check.detail)} |")
    lines.extend(["", "## 問題点", ""])
    problems = [f"{check.name}：{issue}" for check in report.checks for issue in check.issues]
    lines.extend(f"- {_escape(problem)}" for problem in problems)
    if not problems:
        lines.append("- 対象ルールで問題候補は見つかりませんでした。内容の正確性は未検証です。")
    lines.extend(["", "## 改善案", ""])
    suggestions = [f"{check.name}：{advice}" for check in report.checks for advice in check.suggestions]
    lines.extend(f"- {_escape(suggestion)}" for suggestion in suggestions)
    if not suggestions:
        lines.append("- 出典・事実関係・読者に適した内容かを人間が確認してください。")
    return "\n".join(lines) + "\n"


def check_saved_article(folder, theme):
    if folder not in PROFILES:
        raise ValueError("Research・Blog・Noteから選択してください。")
    theme = file_utils.validate_theme(theme)
    root = Path(file_utils.__file__).resolve().parent.parent.parent
    source = root / "data" / folder / f"{theme}.md"
    content = source.read_bytes()
    result = check_article(content.decode("utf-8-sig"), folder, theme)
    result = Report(result.folder, result.theme, result.character_count, result.checks,
                    hashlib.sha256(content).hexdigest())
    directory = root / "data" / "quality" / folder / theme
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"{stamp}_{uuid4().hex}.md"
    rendered = render_report(result)
    created = False
    try:
        with destination.open("x", encoding="utf-8") as output:
            created = True
            output.write(rendered)
    except Exception:
        if created and destination.exists():
            destination.unlink()  # この処理で作成した不完全な報告書だけを除去
        raise
    return result, destination


def run():
    print("\n記事品質チェック（API料金0円）")
    print(NOTICE)
    print("1. Research\n2. Blog\n3. Note\n0. 戻る")
    folder = {"1": "research", "2": "blog", "3": "note"}.get(input("記事の種類を選択してください："))
    if folder is None:
        return
    try:
        themes = file_utils.list_markdown(folder)
    except OSError:
        print("記事一覧を読み込めませんでした。保存先を確認してください。")
        return
    if not themes:
        print("チェックできる記事がありません。")
        return
    for number, theme in enumerate(themes, 1):
        print(f"{number}. {theme}")
    choice = input("記事の番号を入力してください（0で戻る）：")
    if choice == "0":
        return
    try:
        index = int(choice)
        if not 1 <= index <= len(themes):
            raise ValueError
        report, path = check_saved_article(folder, themes[index - 1])
    except (ValueError, OSError, UnicodeError):
        print("品質チェックを保存できませんでした。番号、記事の文字コード、保存先を確認してください。")
        return
    print(render_report(report))
    print(f"チェック結果を保存しました：{path}")


if __name__ == "__main__":
    run()
