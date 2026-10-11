"""新規記事だけの見出し整理。文章の意味や内容は変更しない。"""
import re


def normalize_headings(title, content):
    """保存側がタイトルを所有し、本文見出しの相対階層を保つ。"""
    lines = content.splitlines(keepends=True)
    output, warnings, stack = [], [], []
    fence = None
    for number, line in enumerate(lines, 1):
        text = line.rstrip("\r\n")
        ending = line[len(text):]
        if fence:
            output.append(line)
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", text):
                fence = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", text)
        if opening:
            marker = opening[1]
            fence = (marker[0], len(marker), number)
            output.append(line)
            continue
        if text.startswith(("    ", "\t")) or re.match(r"^ {0,3}>", text):
            output.append(line)
            continue
        heading = re.fullmatch(r" {0,3}(#{1,6})[ \t]+(.+?)", text)
        if not heading:
            if re.match(r"^ {0,3}#{1,}(?:\s|[^#])", text):
                warnings.append(f"{number}行目：空または形式不明の見出し候補は変更していません。")
            if re.fullmatch(r" {0,3}(=+|-+)\s*", text) and number > 1 and lines[number - 2].strip():
                warnings.append(f"{number}行目：下線形式の見出し／区切り線は変更していません。")
            output.append(line)
            continue
        level = len(heading[1])
        label = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2]).strip()
        if not label:
            warnings.append(f"{number}行目：内容のない見出しは変更していません。")
            output.append(line)
            continue
        if label == title:
            # 見出し行だけを除去し、前後の本文はそのまま残す。
            continue
        if level == 1:
            warnings.append(f"{number}行目：保存タイトルと異なる#見出しを本文見出しとして保持しました。")
        while stack and stack[-1] >= level:
            stack.pop()
        stack.append(level)
        target = len(stack) + 1
        if target > 3:
            warnings.append(f"{number}行目：3段を超える階層は意味を確認する必要があるため保持しました。")
            target = level
        output.append("#" * target + " " + heading[2] + ending)
    if fence:
        warnings.append(f"{fence[2]}行目：閉じられていないコードフェンスは変更していません。")
    return f"# {title}\n\n" + "".join(output).lstrip("\r\n"), tuple(warnings)
