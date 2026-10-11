from pathlib import Path
from datetime import datetime, timezone
import os
import shutil
import tempfile
from uuid import uuid4


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

    # 新しい内容を完成させてから、旧版を履歴へ退避して最新を置き換える。
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=save_dir, suffix=".tmp", delete=False) as f:
            temp_path = Path(f.name)
            f.write(f"# {file_name}\n\n")
            f.write(content)
        if file_path.exists():
            history_dir = save_dir / "history" / file_name
            history_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            history_path = history_dir / f"{stamp}_{uuid4().hex}.md"
            # 排他的に作成し、同時刻の保存でも旧版を上書きしない。
            created_history = False
            try:
                with file_path.open("rb") as source, history_path.open("xb") as target:
                    created_history = True
                    shutil.copyfileobj(source, target)
            except Exception:
                # コピー失敗時に自分が作成した不完全な履歴だけを削除する。
                if created_history and history_path.exists():
                    history_path.unlink()
                raise
            print(f"履歴を保存しました：{history_path}")
        os.replace(temp_path, file_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

    print(f"\n保存しました：{file_path}")


def load_markdown(folder_name: str, file_name: str) -> str:
    file_name = validate_theme(file_name)
    project_root = Path(__file__).resolve().parent.parent.parent

    file_path = project_root / "data" / folder_name / f"{file_name}.md"

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def list_markdown(folder_name: str) -> list[str]:
    project_root = Path(__file__).resolve().parent.parent.parent

    folder_path = project_root / "data" / folder_name

    if not folder_path.exists():
        return []

    files = []

    for file in folder_path.glob("*.md"):
        files.append(file.stem)

    return sorted(files)