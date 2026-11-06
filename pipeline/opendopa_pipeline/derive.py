"""`derived`: 穴に入れる値を、元の列から機械的に作る(docs/data.md §8.3)。

op はレジストリ方式。データセットを足すときに op が足りなければ、`@derive_op("名前")` で
関数を足すだけでよい。LLM は使わない。元の文は書き換えず、そのまま使う。
未知の op はエラー。元の値が欠損なら、結果も欠損(`classify` だけは `else` に入る)。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pandas as pd

from opendopa_pipeline.fmt import FORMATTERS, format_datetime, format_value, parse_datetime
from opendopa_pipeline.ingest import is_missing
from opendopa_pipeline.spec import DatasetDef, Derived


class DeriveError(ValueError):
    """derived の定義の誤り(未知の op、引数の不足など)。"""


# op の関数: (元の列の Series, derived の定義) → 結果の Series(同じ index)
DeriveOp = Callable[[pd.Series, Derived], pd.Series]
_OPS: dict[str, DeriveOp] = {}
# 他の列も見る op の関数: (DataFrame 全体, derived の定義) → 結果の Series(同じ index)
FrameOp = Callable[[pd.DataFrame, Derived], pd.Series]
_FRAME_OPS: dict[str, FrameOp] = {}


def derive_op(name: str) -> Callable[[DeriveOp], DeriveOp]:
    def deco(fn: DeriveOp) -> DeriveOp:
        _OPS[name] = fn
        return fn

    return deco


def derive_frame_op(name: str) -> Callable[[FrameOp], FrameOp]:
    """行ごとの変換ではなく、表全体を見て作る op(`fill_by_key` など)を足す。"""

    def deco(fn: FrameOp) -> FrameOp:
        _FRAME_OPS[name] = fn
        return fn

    return deco


def known_derive_ops() -> list[str]:
    return sorted({*_OPS, *_FRAME_OPS})


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
    """数値を日本語の表記(fmt.py の FORMATTERS)にする。`fmt: yen | sen_yen | percent | ...`

    省略できる引数: `abs: true`(符号を除いた大きさにする。黒字・赤字の額など)、
    `min_abs` / `max_abs`(大きさがこの範囲の外なら欠損にする。桁が極端な値を読まないため)。
    """
    fmt = _arg(d, "fmt")
    if fmt not in FORMATTERS:
        raise DeriveError(f"format の fmt {fmt!r} は未知です(使えるのは {', '.join(FORMATTERS)})")
    use_abs = _arg(d, "abs", False)
    lo = _arg(d, "min_abs", None)
    hi = _arg(d, "max_abs", None)

    def f(v: Any) -> str | None:
        x = _to_number(v)
        if x is None:
            return format_value(fmt, v)
        if (lo is not None and abs(x) < lo) or (hi is not None and abs(x) > hi):
            return None
        return format_value(fmt, abs(x) if use_abs else x)

    return _map_non_null(col, f)


def _to_number(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return float(v)


@derive_op("sign_label")
def _sign_label(col: pd.Series, d: Derived) -> pd.Series:
    """数値の符号を言葉にする(黒字・赤字など)。`positive` / `negative` / `zero` に書いた言葉を使い、
    書いていない符号(省略した `zero` など)と数値でない値は欠損にする。"""
    labels = {k: _arg(d, k, None) for k in ("positive", "negative", "zero")}
    if labels["positive"] is None and labels["negative"] is None:
        raise DeriveError("sign_label には positive か negative が必要です")

    def label(v: Any) -> str | None:
        x = _to_number(v)
        if x is None:
            return None
        return labels["positive" if x > 0 else "negative" if x < 0 else "zero"]

    return _map_non_null(col, label)


def _frame_col(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        raise DeriveError(f"列 {name!r} がありません")
    return df[name]


@derive_frame_op("join_flags")
def _join_flags(df: pd.DataFrame, d: Derived) -> pd.Series:
    """フラグの列(1 なら該当)を、`labels`(列名 → ラベル)の順に拾って、ラベルのリストにする。

    該当が 1 つもなければ欠損。リストは、穴に入れるときは「、」でつなぎ、`chips` では
    1 つずつ分ける。
    """
    labels = _arg(d, "labels")
    flags = {col: _frame_col(df, col) for col in labels}

    def row(i: Any) -> list[str] | None:
        hit = [
            label
            for col, label in labels.items()
            if not is_missing(flags[col][i]) and flags[col][i] == 1
        ]
        return hit or None

    return pd.Series([row(i) for i in df.index], index=df.index, dtype=object)


@derive_frame_op("hours_between")
def _hours_between_frame(df: pd.DataFrame, d: Derived) -> pd.Series:
    start = _frame_col(df, str(d.from_))
    end = _frame_col(df, _arg(d, "to"))

    def hours(a: Any, b: Any) -> float | None:
        x, y = parse_datetime(a), parse_datetime(b)
        if x is None or y is None or y < x:
            return None
        return round((y - x).total_seconds() / 3600, 1)

    return pd.Series(
        [hours(a, b) for a, b in zip(start, end, strict=True)], index=df.index, dtype=object
    )


@derive_op("scale")
def _scale(col: pd.Series, d: Derived) -> pd.Series:
    """数値に `by` を掛け、小数 `digits` 桁(省略で 1)に四捨五入する。例: 比率 0.62 → 62(`by: 100`)。

    Decimal で計算するので、0.62 × 100 が 62.00000000000001 にならない。数値でない値は欠損にする。
    """
    by = Decimal(str(_arg(d, "by")))
    places = Decimal(1).scaleb(-int(_arg(d, "digits", 1)))

    def scale(v: Any) -> float | None:
        try:
            return float((Decimal(str(v)) * by).quantize(places, rounding=ROUND_HALF_UP))
        except ArithmeticError:
            return None

    return _map_non_null(col, scale)


@derive_frame_op("fill_by_key")
def _fill_by_key(df: pd.DataFrame, d: Derived) -> pd.Series:
    """`from` の値(緯度など)が欠損の行を、同じ `key`(港名など)の他の行の値で埋める。

    `also: [{key: 別の名前の列, value: 別の値の列}]` を足すと、積み港の列と降ろし港の列のように、
    同じ名前が別の列に出る行からも探す。自分の行に値があればそのまま使う。
    名前に複数の値があるときは、先に出た行の値(行の順)を使う。名前が欠損の行は埋めない。
    """
    key = _arg(d, "key")
    pairs = [(key, d.from_)] + [(a["key"], a["value"]) for a in _arg(d, "also", [])]
    for k, v in pairs:
        for c in (k, v):
            if c not in df.columns:
                raise DeriveError(f"fill_by_key: 列 {c!r} がありません")
    known: dict[Any, Any] = {}
    for k, v in pairs:
        for name, value in zip(df[k], df[v], strict=True):
            if not is_missing(name) and not is_missing(value):
                known.setdefault(name, value)
    own = df[d.from_]
    return pd.Series(
        [
            v if not is_missing(v) else (None if is_missing(n) else known.get(n))
            for n, v in zip(df[key], own, strict=True)
        ],
        index=df.index,
        dtype=object,
    )


def derive(df: pd.DataFrame, dataset: DatasetDef) -> pd.DataFrame:
    """`derived` の列を足した新しい DataFrame を返す(元の DataFrame は変えない)。"""
    out = df.copy()
    for name, d in dataset.derived.items():
        op, frame = _OPS.get(d.op), _FRAME_OPS.get(d.op)
        if op is None and frame is None:
            raise DeriveError(
                f"derived.{name}: 未知の op {d.op!r}(使えるのは {', '.join(known_derive_ops())})"
            )
        if name in df.columns:
            raise DeriveError(f"derived.{name}: 同じ名前の列が元データにあります")
        if frame is None and d.from_ is None:
            raise DeriveError(f"derived.{name}: from が必要です")
        if d.from_ is not None and d.from_ not in df.columns:
            raise DeriveError(f"derived.{name}: 列 {d.from_!r} がありません")
        try:
            if frame is not None:
                out[name] = frame(df, d)
            else:
                assert op is not None and d.from_ is not None
                out[name] = op(df[d.from_], d)
        except DeriveError as e:
            raise DeriveError(f"derived.{name}: {e}") from e
    return out
