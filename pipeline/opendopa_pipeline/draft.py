"""列定義 YAML の下書きを LLM に作らせる(設計書 §0.4・§8.1、docs/data.md §8.9・§10.15)。

LLM が書くのは文章の「ひな型」だけ。数字は、あとでエンジンが元データから入れる。
LLM の出力は、YAML として読めるか・穴の名前が列定義にあるか・型ごとに `short` があるかを
機械で検査し、違反は下書きの先頭にコメントで残す。人が確認して `datasets/<id>.yaml` に置く。
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
from opendopa_pipeline.llm import LlmProvider
from opendopa_pipeline.spec import DatasetDef, validate_against_columns

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "draft_yaml.md"
SCHEMA_DOC = Path(__file__).resolve().parents[2] / "docs" / "data.md"
SAMPLE_ROWS = 10
SAMPLE_MAX_CHARS = 200  # サンプルの1つの値の長さの上限(自由記述でプロンプトが膨らまないように)
SEPARATOR = "====="

_HOLE = re.compile(r"\{([^{}]+)\}")
_FENCE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n```\s*$", re.DOTALL)
# 穴を含みうる文のあるキー(spec.DatasetDef.texts / holes と同じ範囲)
_TEXT_KEYS = ("template_groups", "headline", "chips", "embed_text", "big_number", "map")

NO_LLM_MESSAGE = (
    "LLM が使えません(LLM_PROVIDER=none)。下書きは作りません。\n"
    "下書きが要るときは LLM_PROVIDER=azure と Azure OpenAI の環境変数を設定してください。\n"
    "使わない場合は、`uv run opendopa profile --dataset <id>` で列を調べ、"
    "`datasets/_example.yaml` と docs/data.md §8.3・§10.15 を見て手で書いてください。"
)


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


def strip_fence(text: str) -> str:
    """LLM がコードフェンスで囲んで返したときに、中身だけにする。"""
    text = text.strip()
    m = _FENCE.match(text)
    return m.group(1) if m else text


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def check_draft(text: str, columns: list[str] | set[str]) -> list[str]:
    """下書き YAML の違反を一覧で返す(空なら問題なし)。

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


def with_violations(text: str, violations: list[str]) -> str:
    """違反を、下書きの先頭にコメントとして付ける。"""
    if not violations:
        return text
    head = [
        f"# 機械検査で {len(violations)} 件の違反があります。直してから datasets/ に置いてください"
    ]
    head += [f"# - {v}" for v in violations]
    return "\n".join(head) + "\n\n" + text


def draft_yaml(
    llm: LlmProvider,
    profile: dict[str, Any],
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> tuple[str, list[str]]:
    """LLM に下書きを作らせ、(下書きの本文, 違反の一覧) を返す。本文には違反のコメントを付ける。"""
    system, user = build_prompt(profile, sample_rows(df))
    text = strip_fence(llm.complete(system, user))
    violations = check_draft(text, columns if columns is not None else list(df.columns))
    return with_violations(text, violations), violations
