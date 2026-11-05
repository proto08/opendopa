"""クリーニング(docs/design_doc.md §8.2 の 2、§15.3)。

`filters` を満たさない行を落とし、落とした行を理由つきで記録する。
元の DataFrame は書き換えない(新しい DataFrame を返す)。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from opendopa_pipeline.expr import eval_expr, parse_expr
from opendopa_pipeline.ingest import is_missing, row_dict
from opendopa_pipeline.spec import DatasetDef, FileFilter


@dataclass(frozen=True)
class Excluded:
    row_id: Any
    reason: str


def apply_filters(df: pd.DataFrame, dataset: DatasetDef) -> tuple[pd.DataFrame, list[Excluded]]:
    """`filters` を上から順に当てる。

    列の形(`{col, not_null}`)は、`not_null: true` のとき欠損の行を落とす。
    式の形は、式が真になる行を残す(偽の行を落とす)。
    1 行につき、最初に落とした理由を 1 つだけ記録する。
    """
    excluded: list[Excluded] = []
    keep = df
    for f in dataset.filters:
        if isinstance(f, FileFilter):
            if not f.not_null:
                continue
            ok = keep[f.col].map(lambda v: not is_missing(v))
            reason = f"{f.col} が欠損"
        else:
            expr = parse_expr(f)
            ok = pd.Series(
                [eval_expr(expr, row_dict(r)) for _, r in keep.iterrows()],
                index=keep.index,
                dtype=bool,
            )
            reason = f"filters を満たさない: {f}"
        excluded += [Excluded(i, reason) for i in keep.index[~ok]]
        keep = keep[ok]
    return keep.copy(), excluded


def write_excluded(path: Path, excluded: list[Excluded]) -> None:
    """`out/<id>/excluded.csv`(列: row_id, reason)を書く。0 件でもヘッダは書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "reason"])
        for e in excluded:
            w.writerow([e.row_id, e.reason])
