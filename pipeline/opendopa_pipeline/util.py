"""複数のモジュールで使う小さな部品(安定したハッシュ、JSON 化)。"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import pandas as pd


def stable_int(*parts: object) -> int:
    """入力が同じなら、実行・環境によらず同じ整数になる(Python の `hash()` は使わない)。"""
    digest = hashlib.sha256("\0".join(map(str, parts)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def jsonable(v: Any) -> Any:
    """numpy / pandas の値や欠損(NaN)を、JSON に書ける Python の値にする。"""
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [jsonable(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, str | bytes):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return None if v is pd.NA else v
