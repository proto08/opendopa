"""元データの読み込み(docs/design_doc.md §8.2 の 1)。

元のファイルは書き換えない。読み込んだコピー(DataFrame)の上で処理する。
ローダはファイルの拡張子ごとに差し替えられる(`register_loader`)。CSV と GeoJSON を持つ。

行の識別子は、読み込み順の 1 始まりの番号(ヘッダ行を除く)で、DataFrame の index
(`row_id`)に持つ。`excluded.csv` と `numbers` はこの番号で行を指す。
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from opendopa_pipeline.spec import DatasetDef

Loader = Callable[[Path], pd.DataFrame]

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_LEADING_ZERO = re.compile(r"^-?0\d")


class IngestError(ValueError):
    """元データを読めない(ファイルがない、拡張子のローダがない、など)。"""


def read_csv(path: Path) -> pd.DataFrame:
    """UTF-8(BOM 付き可)の CSV を、すべて文字列のまま読む。空欄も文字列 `""` のまま残す。"""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


RINGS_COLUMN = "rings"


def _rings(geometry: Any) -> list[list[list[float]]] | None:
    """`Polygon` / `MultiPolygon` の座標を、`[[[lon, lat], ...], ...]`(輪のリスト)にする。

    `MultiPolygon` は、すべての多角形の輪を 1 つのリストにまとめる。高度などの 3 つ目の値は捨てる。
    """
    if not isinstance(geometry, dict):
        return None
    kind, coords = geometry.get("type"), geometry.get("coordinates")
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return None
    rings = [[[pt[0], pt[1]] for pt in ring] for poly in polygons or [] for ring in poly]
    return rings or None


def read_geojson(path: Path) -> pd.DataFrame:
    """GeoJSON(FeatureCollection)を、1 Feature = 1 行にする。

    `properties` を列として平坦化し(値は CSV と同じく文字列。`null` は欠損)、
    `geometry` の座標を `rings` 列(輪のリスト。`Polygon` / `MultiPolygon` 以外は欠損)に持つ。
    """
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list):
        raise IngestError(f"{path}: FeatureCollection ではありません")
    columns: dict[str, list[Any]] = {}
    for f in features:
        props = f.get("properties") or {}
        if RINGS_COLUMN in props:
            raise IngestError(f"{path}: properties に予約された列名 {RINGS_COLUMN!r} があります")
        for key in props:
            columns.setdefault(key, [])
    for f in features:
        props = f.get("properties") or {}
        for key, col in columns.items():
            v = props.get(key)
            col.append(None if v is None else str(v))
    cols: dict[str, pd.Series] = {k: pd.Series(v, dtype=object) for k, v in columns.items()}
    cols[RINGS_COLUMN] = pd.Series([_rings(f.get("geometry")) for f in features], dtype=object)
    return pd.DataFrame(cols)


_LOADERS: dict[str, Loader] = {".csv": read_csv, ".geojson": read_geojson}


def register_loader(suffix: str, loader: Loader) -> None:
    """拡張子(`.geojson` など)のローダを足す・差し替える。"""
    _LOADERS[suffix.lower()] = loader


def _to_number_if_possible(col: pd.Series) -> pd.Series:
    """欠損以外がすべて数値の形なら数値にする。`01100` のような先頭 0 の符号は文字列のまま。"""
    values = col.dropna()
    if values.empty or not values.map(lambda v: isinstance(v, str)).all():
        return col  # リスト(座標など)の列は、そのまま
    if not values.map(lambda s: bool(_NUMBER.match(s))).all():
        return col
    if values.map(lambda s: bool(_LEADING_ZERO.match(s))).any():
        return col
    nums = pd.to_numeric(col)
    if nums.notna().all() and (nums % 1 == 0).all() and not values.str.contains(r"\.").any():
        return nums.astype("int64")
    return nums.astype("float64")


def _is_zero(s: Any) -> bool:
    try:
        return float(s) == 0
    except (TypeError, ValueError):
        return False


def normalize(df: pd.DataFrame, dataset: DatasetDef) -> pd.DataFrame:
    """`rename` → `null_values` → `zero_is_null` → 数値化 の順で整える。新しい DataFrame を返す。"""
    df = df.rename(columns=dataset.rename)
    if df.columns.duplicated().any():
        dup = sorted(set(df.columns[df.columns.duplicated()]))
        raise IngestError(f"rename 後に列名が重複しています: {dup}")

    nulls = set(dataset.null_values)
    for col in dataset.zero_is_null:
        if col not in df.columns:
            raise IngestError(f"zero_is_null: 列 {col!r} がありません")
    zero_cols = set(dataset.zero_is_null)

    columns = {}
    for col in df.columns:
        # 欠損は、文字列の列でも数値の列でも扱いやすいよう、いったん None の object 列にする
        values = [
            None
            if (
                is_missing(v)
                or (isinstance(v, str) and v in nulls)
                or (col in zero_cols and _is_zero(v))
            )
            else v
            for v in df[col]
        ]
        columns[col] = _to_number_if_possible(pd.Series(values, dtype=object))
    out = pd.DataFrame(columns)
    out.index = pd.RangeIndex(1, len(out) + 1, name="row_id")
    return out


def load_path(path: Path) -> pd.DataFrame:
    """拡張子に合うローダで 1 ファイルを読む(整形はしない)。"""
    loader = _LOADERS.get(path.suffix.lower())
    if loader is None:
        raise IngestError(f"{path}: 拡張子 {path.suffix!r} のローダがありません")
    if not path.exists():
        raise IngestError(f"{path}: ファイルがありません(data/README.md を参照)")
    return loader(path)


def load_frame(dataset: DatasetDef, root: Path | str = ".") -> pd.DataFrame:
    """`files` を読み、結合して、`rename`・`null_values`・`zero_is_null` を適用する。

    `files` の相対パスは `root`(リポジトリのルート)からの相対。
    複数のファイルは、同じ列を持つものとして縦に結合する。
    """
    root = Path(root)
    frames = [load_path(root / name) for name in dataset.files]
    if not frames:
        raise IngestError("files が空です")
    return normalize(pd.concat(frames, ignore_index=True), dataset)


def is_missing(v: Any) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA


def row_dict(row: pd.Series) -> dict[str, Any]:
    """1 行を、式(`eval_expr`)や穴埋めに渡す dict にする。欠損は `None`、整数の float は int。"""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if is_missing(v):
            out[str(k)] = None
        elif isinstance(v, float) and v.is_integer():
            out[str(k)] = int(v)
        elif hasattr(v, "item"):
            out[str(k)] = v.item()
        else:
            out[str(k)] = v
    return out
