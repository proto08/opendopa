"""台本: 型の中のテンプレートを選び、穴を埋め、長さを整える(docs/data.md §8.3.1)。

LLM は使わない。文に入る値は、行の列と `derived` / `stats` の値だけ。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from opendopa_pipeline.spec import DatasetDef, Template, TemplateGroup
from opendopa_pipeline.util import stable_int

CHARS_PER_SEC = 6.5  # TTS_PROVIDER=none のときの見積もり(設計書 §8.8)
MIN_SEC = 15.0
MAX_SEC = 30.0

_HOLE = re.compile(r"\{([^{}]+)\}")


LIST_SEP = "、"


def _text_of(v: Any) -> str | None:
    if isinstance(v, list):  # 項目のリスト(`join_flags` など)は「、」でつなぐ
        return LIST_SEP.join(str(x) for x in v) or None
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip() if isinstance(v, str) else str(v)
    return s or None


def fill(text: str, row: Mapping[str, Any]) -> str | None:
    """穴を行の値で埋める。穴が1つでも空(欠損・空文字)なら `None`。"""
    missing = False

    def sub(m: re.Match[str]) -> str:
        nonlocal missing
        v = _text_of(row.get(m.group(1)))
        if v is None:
            missing = True
            return ""
        return v

    out = _HOLE.sub(sub, text)
    return None if missing else out


def fill_lenient(text: str, row: Mapping[str, Any]) -> str:
    """穴が空なら空の文字列にして埋める(検索用の文など、欠けても作りたいとき)。"""
    out = _HOLE.sub(lambda m: _text_of(row.get(m.group(1))) or "", text)
    return re.sub(r"\s+", " ", out).strip()


def estimate_sec(lines: Iterable[str]) -> float:
    """推定秒数 = 文字数 ÷ 6.5。"""
    return sum(len(x) for x in lines) / CHARS_PER_SEC


@dataclass
class Script:
    type_id: str
    template_id: str
    lines: list[str]
    short: bool  # 短い版を使ったか
    dropped_optional: int  # 長さのために省いた任意の行の数
    omitted_empty: int  # 穴が空で省いた任意の行の数


@dataclass
class ScriptResult:
    script: Script | None = None
    # 台本が作れなかった理由: `no_template`(埋められるテンプレートがない)/ `too_long`
    excluded: str | None = None
    detail: str = ""
    tried: list[str] = field(default_factory=list)


def _fillable_lines(t: Template, row: Mapping[str, Any]) -> list[tuple[str, bool]] | None:
    """(埋めた文, 任意か)の一覧。必須の行の穴が空なら `None`。任意の行の穴が空ならその行は省く。"""
    out: list[tuple[str, bool]] = []
    for line in t.lines:
        text = fill(line.text, row)
        if text is None:
            if not line.optional:
                return None
            continue
        out.append((text, line.optional))
    return out


def fillable_types(dataset: DatasetDef, row: Mapping[str, Any]) -> list[str]:
    """その行で、少なくとも1つのテンプレートが埋められる型の id(判断モデルの選択肢)。"""
    return [
        g.id
        for g in dataset.template_groups
        if any(_fillable_lines(t, row) is not None for t in g.templates)
    ]


def _required_holes(t: Template) -> frozenset[str]:
    return frozenset(h for line in t.lines if not line.optional for h in _HOLE.findall(line.text))


def _fit(lines: list[tuple[str, bool]]) -> tuple[list[str], int] | None:
    """30秒を超えるあいだ、任意の行を後ろから省く。収まれば (文の一覧, 省いた数)。"""
    cur = list(lines)
    dropped = 0
    while estimate_sec(x for x, _ in cur) > MAX_SEC:
        last_opt = next((i for i in range(len(cur) - 1, -1, -1) if cur[i][1]), None)
        if last_opt is None:
            return None
        del cur[last_opt]
        dropped += 1
    return [x for x, _ in cur], dropped


def write_script(
    dataset: DatasetDef, group: TemplateGroup, row: Mapping[str, Any], key: str
) -> ScriptResult:
    """型の中から、埋められて長さに収まるテンプレートを選んで台本にする。

    標準のテンプレートを定義の順に試し(任意の行を後ろから省いて30秒に収める)、
    どれも収まらなければ `short: true` のテンプレートを試す。言い回し違い
    (必須の行の穴が同じテンプレート)が複数収まるときは、`key` のハッシュで選ぶ。
    """
    result = ScriptResult()
    for use_short in (False, True):
        fits: list[tuple[Template, list[str], int]] = []
        for t in (t for t in group.templates if t.short == use_short):
            filled = _fillable_lines(t, row)
            if filled is None:
                continue
            result.tried.append(t.id)
            fitted = _fit(filled)
            if fitted is not None:
                fits.append((t, *fitted))
        if fits:
            first = fits[0][0]
            variants = [f for f in fits if _required_holes(f[0]) == _required_holes(first)]
            t, lines, dropped = variants[stable_int(key, group.id) % len(variants)]
            empty = sum(1 for ln in t.lines if ln.optional and fill(ln.text, row) is None)
            result.script = Script(group.id, t.id, lines, use_short, dropped, empty)
            return result
    if result.tried:
        result.excluded = "too_long"
        result.detail = f"型 {group.id}: 30秒に収まりません({', '.join(result.tried)})"
    else:
        result.excluded = "no_template"
        result.detail = f"型 {group.id}: 埋められるテンプレートがありません"
    return result


def line_durations(lines: list[str]) -> tuple[list[float], float]:
    """字幕ごとの秒数と動画の長さ。15秒に満たなければ、最後の字幕の秒数を延ばして15秒にする。"""
    total = round(max(estimate_sec(lines), MIN_SEC), 2)
    durations = [round(len(x) / CHARS_PER_SEC, 2) for x in lines[:-1]]
    durations.append(round(total - sum(durations), 2))
    return durations, total
