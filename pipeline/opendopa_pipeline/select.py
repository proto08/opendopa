"""選定: 動画にする行を絞る(docs/data.md §8.4)。

`filters` → `score` の降順(なければ `seed` でランダム)→ `diversify_by` のラウンドロビン → `cap` 本。
同じ設定・同じデータなら、結果は毎回同じ。
"""

from __future__ import annotations

import random
import re
from collections.abc import Hashable
from typing import Any

import pandas as pd

from opendopa_pipeline.expr import eval_expr, parse_expr
from opendopa_pipeline.ingest import is_missing, row_dict
from opendopa_pipeline.spec import DatasetDef, FileFilter

DEFAULT_CAP = 150
DEFAULT_SEED = 0

# score の式: 列名 / abs(列名) / rank_desc(列名) / rank_asc(列名)
_SCORE_EXPR = re.compile(r"^\s*(?:(abs|rank_desc|rank_asc)\(\s*(\w+)\s*\)|(\w+))\s*$")


class SelectError(ValueError):
    """`select` の定義の誤り。"""


def _numbers(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        raise SelectError(f"select.score: 列 {col!r} がありません")
    return pd.to_numeric(df[col], errors="coerce")


def _score_term(df: pd.DataFrame, expr: str) -> pd.Series:
    m = _SCORE_EXPR.match(expr)
    if m is None:
        raise SelectError(
            f"select.score: 式 {expr!r} は 列 / abs(列) / rank_desc(列) / rank_asc(列) です"
        )
    func, arg, plain = m.groups()
    x = _numbers(df, arg or plain)
    if func == "abs":
        return x.abs().fillna(0.0)
    if func in ("rank_desc", "rank_asc"):
        # 大きい(rank_asc は小さい)ほど 1 に近い 0〜1。欠損は 0。重みをつけて足せるよう正規化する
        rank = x.rank(method="min", ascending=(func == "rank_asc"))
        n = x.count()
        return ((n - rank + 1) / n).fillna(0.0) if n else x.fillna(0.0)
    return x.fillna(0.0)


def scores(df: pd.DataFrame, dataset: DatasetDef) -> pd.Series | None:
    """各行の点数(式の重みづけ和)。`score` の指定がなければ `None`。"""
    if not dataset.select.score:
        return None
    total = pd.Series(0.0, index=df.index)
    for i, term in enumerate(dataset.select.score):
        if "expr" not in term:
            raise SelectError(f"select.score[{i}]: expr が必要です")
        total = total + float(term.get("weight", 1.0)) * _score_term(df, str(term["expr"]))
    return total


def _passes(df: pd.DataFrame, dataset: DatasetDef) -> list[Any]:
    keep = []
    for rid, row in df.iterrows():
        ok = True
        for f in dataset.select.filters:
            if isinstance(f, FileFilter):
                if f.col not in df.columns:
                    raise SelectError(f"select.filters: 列 {f.col!r} がありません")
                ok = ok and (not f.not_null or not is_missing(row[f.col]))
            else:
                ok = ok and eval_expr(parse_expr(f), row_dict(row))
        if ok:
            keep.append(rid)
    return keep


def _base_order(df: pd.DataFrame, dataset: DatasetDef, ids: list[Any]) -> list[Any]:
    """点数順(同点は `order_by`、なければ元の行の順)。点数がなければ `seed` でランダム。"""
    sel = dataset.select
    sub = df.loc[ids]
    if sel.order_by is not None and sel.order_by not in df.columns:
        raise SelectError(f"select.order_by: 列 {sel.order_by!r} がありません")
    pts = scores(sub, dataset)
    if pts is None:
        if sel.seed is not None:
            ids = list(ids)
            random.Random(sel.seed).shuffle(ids)
            return ids
        if sel.order_by is None:
            return list(ids)
        pts = pd.Series(0.0, index=sub.index)
    tie = (
        pd.to_numeric(sub[sel.order_by], errors="coerce").fillna(float("inf"))
        if sel.order_by
        else pd.Series(range(len(sub)), index=sub.index, dtype=float)
    )
    pos = {rid: i for i, rid in enumerate(ids)}
    return sorted(ids, key=lambda r: (-pts[r], tie[r], pos[r]))


def _round_robin(df: pd.DataFrame, ordered: list[Any], cols: list[str], cap: int) -> list[Any]:
    for c in cols:
        if c not in df.columns:
            raise SelectError(f"select.diversify_by: 列 {c!r} がありません")
    groups: dict[Hashable, list[Any]] = {}
    for rid in ordered:
        key = tuple(None if is_missing(df.at[rid, c]) else df.at[rid, c] for c in cols)
        groups.setdefault(key, []).append(rid)
    queues = list(groups.values())  # 最初に出てきた(点数の高い)グループから
    out: list[Any] = []
    depth = 0
    while len(out) < cap and any(depth < len(q) for q in queues):
        for q in queues:
            if depth < len(q) and len(out) < cap:
                out.append(q[depth])
        depth += 1
    return out


def select_rows(df: pd.DataFrame, dataset: DatasetDef) -> list[Any]:
    """動画にする行の識別子(`row_id`)を、動画の順に返す。"""
    sel = dataset.select
    cap = DEFAULT_CAP if sel.cap is None else sel.cap
    ordered = _base_order(df, dataset, _passes(df, dataset))
    div = sel.diversify_by
    cols = [div] if isinstance(div, str) else list(div or [])
    return _round_robin(df, ordered, cols, cap) if cols else ordered[:cap]
