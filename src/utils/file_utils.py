from pathlib import Path


def save_markdown(folder_name: str, file_name: str, content: str):
    project_root = Path(__file__).resolve().parent.parent.parent

    save_dir = project_root / "data" / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)

    file_path = save_dir / f"{file_name}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# {file_name}\n\n")
        f.write(content)

    print(f"\n保存しました：{file_path}")


def load_markdown(folder_name: str, file_name: str) -> str:
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