"""UMAP で 2 次元にし、各軸を 0.05〜0.95 に収める(設計書 §11.2 の 3)。"""

from __future__ import annotations

import numpy as np

LO, HI = 0.05, 0.95
SEED = 42


def scale_unit(a: np.ndarray) -> np.ndarray:
    """各軸を [LO, HI] に収める。軸の幅が 0(全点が同じ)なら中央に置く。"""
    lo, hi = a.min(axis=0), a.max(axis=0)
    span = hi - lo
    unit = np.where(span > 0, (a - lo) / np.where(span > 0, span, 1.0), 0.5)
    return LO + unit * (HI - LO)


def project(embeddings: np.ndarray) -> np.ndarray:
    """`(n, 2)` の座標。同じ入力なら同じ結果(`random_state=42`)。

    UMAP は点が少ないと動かない(固有値分解の制約)ので、5 本未満は SVD の上位 2 軸で代用する。
    `n_neighbors` は 15 を上限に、点の数に合わせて下げる。
    """
    n = len(embeddings)
    if n == 0:
        return np.zeros((0, 2))
    if n < 5:
        centered = embeddings - embeddings.mean(axis=0)
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        coords = centered @ vt[:2].T
        if coords.shape[1] < 2:
            coords = np.hstack([coords, np.zeros((n, 2 - coords.shape[1]))])
        return scale_unit(coords)

    import umap

    reducer = umap.UMAP(
        n_neighbors=min(15, n - 1),
        min_dist=0.1,
        metric="cosine",
        n_components=2,
        random_state=SEED,
    )
    return scale_unit(np.asarray(reducer.fit_transform(embeddings), dtype=np.float64))
