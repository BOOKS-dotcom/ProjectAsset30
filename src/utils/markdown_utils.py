"""新規記事だけの見出し整理。文章の意味や内容は変更しない。"""
import re


def normalize_headings(title, content):
    """先頭の同名タイトルだけを統合し、判断できない階層は保持する。"""
    lines = content.splitlines(keepends=True)
    output, warnings, headings = list(lines), [], []
    ambiguous = False
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    removed_title = False
    fence = None
    for number, line in enumerate(lines, 1):
        text = line.rstrip("\r\n")
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", text):
                fence = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", text)
        if opening:
            marker = opening[1]
            fence = (marker[0], len(marker), number)
            continue
        if text.startswith(("    ", "\t")) or re.match(r"^ {0,3}>", text):
            continue
        heading = re.fullmatch(r" {0,3}(#{1,6})[ \t]+(.+?)", text)
        if not heading:
            if re.match(r"^ {0,3}#{1,}(?:\s|[^#])", text):
                ambiguous = True
                warnings.append(f"{number}行目：空または形式不明の見出し候補は変更していません。")
            if re.fullmatch(r" {0,3}(=+|-+)\s*", text) and number > 1 and lines[number - 2].strip():
                ambiguous = True
                warnings.append(f"{number}行目：下線形式の見出し／区切り線は変更していません。")
            continue
        level = len(heading[1])
        label = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2]).strip()
        if not label:
            ambiguous = True
            warnings.append(f"{number}行目：内容のない見出しは変更していません。")
            continue
        if level == 1 and label == title and number - 1 == first:
            output[number - 1] = ""
            removed_title = True
            continue
        if label == title:
            warnings.append(f"{number}行目：本文中の同名見出しは意味を保持するため残しました。")
        if level == 1:
            ambiguous = True
            warnings.append(f"{number}行目：本文中の#見出しは意味を判断できないため保持しました。")
        headings.append((number - 1, level, heading))
    if fence:
        warnings.append(f"{fence[2]}行目：閉じられていないコードフェンスは変更していません。")
    # 本文全体が同じだけ深く始まる場合のみ一律に移動する。
    # 内部の飛びは親の欠落か意図した構造か判別できないため補わない。
    offset = 0
    if headings and not ambiguous and not fence:
        minimum = min(level for _, level, _ in headings)
        levels = [level for _, level, _ in headings]
        if minimum >= 3 and levels[0] == minimum and all(
                following <= previous + 1 for previous, following in zip(levels, levels[1:])):
            offset = minimum - 2
    previous = 1
    for index, level, heading in headings:
        target = level - offset
        if target > 3:
            warnings.append(f"{index + 1}行目：3段を超える階層は保持しました。")
        if target > previous + 1:
            warnings.append(f"{index + 1}行目：見出し階層の飛びは判断できないため保持しました。")
        previous = target
        if offset:
            # 記号だけを置換し、空白・見出し文言・改行は元のまま保持する。
            start, end = heading.span(1)
            output[index] = lines[index][:start] + "#" * target + lines[index][end:]
    body = "".join(output)
    if removed_title:
        body = body.lstrip("\r\n")
    return f"# {title}\n\n" + body, tuple(warnings)
