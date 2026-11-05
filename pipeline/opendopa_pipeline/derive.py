"""`derived`: 穴に入れる値を、元の列から機械的に作る(docs/data.md §8.3)。

op はレジストリ方式。データセットを足すときに op が足りなければ、`@derive_op("名前")` で
関数を足すだけでよい。LLM は使わない。元の文は書き換えず、そのまま使う。
未知の op はエラー。元の値が欠損なら、結果も欠損(`classify` だけは `else` に入る)。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pandas as pd

from opendopa_pipeline.fmt import FORMATTERS, format_datetime, format_value
from opendopa_pipeline.ingest import is_missing
from opendopa_pipeline.spec import DatasetDef, Derived


class DeriveError(ValueError):
    """derived の定義の誤り(未知の op、引数の不足など)。"""


# op の関数: (元の列の Series, derived の定義) → 結果の Series(同じ index)
DeriveOp = Callable[[pd.Series, Derived], pd.Series]
_OPS: dict[str, DeriveOp] = {}


def derive_op(name: str) -> Callable[[DeriveOp], DeriveOp]:
    def deco(fn: DeriveOp) -> DeriveOp:
        _OPS[name] = fn
        return fn

    return deco


def known_derive_ops() -> list[str]:
    return sorted(_OPS)


def _arg(d: Derived, key: str, default: Any = ...) -> Any:
    extra = d.model_extra or {}
    if key in extra:
        return extra[key]
    if default is ...:
        raise DeriveError(f"op {d.op!r} には {key!r} が必要です")
    return default


def _map_non_null(col: pd.Series, f: Callable[[Any], Any]) -> pd.Series:
    return pd.Series([None if is_missing(v) else f(v) for v in col], index=col.index, dtype=object)


@derive_op("format_datetime")
def _format_datetime(col: pd.Series, d: Derived) -> pd.Series:
    fmt = _arg(d, "fmt", "ymdhm")
    format_datetime("2000/1/1", fmt)  # fmt の誤りを、行を処理する前に見つける
    return _map_non_null(col, lambda v: format_datetime(v, fmt))


_PAREN = re.compile(r"[（(][^（）()]*[）)]")


def strip_parenthesis(text: str) -> str:
    """括弧(全角・半角。入れ子も)とその中身を取り除く。"""
    prev = None
    while prev != text:
        prev, text = text, _PAREN.sub("", text)
    return text.strip()


@derive_op("strip_parenthesis")
def _strip_parenthesis(col: pd.Series, d: Derived) -> pd.Series:
    return _map_non_null(col, lambda v: strip_parenthesis(str(v)) or None)


PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 "
    "神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 "
    "大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 "
    "福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()
_PREF = re.compile("^(" + "|".join(PREFECTURES) + ")")


def extract_pref(text: str) -> str | None:
    """先頭の都道府県名。先頭にないとき(海外の長い文など)は `None`。"""
    m = _PREF.match(text.strip())
    return m.group(1) if m else None


@derive_op("extract_pref")
def _extract_pref(col: pd.Series, d: Derived) -> pd.Series:
    return _map_non_null(col, lambda v: extract_pref(str(v)))


@derive_op("classify")
def _classify(col: pd.Series, d: Derived) -> pd.Series:
    rules = _arg(d, "rules")
    contains = [(r["contains"], r["value"]) for r in rules if "contains" in r]
    others = [r["else"] for r in rules if "else" in r]
    if len(others) != 1:
        raise DeriveError("classify の rules には、else を1つだけ書いてください")
    else_value = others[0]

    def classify(v: Any) -> Any:
        text = "" if is_missing(v) else str(v)
        return next((value for word, value in contains if word in text), else_value)

    return pd.Series([classify(v) for v in col], index=col.index, dtype=object)


_SENTENCE = re.compile(r"[^。！？]*[。！？]+[」』）)]*|[^。！？]+$")


def sentences(text: str) -> list[str]:
    """文に分ける(`。` `！` `？` の後ろで切る)。元の文字は変えない(前後の空白だけ除く)。"""
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


@derive_op("sentence")
def _sentence(col: pd.Series, d: Derived) -> pd.Series:
    n = _arg(d, "n")
    if not isinstance(n, int) or n < 1:
        raise DeriveError("sentence の n は 1 以上の整数です")

    def nth(v: Any) -> str | None:
        parts = sentences(str(v))
        return parts[n - 1] if len(parts) >= n else None

    return _map_non_null(col, nth)


@derive_op("map")
def _map(col: pd.Series, d: Derived) -> pd.Series:
    mapping = {str(k): v for k, v in _arg(d, "map").items()}
    else_value = _arg(d, "else", None)
    return _map_non_null(col, lambda v: mapping.get(str(v), else_value))


@derive_op("format")
def _format(col: pd.Series, d: Derived) -> pd.Series:
    """数値を日本語の表記(fmt.py の FORMATTERS)にする。`fmt: yen | sen_yen | percent | ...`"""
    fmt = _arg(d, "fmt")
    if fmt not in FORMATTERS:
        raise DeriveError(f"format の fmt {fmt!r} は未知です(使えるのは {', '.join(FORMATTERS)})")
    return _map_non_null(col, lambda v: format_value(fmt, v))


def derive(df: pd.DataFrame, dataset: DatasetDef) -> pd.DataFrame:
    """`derived` の列を足した新しい DataFrame を返す(元の DataFrame は変えない)。"""
    out = df.copy()
    for name, d in dataset.derived.items():
        op = _OPS.get(d.op)
        if op is None:
            raise DeriveError(
                f"derived.{name}: 未知の op {d.op!r}(使えるのは {', '.join(known_derive_ops())})"
            )
        if name in df.columns:
            raise DeriveError(f"derived.{name}: 同じ名前の列が元データにあります")
        if d.from_ is None:
            raise DeriveError(f"derived.{name}: from が必要です")
        if d.from_ not in df.columns:
            raise DeriveError(f"derived.{name}: 列 {d.from_!r} がありません")
        try:
            out[name] = op(df[d.from_], d)
        except DeriveError as e:
            raise DeriveError(f"derived.{name}: {e}") from e
    return out
