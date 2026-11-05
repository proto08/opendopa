"""取り込み → derived → クリーニング →(grain: group の集計)→ stats(設計書 §8.2 の 1〜3)。

選定(#33)、テンプレートの穴埋め(#33)、品質ゲート(#34)はここに含めない。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from opendopa_pipeline.clean import Excluded, apply_filters, write_excluded
from opendopa_pipeline.derive import derive
from opendopa_pipeline.ingest import IngestError, load_frame
from opendopa_pipeline.spec import DatasetDef, validate_against_columns
from opendopa_pipeline.stats import Numbers, apply_stats


@dataclass
class Prepared:
    frame: pd.DataFrame  # 行の識別子(row_id)を index に持つ。grain: group ではグループごとの 1 行
    numbers: Numbers  # row_id → 計算に使った数字の記録(stats.py)
    excluded: list[Excluded]


def aggregate_groups(df: pd.DataFrame, dataset: DatasetDef) -> pd.DataFrame:
    """`group_by` の列で集計して、1 グループ = 1 行にする(`grain: group`)。

    列は `group_by` と `aggregate` に書いた列、それと元の行数 `n_rows`。
    グループの列が欠損の行は、どのグループにも入らない。
    index(`row_id`)はグループの並び順の 1 始まりの番号。
    """
    missing = [c for c in [*dataset.group_by, *dataset.aggregate] if c not in df.columns]
    if missing:
        raise IngestError(f"group_by / aggregate: 列 {missing} がありません")
    g = df.groupby(dataset.group_by, sort=True, dropna=True, as_index=False)
    parts = {"n_rows": (dataset.group_by[0], "size")}
    for col, how in dataset.aggregate.items():
        # sum は、全部欠損のグループを 0 でなく欠損にする
        parts[col] = (col, (lambda s: s.sum(min_count=1)) if how == "sum" else how)
    out = g.agg(**parts)
    out.index = pd.RangeIndex(1, len(out) + 1, name="row_id")
    return out


def prepare(
    dataset: DatasetDef, root: Path | str = ".", out_dir: Path | str | None = None
) -> Prepared:
    """データセットの元データを読み、整えて、数字を計算する。

    `out_dir`(`out/<id>` など)を渡すと、落とした行を `excluded.csv` に書く。
    `derived` は行ごとの変換なので、`filters` より先に作る(`filters` の式が使えるように)。
    """
    df = load_frame(dataset, root)
    validate_against_columns(dataset, list(df.columns))
    df = derive(df, dataset)
    df, excluded = apply_filters(df, dataset)
    if dataset.grain == "group":
        df = aggregate_groups(df, dataset)
    df, numbers = apply_stats(df, dataset)
    if out_dir is not None:
        write_excluded(Path(out_dir) / "excluded.csv", excluded)
    return Prepared(df, numbers, excluded)
