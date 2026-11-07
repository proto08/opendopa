"""列定義 YAML の下書きの材料と機械検査(設計書 §8.1、docs/data.md §8.9・§10.15)。

下書きは Claude Code が書く(実行時にも pipeline からも LLM API は呼ばない)。ここでは、
①下書きを書くための材料(プロファイル・サンプル 10 行・スキーマの説明・禁止事項)をプロンプトに
まとめ、②書かれた YAML を、YAML として読めるか・穴の名前が列定義にあるか・型ごとに `short` が
あるかを機械で検査する。書くのは文章の「ひな型」だけで、数字は、あとでエンジンが元データから入れる。
人が確認して `datasets/<id>.yaml` に置く。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pydantic import ValidationError

from opendopa_pipeline.ingest import row_dict
from opendopa_pipeline.spec import DatasetDef, validate_against_columns

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "draft_yaml.md"
SCHEMA_DOC = Path(__file__).resolve().parents[2] / "docs" / "data.md"
SAMPLE_ROWS = 10
SAMPLE_MAX_CHARS = 200  # サンプルの1つの値の長さの上限(自由記述でプロンプトが膨らまないように)
SEPARATOR = "====="

_HOLE = re.compile(r"\{([^{}]+)\}")
# 穴を含みうる文のあるキー(spec.DatasetDef.texts / holes と同じ範囲)
_TEXT_KEYS = ("template_groups", "headline", "chips", "embed_text", "big_number", "map")


def schema_text(doc: Path = SCHEMA_DOC) -> str:
    """docs/data.md の §8.3(列定義 YAML のスキーマ)から §8.3a の手前まで。"""
    text = doc.read_text(encoding="utf-8")
    start = text.index("### 8.3 ")
    end = text.index("### 8.3a", start)
    return text[start:end].strip()


def sample_rows(df: pd.DataFrame, n: int = SAMPLE_ROWS) -> list[dict[str, Any]]:
    rows = []
    for _, r in df.head(n).iterrows():
        d = row_dict(r)
        rows.append(
            {
                k: (
                    v[:SAMPLE_MAX_CHARS] + "…"
                    if isinstance(v, str) and len(v) > SAMPLE_MAX_CHARS
                    else v
                )
                for k, v in d.items()
            }
        )
    return rows


def build_prompt(
    profile: dict[str, Any],
    samples: list[dict[str, Any]],
    template: str | None = None,
    schema: str | None = None,
) -> tuple[str, str]:
    """(システム指示, ユーザー入力) を返す。"""
    template = template if template is not None else PROMPT_PATH.read_text(encoding="utf-8")
    template = re.sub(r"<!--.*?-->\s*", "", template, count=1, flags=re.DOTALL)
    system, sep, user = template.partition(f"\n{SEPARATOR}\n")
    if not sep:
        raise ValueError(f"{PROMPT_PATH} に区切り行({SEPARATOR})がありません")
    values = {
        "dataset_id": str(profile.get("dataset", "")),
        "profile": json.dumps(profile, ensure_ascii=False, indent=2, default=str),
        "samples": "\n".join(json.dumps(s, ensure_ascii=False, default=str) for s in samples),
        "schema": schema if schema is not None else schema_text(),
    }

    def fill(s: str) -> str:
        for k, v in values.items():
            s = s.replace("{{" + k + "}}", v)
        return s

    return fill(system).strip(), fill(user).strip()


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def check_draft(text: str, columns: list[str] | set[str]) -> list[str]:
    """書かれた下書き YAML の違反を一覧で返す(空なら問題なし)。

    - YAML として不正
    - 穴 `{名前}` が、列名にも `derived` / `stats` にもない
    - スキーマ違反(型ごとの `short: true` がない、式の誤りなど)
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"YAML として読めません: {str(e).splitlines()[0] if str(e) else e}"]
    if not isinstance(raw, dict):
        return [
            "トップレベルがマッピングではありません(YAML 以外の文が混ざっている可能性があります)"
        ]

    errors: list[str] = []
    derived = raw.get("derived") if isinstance(raw.get("derived"), dict) else {}
    stats = raw.get("stats") if isinstance(raw.get("stats"), list) else []
    known = set(columns) | set(derived)
    for s in stats:
        if isinstance(s, dict) and isinstance(s.get("name"), str):
            known |= {s["name"], f"{s['name']}_text", f"{s['name']}_n"}
    if raw.get("grain") == "group":
        known.add("n_rows")
    unknown: dict[str, None] = {}
    for key in _TEXT_KEYS:
        for s in _strings(raw.get(key)):
            for hole in _HOLE.findall(s):
                if hole not in known:
                    unknown[hole] = None
    errors += [f"未知の穴 {{{h}}}: 列にも derived / stats にもありません" for h in unknown]

    try:
        dataset = DatasetDef.model_validate(raw)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(トップレベル)"
            for msg in str(err["msg"]).removeprefix("Value error, ").splitlines():
                errors.append(f"{loc}: {msg}")
        return errors
    if not unknown:
        try:
            validate_against_columns(dataset, columns)
        except ValueError as e:
            errors += [ln.strip() for ln in str(e).splitlines()[1:] if ln.strip()]
    return errors
