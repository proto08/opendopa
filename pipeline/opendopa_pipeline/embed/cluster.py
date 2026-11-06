"""KMeans でクラスタに分け、名前と色を付ける(設計書 §11.2 の 4〜6)。"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.cluster import KMeans

from opendopa_pipeline.embed.providers import normalize
from opendopa_pipeline.llm import LlmProvider

SEED = 42
NAME_MAX = 12
NEAREST = 8
log = logging.getLogger(__name__)

SYSTEM = (
    "あなたはデータ動画のカテゴリ名を付ける編集者です。"
    f"渡された動画の見出しとデータ名に共通する話題を、{NAME_MAX}文字以内の日本語の名詞句で1つだけ答えてください。"
    "説明・記号・括弧・改行は付けません。"
)


@dataclass
class Meta:
    """クラスタ名と色を決めるための、動画ごとの情報(シーンJSONから取る)。"""

    headline: str = ""
    dataset_id: str = ""
    dataset_name: str = ""  # 例: 事故等報告
    color: str = "#888888"
    chips: tuple[str, ...] = ()  # 地域・種別など(例: 北海道、事故)

    @classmethod
    def from_scene(cls, scene: dict[str, Any], dataset_id: str) -> Meta:
        return cls(
            headline=str(scene.get("headline") or ""),
            dataset_id=dataset_id,
            dataset_name=str(scene.get("categoryName") or dataset_id),
            color=str(scene.get("color") or cls.color),
            chips=tuple(str(c) for c in scene.get("chips") or []),
        )


def kmeans(embeddings: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """`(ラベル, 重心(正規化))`。k は動画の数を上限にする。"""
    k = max(1, min(k, len(embeddings)))
    labels = KMeans(n_clusters=k, random_state=SEED, n_init=10).fit_predict(embeddings)
    centroids = np.stack([embeddings[labels == i].mean(axis=0) for i in range(k)])
    return labels, normalize(centroids)


def mechanical_name(members: list[Meta], taken: frozenset[str] = frozenset()) -> str:
    """「{主なデータ名}の{最頻の地域・種別}」。地域・種別がなければデータ名だけ。

    `taken`(他のクラスタの名前)と重なるときは、次に多い地域・種別を足し、
    それでも重なれば「(2)」のような番号を付ける。
    """
    name = Counter(m.dataset_name for m in members).most_common(1)[0][0]
    chips = Counter(c for m in members for c in m.chips)
    ranked = [c for c, _ in sorted(chips.items(), key=lambda kv: (-kv[1], kv[0]))]
    candidate = f"{name}の{ranked[0]}" if ranked else name
    for extra in ranked[1:]:
        if candidate not in taken:
            return candidate
        candidate += f"・{extra}"
    base, n = candidate, 2
    while candidate in taken:
        candidate = f"{base}({n})"
        n += 1
    return candidate


def clean_llm_name(text: str) -> str:
    """LLM の返答から名前だけを取り出す(先頭の1行、飾りを除き、12 文字に切る)。"""
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    first = re.sub(r"^[\s「『\"'・\-*#]+|[\s」』\"'。]+$", "", first)
    return first[:NAME_MAX]


def llm_name(llm: LlmProvider, members: list[Meta]) -> str | None:
    user = "\n".join(f"- {m.headline}({m.dataset_name})" for m in members)
    try:
        name = clean_llm_name(llm.complete(SYSTEM, user))
    except Exception as e:  # 名前付けの失敗で全体を止めない
        log.warning("クラスタ名の LLM 呼び出しに失敗(機械的な名前にする): %s", e)
        return None
    return name or None


def majority_color(members: list[Meta]) -> str:
    """所属動画で最多のデータセットの色(同数なら ID の昇順で先)。"""
    counts = Counter(m.dataset_id for m in members)
    top = min(counts, key=lambda d: (-counts[d], d))
    return next(m.color for m in members if m.dataset_id == top)


def build_clusters(
    embeddings: np.ndarray,
    coords: np.ndarray,
    metas: list[Meta],
    k: int,
    llm: LlmProvider | None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """`(各動画の cluster_id, clusters.json の中身)`。"""
    labels, centroids = kmeans(embeddings, k)
    clusters: list[dict[str, Any]] = []
    for cid, centroid in enumerate(centroids):
        idx = np.flatnonzero(labels == cid)
        members = [metas[i] for i in idx]
        near = idx[np.argsort(-(embeddings[idx] @ centroid), kind="stable")[:NEAREST]]
        taken = frozenset(c["name"] for c in clusters)
        name = (llm_name(llm, [metas[i] for i in near]) if llm else None) or mechanical_name(
            members, taken
        )
        clusters.append(
            {
                "id": cid,
                "name": name,
                "color": majority_color(members),
                "centroid": [float(x) for x in centroid],
                "cx": float(coords[idx, 0].mean()),
                "cy": float(coords[idx, 1].mean()),
            }
        )
    return labels, clusters
