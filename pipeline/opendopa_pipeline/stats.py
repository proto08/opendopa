"""`stats`: 順位・前年比・合計などを計算して列に足す(docs/data.md §8.5)。

op はレジストリ方式(`@stat_op("名前")`)。各 op は、計算に使った元の列・操作・値・表示形を
`numbers` に残す。`numbers` は行の識別子(`row_id`)→ 記録の一覧で、記録の形は次のとおり。

    {"name": "pref_seq", "op": "seq_in_group", "columns": ["pref", "OCCURRENCE_DATE"],
     "operation": "pref ごとに OCCURRENCE_DATE の順で数えた通し番号",
     "inputs": {"pref": "東京都", "OCCURRENCE_DATE": "2022/12/6 11:20"},
     "value": 3, "display": "3件"}

欠損の値は記録しない。`fmt:` を指定した stat は、`<name>_text` 列に表示形の文字列も作る。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from opendopa_pipeline.fmt import FORMATTERS, format_value, parse_datetime
from opendopa_pipeline.ingest import is_missing
from opendopa_pipeline.spec import DatasetDef, Stat

Numbers = dict[Any, list[dict[str, Any]]]

MAX_SERIES_POINTS = 12


class StatError(ValueError):
    """stats の定義の誤り(未知の op、引数の不足、列がない、など)。"""


@dataclass
class StatOutput:
    """op の戻り値。`values` が `name` の列になる。"""

    values: pd.Series
    columns: list[str]  # 計算に使った元の列
    operation: str  # 何をしたかの説明(日本語)
    inputs: dict[str, pd.Series] = field(default_factory=dict)  # 行ごとの入力値(記録用)
    extras: dict[str, pd.Series] = field(default_factory=dict)  # 追加の列(`<name>_n` など)
    default_fmt: str | None = None  # `fmt:` がないときの表示形


StatOp = Callable[[pd.DataFrame, Stat], StatOutput]
_OPS: dict[str, StatOp] = {}


def stat_op(name: str) -> Callable[[StatOp], StatOp]:
    def deco(fn: StatOp) -> StatOp:
        _OPS[name] = fn
        return fn

    return deco


def known_stat_ops() -> list[str]:
    return sorted(_OPS)


# ---- 引数の読み取り ----


def _param(s: Stat, key: str, default: Any = ...) -> Any:
    extra = s.model_extra or {}
    if key in extra:
        return extra[key]
    if default is ...:
        raise StatError(f"op {s.op!r} には {key!r} が必要です")
    return default


def _col(df: pd.DataFrame, s: Stat, key: str, default: Any = ...) -> str | None:
    name = _param(s, key, default)
    if name is not None and name not in df.columns:
        raise StatError(f"{key}: 列 {name!r} がありません")
    return name


def _cols(df: pd.DataFrame, s: Stat, key: str, required: bool = True) -> list[str]:
    raw = _param(s, key, ... if required else None)
    names = [] if raw is None else ([raw] if isinstance(raw, str) else list(raw))
    for n in names:
        if n not in df.columns:
            raise StatError(f"{key}: 列 {n!r} がありません")
    return names


def _order_keys(col: pd.Series) -> list[Any]:
    """並べ替え用のキー。数値はそのまま、日付の文字列は日時で比べる(欠損は `None`)。"""
    values = [None if is_missing(v) else v for v in col]
    present = [v for v in values if v is not None]
    if all(isinstance(v, int | float | np.number) for v in present):
        return [None if v is None else float(v) for v in values]
    parsed = [None if v is None else parse_datetime(v) for v in values]
    if all(p is not None for p, v in zip(parsed, values, strict=True) if v is not None):
        return [None if p is None else p.timestamp() for p in parsed]
    return [None if v is None else str(v) for v in values]


def _group_positions(df: pd.DataFrame, group: list[str]) -> list[list[int]]:
    """グループごとの行の位置(元の並び順)。グループ列が欠損の行は含めない。"""
    if not group:
        return [list(range(len(df)))]
    keys = df[group].astype(object)
    out: dict[tuple, list[int]] = {}
    for pos, row in enumerate(keys.itertuples(index=False)):
        if any(is_missing(v) for v in row):
            continue
        out.setdefault(tuple(row), []).append(pos)
    return list(out.values())


def _empty(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.nan, index=df.index, dtype=float)


# ---- op ----


@stat_op("rank_in_group")
def _rank_in_group(df: pd.DataFrame, s: Stat) -> StatOutput:
    value = _col(df, s, "value")
    group = _cols(df, s, "group", required=False)
    order = _param(s, "order", "desc")
    if order not in ("desc", "asc"):
        raise StatError("rank_in_group の order は desc か asc です")
    asc = order == "asc"
    rank, n = _empty(df), _empty(df)
    for pos in _group_positions(df, group):
        v = df[value].iloc[pos]
        rank.iloc[pos] = v.rank(method="min", ascending=asc).to_numpy()  # 同順位は同じ順位
        n.iloc[pos] = v.count()
    where = f"{'・'.join(group)} ごとに" if group else "全体で"
    return StatOutput(
        rank,
        [value, *group],
        f"{where} {value} の{'小さい' if asc else '大きい'}順の順位(同順位は同じ順位)",
        {value: df[value], "n": n},
        {f"{s.name}_n": n},
        "rank",
    )


def _prev_year(df: pd.DataFrame, s: Stat) -> tuple[str, list[str], str, pd.Series]:
    value = _col(df, s, "value")
    group_by = _cols(df, s, "group_by")
    year = _col(df, s, "year")
    lookup: dict[tuple, Any] = {}
    for key, v in zip(
        zip(*(df[c] for c in [*group_by, year]), strict=True), df[value], strict=True
    ):
        if not any(is_missing(k) for k in key) and not is_missing(v):
            lookup.setdefault(tuple(key), v)
    prev = []
    for key in zip(*(df[c] for c in [*group_by, year]), strict=True):
        if any(is_missing(k) for k in key):
            prev.append(np.nan)
        else:
            prev.append(lookup.get((*key[:-1], key[-1] - 1), np.nan))
    return value, group_by, year, pd.Series(prev, index=df.index, dtype=float)


@stat_op("yoy_diff")
def _yoy_diff(df: pd.DataFrame, s: Stat) -> StatOutput:
    value, group_by, year, prev = _prev_year(df, s)
    return StatOutput(
        df[value] - prev,
        [value, *group_by, year],
        f"{'・'.join(group_by)} が同じ前年({year} - 1)の行との {value} の差"
        "(前年の行がなければ欠損)",
        {value: df[value], "prev": prev},
    )


@stat_op("yoy_ratio")
def _yoy_ratio(df: pd.DataFrame, s: Stat) -> StatOutput:
    value, group_by, year, prev = _prev_year(df, s)
    ratio = (df[value] - prev) / prev.abs() * 100
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    return StatOutput(
        ratio,
        [value, *group_by, year],
        f"{'・'.join(group_by)} が同じ前年({year} - 1)の行からの {value} の変化率(%。"
        "(今年 - 前年) / |前年|)。前年の行がない・前年が 0 なら欠損",
        {value: df[value], "prev": prev},
        default_fmt="percent",
    )


def _group_transform(df: pd.DataFrame, group: list[str], value: str, how: str) -> pd.Series:
    out = _empty(df)
    for pos in _group_positions(df, group):
        v = df[value].iloc[pos]
        out.iloc[pos] = (
            {"sum": v.sum, "mean": v.mean, "count": v.count}[how]()
            if v.count()
            else (0 if how == "count" else np.nan)
        )
    return out


@stat_op("share_of_total")
def _share_of_total(df: pd.DataFrame, s: Stat) -> StatOutput:
    value = _col(df, s, "value")
    group = _cols(df, s, "group", required=False)
    total = _group_transform(df, group, value, "sum")
    share = (df[value] / total * 100).where(total > 0)
    where = f"{'・'.join(group)} ごとの" if group else "全体の"
    return StatOutput(
        share,
        [value, *group],
        f"{where} {value} の合計に占める割合(%)。合計が 0 以下なら欠損",
        {value: df[value], "total": total},
        default_fmt="percent",
    )


def _by(how: str, label: str) -> StatOp:
    def op(df: pd.DataFrame, s: Stat) -> StatOutput:
        group = _cols(df, s, "group")
        value = _col(df, s, "value", None if how == "count" else ...)
        if value is None:  # count_by: 行数を数える
            result = _empty(df)
            for pos in _group_positions(df, group):
                result.iloc[pos] = len(pos)
            cols, inputs = list(group), {}
        else:
            result = _group_transform(df, group, value, how)
            cols, inputs = [value, *group], {value: df[value]}
        what = f"{value} の{label}" if value else "行数"
        return StatOutput(
            result,
            cols,
            f"{'・'.join(group)} ごとの{what}",
            inputs,
            default_fmt="count" if how == "count" else None,
        )

    return op


stat_op("sum_by")(_by("sum", "合計"))
stat_op("mean_by")(_by("mean", "平均"))
stat_op("count_by")(_by("count", "件数"))


@stat_op("series")
def _series(df: pd.DataFrame, s: Stat) -> StatOutput:
    value = _col(df, s, "value")
    group_by = _cols(df, s, "group_by")
    order = _col(df, s, "order")
    n = _param(s, "max_points", MAX_SERIES_POINTS)
    if not isinstance(n, int) or not 1 <= n <= MAX_SERIES_POINTS:
        raise StatError(f"series の max_points は 1〜{MAX_SERIES_POINTS} の整数です")
    keys = _order_keys(df[order])
    out = pd.Series([None] * len(df), index=df.index, dtype=object)
    for pos in _group_positions(df, group_by):
        for p in pos:
            if keys[p] is None:
                continue
            upto = sorted(
                (q for q in pos if keys[q] is not None and keys[q] <= keys[p]),
                key=lambda q: (keys[q], q),
            )
            pts = [float(df[value].iloc[q]) for q in upto if not is_missing(df[value].iloc[q])]
            out.iloc[p] = [int(x) if x.is_integer() else x for x in pts[-n:]]
    return StatOutput(
        out,
        [value, *group_by, order],
        f"{'・'.join(group_by)} ごとに、{order} が今の行以前の {value} を時系列に並べた最大{n}点",
        {value: df[value]},
    )


@stat_op("seq_in_group")
def _seq_in_group(df: pd.DataFrame, s: Stat) -> StatOutput:
    group = _cols(df, s, "group")
    order = _col(df, s, "order")
    keys = _order_keys(df[order])
    seq = _empty(df)
    for pos in _group_positions(df, group):
        # 同じ順序のキーは元の行の順。キーが欠損の行は最後
        ranked = sorted(
            pos, key=lambda p: (keys[p] is None, keys[p] if keys[p] is not None else 0, p)
        )
        for i, p in enumerate(ranked, start=1):
            seq.iloc[p] = i
    return StatOutput(
        seq,
        [*group, order],
        f"{'・'.join(group)} ごとに {order} の順で数えた通し番号(1 始まり。同じ値は元の行の順)",
        {c: df[c] for c in [*group, order]},
        default_fmt="count",
    )


@stat_op("is_first_time")
def _is_first_time(df: pd.DataFrame, s: Stat) -> StatOutput:
    value = _col(df, s, "value")
    group_by = _cols(df, s, "group_by")
    order = _col(df, s, "order")
    cond = _param(s, "condition", "positive")
    if cond not in ("positive", "negative"):
        raise StatError("is_first_time の condition は positive(黒字)か negative(赤字)です")
    keys = _order_keys(df[order])

    def hit(v: Any) -> bool:
        return not is_missing(v) and (v > 0 if cond == "positive" else v < 0)

    out = pd.Series([None] * len(df), index=df.index, dtype=object)
    for pos in _group_positions(df, group_by):
        ranked = sorted((p for p in pos if keys[p] is not None), key=lambda p: (keys[p], p))
        seen_hit = False
        for i, p in enumerate(ranked):
            v = df[value].iloc[p]
            if is_missing(v):
                continue
            # 最初の行は「それ以前」が分からないので、初めてとは言わない
            out.iloc[p] = bool(i > 0 and hit(v) and not seen_hit)
            seen_hit = seen_hit or hit(v)
    word = "正" if cond == "positive" else "負"
    return StatOutput(
        out,
        [value, *group_by, order],
        f"{'・'.join(group_by)} ごとに、{order} の順で {value} が初めて{word}になった行か"
        "(グループの最初の行は偽)",
        {value: df[value]},
    )


@stat_op("per")
def _per(df: pd.DataFrame, s: Stat) -> StatOutput:
    num = _col(df, s, "num")
    den = _col(df, s, "den")
    scale = _param(s, "scale", 1)
    ratio = (df[num] / df[den].where(df[den] != 0)) * scale
    return StatOutput(
        ratio.replace([np.inf, -np.inf], np.nan),
        [num, den],
        f"{num} ÷ {den}" + (f" × {scale}" if scale != 1 else "") + "(分母が 0 なら欠損)",
        {num: df[num], den: df[den]},
    )


# ---- 実行 ----


def _py(v: Any) -> Any:
    """JSON にできる Python の値にする(欠損は `None`)。"""
    if isinstance(v, list):
        return v
    if is_missing(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _plain(v: Any) -> str:
    if isinstance(v, bool):
        return "はい" if v else "いいえ"
    return f"{v:g}" if isinstance(v, float) else str(v)


def apply_stats(df: pd.DataFrame, dataset: DatasetDef) -> tuple[pd.DataFrame, Numbers]:
    """`stats` を上から順に計算して列に足す。後の stat は、前の stat の列を使える。

    元の DataFrame は変えない。`numbers` は、行の識別子(index)→ 記録の一覧。
    """
    out = df.copy()
    numbers: Numbers = {}
    for s in dataset.stats:
        op = _OPS.get(s.op)
        if op is None:
            raise StatError(
                f"stats.{s.name}: 未知の op {s.op!r}(使えるのは {', '.join(known_stat_ops())})"
            )
        if s.name in out.columns:
            raise StatError(f"stats.{s.name}: 同じ名前の列がすでにあります")
        if s.fmt is not None and s.fmt not in FORMATTERS:
            raise StatError(
                f"stats.{s.name}: 未知の fmt {s.fmt!r}(使えるのは {', '.join(FORMATTERS)})"
            )
        try:
            res = op(out, s)
        except StatError as e:
            raise StatError(f"stats.{s.name}: {e}") from e

        fmt = s.fmt or res.default_fmt
        for i, idx in enumerate(out.index):
            v = _py(res.values.iloc[i])
            if v is None:
                continue
            display = None if isinstance(v, list) else (format_value(fmt, v) if fmt else _plain(v))
            numbers.setdefault(idx, []).append(
                {
                    "name": s.name,
                    "op": s.op,
                    "columns": res.columns,
                    "operation": res.operation,
                    "inputs": {k: _py(x.iloc[i]) for k, x in res.inputs.items()},
                    "value": v,
                    "display": display,
                }
            )
        out[s.name] = res.values
        for k, x in res.extras.items():
            out[k] = x
        if s.fmt is not None:
            out[f"{s.name}_text"] = pd.Series(
                [None if is_missing(x) else format_value(s.fmt, x) for x in res.values],
                index=out.index,
                dtype=object,
            )
    return out, numbers
