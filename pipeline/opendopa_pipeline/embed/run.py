"""`opendopa embed` の本体。全データセットの `videos.jsonl` から、3 つのファイルを作る。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from opendopa_pipeline.embed.cluster import Meta, build_clusters
from opendopa_pipeline.embed.project import project
from opendopa_pipeline.embed.providers import EmbedProvider, normalize
from opendopa_pipeline.llm import LlmProvider

DEFAULT_K = 12
log = logging.getLogger(__name__)


class EmbedError(ValueError):
    pass


@dataclass
class EmbedResult:
    videos: int
    clusters: list[dict[str, Any]]
    model: str
    replaced_model: str | None  # 出力が既にあり、モデルが違ったときの古いモデル名


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def load_videos(out_root: Path) -> tuple[list[str], list[str], list[Meta]]:
    """`out/<id>/videos.jsonl` の `status='ok'` を、データセット名・動画 ID の順に読む。"""
    ids: list[str] = []
    texts: list[str] = []
    metas: list[Meta] = []
    for videos_path in sorted(out_root.glob("*/videos.jsonl")):
        scenes = {s["videoId"]: s for s in _read_jsonl(videos_path.parent / "scenes.jsonl")}
        for v in _read_jsonl(videos_path):
            if v.get("status") != "ok":
                continue
            ids.append(v["id"])
            texts.append(v["search_text"])
            metas.append(Meta.from_scene(scenes.get(v["id"], {}), v["dataset_id"]))
    return ids, texts, metas


def _existing_model(npz_path: Path) -> str | None:
    if not npz_path.exists():
        return None
    try:
        with np.load(npz_path, allow_pickle=False) as z:
            return str(z["model"])
    except (OSError, KeyError, ValueError):
        return None


def _dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_embed(
    out_root: Path,
    embedder: EmbedProvider,
    llm: LlmProvider | None = None,
    k: int = DEFAULT_K,
) -> EmbedResult:
    """常に全動画を埋め込み直す。古い出力のベクトルは再利用しない(モデルが混ざらない)。"""
    ids, texts, metas = load_videos(out_root)
    if not ids:
        raise EmbedError(f"{out_root}/*/videos.jsonl に status='ok' の動画がありません")
    if k < 1:
        raise EmbedError("--k は 1 以上にしてください")

    npz_path = out_root / "embeddings.npz"
    old_model = _existing_model(npz_path)
    replaced = old_model if old_model not in (None, embedder.model) else None
    if replaced:
        log.warning("既存の出力のモデル(%s)が違うため、全動画を埋め込み直します", replaced)

    emb = normalize(embedder.embed(texts, "passage"))
    if emb.shape[0] != len(ids):
        raise EmbedError(f"埋め込みの本数({emb.shape[0]})が動画の数({len(ids)})と違います")
    centroid = normalize(emb.mean(axis=0))
    coords = project(emb)
    labels, clusters = build_clusters(emb, coords, metas, k, llm)

    out_root.mkdir(parents=True, exist_ok=True)
    np.savez(
        npz_path,
        video_id=np.array(ids),
        embedding=emb.astype(np.float32),
        x=coords[:, 0].astype(np.float32),
        y=coords[:, 1].astype(np.float32),
        cluster_id=labels.astype(np.int32),
        model=np.array(embedder.model),
    )
    _dump(out_root / "clusters.json", clusters)
    _dump(out_root / "centroid.json", {"model": embedder.model, "centroid": centroid.tolist()})
    return EmbedResult(len(ids), clusters, embedder.model, replaced)
