"""列のプロファイル(docs/design_doc.md §8.1、docs/data.md §10.15)。

列ごとに型・欠損率・種類数・最長の文字数・役割の推定・上位の値を出す。
新しいデータセットの列定義 YAML を作るときの調査に使う。役割はルールで推定する(LLM は使わない)。
"""

from __future__ import annotations

import re
import unicodedata
from types import SimpleNamespace
from typing import Any

import pandas as pd

from opendopa_pipeline.ingest import normalize

TOP_N = 5
FREE_TEXT_MIN_LEN = 31  # 最長がこれ以上(30 字超)なら free_text
ID_UNIQUE_RATIO = 0.98  # 欠損以外の値のうち、一意な値の割合がこれ以上なら id
CATEGORY_MAX_UNIQUE = 20  # 種類数がこれ以下(かつ行数の半分以下)なら category

_DATE = re.compile(r"^\d{4}[-/.年]\d{1,2}([-/.月]\d{1,2}日?)?([ T]\d{1,2}:\d{2}(:\d{2})?)?$")
_LAT_NAME = re.compile(r"(^|[^a-z])(lat|latitude)([^a-z]|$)|緯度", re.IGNORECASE)
_LON_NAME = re.compile(r"(^|[^a-z])(lon|lng|long|longitude)([^a-z]|$)|経度", re.IGNORECASE)


def prepare_raw(df: pd.DataFrame) -> pd.DataFrame:
    """YAML のない読み込み用。空欄を欠損にし、数の形の列を数値にする(rename などはしない)。"""
    spec = SimpleNamespace(rename={}, null_values=[""], zero_is_null=[])
    return normalize(df, spec)  # type: ignore[arg-type]


def _native(v: Any) -> Any:
    return v.item() if hasattr(v, "item") else v


def _dtype(col: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(col):
        return "int"
    if pd.api.types.is_float_dtype(col):
        return "float"
    return "string"


def _is_date(values: pd.Series) -> bool:
    if values.empty or _dtype(values) != "string":
        return False
    return bool(values.map(lambda v: bool(_DATE.match(str(v).strip()))).mean() >= 0.9)


def _is_coordinate(name: str, values: pd.Series) -> bool:
    if values.empty or not pd.api.types.is_numeric_dtype(values):
        return False
    if _LAT_NAME.search(name):
        return bool(values.between(-90, 90).all())
    if _LON_NAME.search(name):
        return bool(values.between(-180, 180).all())
    return False


def infer_role(name: str, dtype: str, values: pd.Series, n_rows: int, max_len: int) -> str:
    """役割を推定する。上から順に当てはまったものを返す。

    coordinate → flag → date → free_text → id → number → category → other
    """
    if values.empty:
        return "other"
    n_unique = values.nunique()
    if _is_coordinate(name, values):
        return "coordinate"
    if dtype != "string" and set(values.unique()) <= {0, 1}:
        return "flag"
    if _is_date(values):
        return "date"
    if dtype == "string" and max_len >= FREE_TEXT_MIN_LEN:
        return "free_text"
    # 小数の列は、すべて異なっても計測値なので id にしない
    if dtype != "float" and n_unique / len(values) >= ID_UNIQUE_RATIO and len(values) > 1:
        return "id"
    if dtype != "string":
        return "number"
    if n_unique <= CATEGORY_MAX_UNIQUE and n_unique <= n_rows / 2:
        return "category"
    return "other"


def profile_column(name: str, col: pd.Series) -> dict[str, Any]:
    n_rows = len(col)
    values = col.dropna()
    if not values.empty and values.map(lambda v: isinstance(v, list)).all():
        # 座標などのリストの列(GeoJSON の rings)。値の分布は出さない
        return {
            "name": name,
            "dtype": "list",
            "missing_rate": round(1 - len(values) / n_rows, 4),
            "n_unique": 0,
            "max_len": 0,
            "role": "geometry",
            "top": [],
        }
    dtype = _dtype(col)
    max_len = int(values.map(lambda v: len(str(v))).max()) if not values.empty else 0
    counts = values.value_counts()
    # 件数の多い順。同数は値の文字列順(出力を決定的にするため)
    top = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))[:TOP_N]
    return {
        "name": name,
        "dtype": dtype,
        "missing_rate": round(1 - len(values) / n_rows, 4) if n_rows else 0.0,
        "n_unique": int(values.nunique()),
        "max_len": max_len,
        "role": infer_role(name, dtype, values, n_rows, max_len),
        "top": [{"value": _native(v), "count": int(c)} for v, c in top],
    }


def profile_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [profile_column(str(name), df[name]) for name in df.columns]


def build_profile(dataset_id: str, df: pd.DataFrame, source: list[str]) -> dict[str, Any]:
    return {
        "dataset": dataset_id,
        "source": source,
        "n_rows": len(df),
        "columns": profile_frame(df),
    }


def _width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _width(s))


def _clip(s: str, limit: int) -> str:
    out, w = "", 0
    for c in s:
        cw = _width(c)
        if w + cw > limit - 1:
            return out + "…"
        out, w = out + c, w + cw
    return out


def format_table(profile: dict[str, Any]) -> str:
    """標準出力用の表。上位の値は `値(件数)` を並べ、長い値は切る。"""
    header = ["列", "型", "欠損率", "種類数", "最長", "役割", "上位の値(件数)"]
    rows = [header]
    for c in profile["columns"]:
        top = " / ".join(
            f"{_clip(str(t['value']).replace(chr(10), ' '), 24)}({t['count']})" for t in c["top"]
        )
        rows.append(
            [
                c["name"],
                c["dtype"],
                f"{c['missing_rate'] * 100:.1f}%",
                str(c["n_unique"]),
                str(c["max_len"]),
                c["role"],
                top,
            ]
        )
    widths = [max(_width(r[i]) for r in rows) for i in range(len(header))]
    lines = ["  ".join(_pad(cell, widths[i]) for i, cell in enumerate(r)).rstrip() for r in rows]
    title = f"{profile['dataset']}: {profile['n_rows']} 行 {len(profile['columns'])} 列"
    return "\n".join([title, *lines])
