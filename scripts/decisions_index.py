"""ADR と小さな決定の索引を Markdown で標準出力に出す(コミットしない)。

使い方: mise run decisions-index
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def field(text: str, name: str) -> str:
    m = re.search(rf"^- {name}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def adr_rows() -> list[str]:
    rows = []
    for path in sorted((DOCS / "adr").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = re.sub(r"^ADR-\d+\s*", "", first_heading(text))
        rows.append(
            f"| [{path.stem}](adr/{path.name}) | {title} | {field(text, 'Issue')} |"
        )
    return rows


def decision_rows() -> list[str]:
    rows = []
    for path in sorted((DOCS / "decisions").glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        date = field(text, "日付") or path.name[:10]
        rows.append(
            f"| {date} | [{first_heading(text)}](decisions/{path.name}) | {field(text, 'Issue')} |"
        )
    return rows


def main() -> int:
    print("# 決定の索引(生成物。コミットしない)\n")
    print("## ADR\n\n| ADR | 題 | Issue |\n| --- | --- | --- |")
    print("\n".join(adr_rows()))
    print(
        "\n## 小さな決定(`docs/decisions/`。2026-11-05 より前は `docs/DECISIONS.md`)\n"
    )
    print("| 日付 | 決定 | Issue |\n| --- | --- | --- |")
    print("\n".join(decision_rows()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
