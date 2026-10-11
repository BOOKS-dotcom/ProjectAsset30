from pathlib import Path


def validate_theme(theme: str) -> str:
    """テーマを安全な単一ファイル名として検証する。"""
    theme = theme.strip()
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
    }
    if (not theme or theme in {".", ".."} or theme.endswith(".")
            or any(c in '<>:"/\\|?*' or ord(c) < 32 for c in theme)
            or theme.split(".")[0].upper() in reserved
            or len(theme.encode("utf-8")) > 240):
        raise ValueError("保存可能な調査テーマを指定してください。")
    return theme


def save_markdown(folder_name: str, file_name: str, content: str):
    file_name = validate_theme(file_name)
    project_root = Path(__file__).resolve().parent.parent.parent

    save_dir = project_root / "data" / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)

    file_path = save_dir / f"{file_name}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# {file_name}\n\n")
        f.write(content)

    print(f"\n保存しました：{file_path}")


def load_markdown(folder_name: str, file_name: str) -> str:
    file_name = validate_theme(file_name)
    project_root = Path(__file__).resolve().parent.parent.parent

    file_path = project_root / "data" / folder_name / f"{file_name}.md"

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

from pathlib import Path


def list_markdown(folder_name: str) -> list[str]:
    project_root = Path(__file__).resolve().parent.parent.parent

    folder_path = project_root / "data" / folder_name

    if not folder_path.exists():
        return []

    files = []

    for file in folder_path.glob("*.md"):
        files.append(file.stem)

    return sorted(files)