"""流れるコメントの生成(設計書 §3.5)。

動画 ID を種にした乱数で決めるので、同じ動画は毎回同じコメントになる
(Python の `hash()` は実行ごとに変わるので使わない。`util.stable_int`)。
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from functools import cache
from typing import Any

from opendopa_pipeline.expr import Expr, eval_expr, parse_expr
from opendopa_pipeline.spec import DatasetDef, parse_comment_rule
from opendopa_pipeline.util import stable_int

MIN_COMMENTS = 6
MAX_COMMENTS = 12
EDGE_SEC = 0.5  # 動画の最初と最後の近くには出さない
YELLOW_RATE = 0.15

# YAML の `comments.pool_<名前>` がないときの既定
DEFAULT_POOLS: dict[str, list[str]] = {
    "calm": ["気をつけたい", "無事でよかった", "安全第一", "落ち着いて見たい"],
    "light": ["ほう", "なるほど", "数字えぐい", "へえ", "これは気になる", "知らなかった"],
}
# 落ち着いたプール(calm)に混ぜない言い回し
FORBIDDEN_IN_CALM = ("草", "ｗ", "w", "W", "笑")


@cache
def _parse(text: str) -> Expr:
    return parse_expr(text)


def pool_name(dataset: DatasetDef, row: Mapping[str, Any]) -> str:
    """行に使うプールの名前。`rule` の最初に合った節。どれにも合わなければ `none`。"""
    rule = dataset.comments.get("rule")
    if rule is None:
        # ルールがなければ、軽い反応のプール。YAML が落ち着いたプールだけ持つなら、そちらを使う
        has = dataset.comments
        return "calm" if "pool_calm" in has and "pool_light" not in has else "light"
    for expr, pool in parse_comment_rule(rule):
        if expr is None or eval_expr(_parse(expr), row):
            return pool
    return "none"


def _pool(dataset: DatasetDef, name: str) -> list[str]:
    pool = dataset.comments.get(f"pool_{name}", DEFAULT_POOLS.get(name))
    if pool is None:
        raise ValueError(f"{dataset.id}: comments.pool_{name} がありません(rule が使っています)")
    if name == "calm":
        pool = [c for c in pool if not any(w in c for w in FORBIDDEN_IN_CALM)]
    return list(pool)


def generate_comments(
    dataset: DatasetDef, row: Mapping[str, Any], video_id: str, duration_sec: float
) -> list[dict[str, Any]]:
    """6〜12 件のコメント(`t` は 0〜`duration_sec` の秒、昇順)。`none` のときは空。"""
    name = pool_name(dataset, row)
    if name == "none":
        return []
    pool = _pool(dataset, name)
    if not pool:
        return []
    rng = random.Random(stable_int("comments", video_id))
    n = rng.randint(MIN_COMMENTS, MAX_COMMENTS)
    times = sorted(round(rng.uniform(EDGE_SEC, duration_sec - EDGE_SEC), 1) for _ in range(n))
    return [
        {
            "t": t,
            "text": rng.choice(pool),
            "style": "yellow" if name != "calm" and rng.random() < YELLOW_RATE else "normal",
        }
        for t in times
    ]
