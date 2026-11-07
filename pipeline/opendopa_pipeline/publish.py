"""`publish`: out/ の結果を DB と Blob へ書き込む(設計書 §4、§6.6、§8.1)。

DB は 1 つのトランザクションで入れ替える(失敗したらロールバック)。Blob は DB より先に書く
(同じ内容の上書きなので、やり直しても結果は同じ)。公開のあと recsys に読み直しを頼む。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from opendopa_pipeline.spec import DatasetDef, load_dataset

log = logging.getLogger(__name__)

# 入れ替えで消えた動画の理由(`videos` は閲覧・いいねの記録から参照されるので、行は消さない)
UNPUBLISHED = "unpublished"


class PublishError(ValueError):
    pass


@dataclass
class VideoRow:
    id: str
    dataset_id: str
    kind: str
    category_name: str
    headline: str
    duration_sec: float
    scene: dict[str, Any]
    csv_row: list[list[Any]]
    source_ref: str
    search_text: str
    decisions: dict[str, Any] | None
    status: str
    excluded_why: str | None


@dataclass
class Bundle:
    """out/ から読んだ、公開するものすべて。"""

    datasets: list[DatasetDef]
    videos: list[VideoRow]
    embeddings: dict[str, Any]  # video_id, embedding, x, y, cluster_id, model
    clusters: list[dict[str, Any]]
    centroid: list[float]
    media: dict[str, Path] = field(default_factory=dict)  # Blob のパス → ローカルのファイル

    @property
    def ok_videos(self) -> list[VideoRow]:
        return [v for v in self.videos if v.status == "ok"]


@dataclass
class PublishResult:
    datasets: int
    videos_ok: int
    videos_excluded: int
    embeddings: int
    clusters: int
    scene_blobs: int
    media_blobs: int
    reloaded: bool | None  # None は呼ばなかった
    warnings: list[str] = field(default_factory=list)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _with_media_urls(scene: dict[str, Any], media_base_url: str) -> dict[str, Any]:
    """`lines[].audio.url` が相対パス(`<videoId>/<n>.mp3`)なら、MEDIA_BASE_URL を前に付ける。"""
    base = media_base_url.rstrip("/")
    for line in scene.get("lines", []):
        audio = line.get("audio")
        if audio and base and not audio["url"].startswith(("http://", "https://", "/")):
            audio["url"] = f"{base}/{audio['url']}"
    return scene


def load_bundle(root: Path, out_root: Path, media_base_url: str = "") -> Bundle:
    """`out/<id>/` と `out/{embeddings.npz,clusters.json,centroid.json}` を読んで確かめる。"""
    datasets: list[DatasetDef] = []
    videos: list[VideoRow] = []
    media: dict[str, Path] = {}
    for videos_path in sorted(out_root.glob("*/videos.jsonl")):
        ds_dir = videos_path.parent
        yaml_path = root / "datasets" / f"{ds_dir.name}.yaml"
        if not yaml_path.exists():
            raise PublishError(f"{ds_dir} に対応する {yaml_path} がありません")
        ds = load_dataset(yaml_path)
        datasets.append(ds)
        scenes = {s["videoId"]: s for s in _read_jsonl(ds_dir / "scenes.jsonl")}
        excluded_kind = ds.kind or ("event" if ds.grain == "row" else "stat")
        for v in _read_jsonl(videos_path):
            scene = scenes.get(v["id"])
            if v["status"] == "ok":
                if scene is None:
                    raise PublishError(f"{v['id']}: scenes.jsonl にシーンがありません")
                scene = _with_media_urls(scene, media_base_url)
                for n_path in sorted((ds_dir / "media" / v["id"]).glob("*.mp3")):
                    media[f"media/{v['id']}/{n_path.name}"] = n_path
            # 除外の行は scene がない。NOT NULL の列には空の値を入れる(配信しない)
            videos.append(
                VideoRow(
                    id=v["id"],
                    dataset_id=v["dataset_id"],
                    kind=scene["kind"] if scene else excluded_kind,
                    category_name=scene["categoryName"] if scene else "",
                    headline=scene["headline"] if scene else "",
                    duration_sec=float(scene["durationSec"]) if scene else 0.0,
                    scene=scene or {},
                    csv_row=v["csv_row"],
                    source_ref=v["source_ref"],
                    search_text=v["search_text"],
                    decisions=v.get("decisions"),
                    status=v["status"],
                    excluded_why=v.get("excluded_why"),
                )
            )
    if not videos:
        raise PublishError(f"{out_root}/*/videos.jsonl がありません(先に generate を実行)")

    npz_path = out_root / "embeddings.npz"
    for p in (npz_path, out_root / "clusters.json", out_root / "centroid.json"):
        if not p.exists():
            raise PublishError(f"{p} がありません(先に embed を実行)")
    with np.load(npz_path, allow_pickle=False) as z:
        emb = {
            "video_id": [str(x) for x in z["video_id"]],
            "embedding": z["embedding"],
            "x": z["x"],
            "y": z["y"],
            "cluster_id": z["cluster_id"],
            "model": str(z["model"]),
        }
    clusters = json.loads((out_root / "clusters.json").read_text(encoding="utf-8"))
    centroid = json.loads((out_root / "centroid.json").read_text(encoding="utf-8"))["centroid"]

    ok_ids = {v.id for v in videos if v.status == "ok"}
    if set(emb["video_id"]) != ok_ids or len(emb["video_id"]) != len(ok_ids):
        raise PublishError(
            f"embeddings.npz の動画({len(emb['video_id'])} 本)が status='ok' の動画"
            f"({len(ok_ids)} 本)と一致しません(generate のあとに embed をやり直してください)"
        )
    return Bundle(datasets, videos, emb, clusters, centroid, media)


def _vec(values: Any) -> str:
    """pgvector のテキスト形式。"""
    return "[" + ",".join(repr(float(x)) for x in values) + "]"


def write_db(conn: Any, b: Bundle) -> None:
    """全体を 1 つのトランザクションで入れ替える。呼び出し側が commit / rollback する。"""
    from psycopg.types.json import Jsonb

    with conn.cursor() as cur:
        for d in b.datasets:
            cur.execute(
                """INSERT INTO datasets (id, label, source_name, wm_char, color)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label,
                     source_name = EXCLUDED.source_name, wm_char = EXCLUDED.wm_char,
                     color = EXCLUDED.color""",
                (d.id, d.label, d.source_name, d.wm_char, d.color),
            )
        # 埋め込みとクラスタは毎回すべて作り直す(embed が全体をやり直すため)
        cur.execute("DELETE FROM embeddings")
        cur.execute("DELETE FROM clusters")
        for v in b.videos:
            cur.execute(
                """INSERT INTO videos (id, dataset_id, kind, category_name, headline,
                     duration_sec, scene, csv_row, source_ref, search_text, decisions,
                     status, excluded_why)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET dataset_id = EXCLUDED.dataset_id,
                     kind = EXCLUDED.kind, category_name = EXCLUDED.category_name,
                     headline = EXCLUDED.headline, duration_sec = EXCLUDED.duration_sec,
                     scene = EXCLUDED.scene, csv_row = EXCLUDED.csv_row,
                     source_ref = EXCLUDED.source_ref, search_text = EXCLUDED.search_text,
                     decisions = EXCLUDED.decisions, status = EXCLUDED.status,
                     excluded_why = EXCLUDED.excluded_why""",
                (
                    v.id, v.dataset_id, v.kind, v.category_name, v.headline, v.duration_sec,
                    Jsonb(v.scene), Jsonb(v.csv_row), v.source_ref, v.search_text,
                    Jsonb(v.decisions) if v.decisions is not None else None,
                    v.status, v.excluded_why,
                ),
            )  # fmt: skip
        # 今回の出力にない動画は、閲覧の記録から参照されるので消さず、配信から外す
        cur.execute(
            "UPDATE videos SET status = 'excluded', excluded_why = %s "
            "WHERE NOT (id = ANY(%s)) AND status <> 'excluded'",
            (UNPUBLISHED, [v.id for v in b.videos]),
        )
        for c in b.clusters:
            cur.execute(
                "INSERT INTO clusters (id, name, color, centroid, cx, cy) "
                "VALUES (%s, %s, %s, %s::vector, %s, %s)",
                (c["id"], c["name"], c["color"], _vec(c["centroid"]), c["cx"], c["cy"]),
            )
        e = b.embeddings
        for i, vid in enumerate(e["video_id"]):
            cur.execute(
                "INSERT INTO embeddings (video_id, embedding, x, y, cluster_id, model) "
                "VALUES (%s, %s::vector, %s, %s, %s, %s)",
                (
                    vid, _vec(e["embedding"][i]), float(e["x"][i]), float(e["y"][i]),
                    int(e["cluster_id"][i]), e["model"],
                ),
            )  # fmt: skip
        cur.execute(
            "INSERT INTO meta (key, value) VALUES ('centroid', %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (Jsonb(b.centroid),),
        )


def write_blobs(connection_string: str, b: Bundle) -> tuple[int, int]:
    """`scenes/<videoId>.json` と `media/<videoId>/<n>.mp3` を上書きで置く。"""
    from azure.storage.blob import BlobServiceClient, ContentSettings

    service = BlobServiceClient.from_connection_string(connection_string)
    scenes = service.get_container_client("scenes")
    media = service.get_container_client("media")
    for v in b.ok_videos:
        scenes.upload_blob(
            f"{v.id}.json",
            json.dumps(v.scene, ensure_ascii=False).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )
    for name, path in b.media.items():
        media.upload_blob(
            name.removeprefix("media/"),
            path.read_bytes(),
            overwrite=True,
            content_settings=ContentSettings(content_type="audio/mpeg"),
        )
    return len(b.ok_videos), len(b.media)


def reload_recsys(url: str, token: str) -> None:
    req = urllib.request.Request(
        url.rstrip("/") + "/internal/reload",
        method="POST",
        headers={"X-Internal-Token": token},
    )
    with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
        if res.status >= 300:
            raise OSError(f"HTTP {res.status}")


def run_publish(
    root: Path,
    out_root: Path,
    *,
    skip_blob: bool = False,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
) -> PublishResult:
    import psycopg

    env = dict(os.environ if env is None else env)
    b = load_bundle(root, out_root, env.get("MEDIA_BASE_URL", ""))
    result = PublishResult(
        datasets=len(b.datasets),
        videos_ok=len(b.ok_videos),
        videos_excluded=len(b.videos) - len(b.ok_videos),
        embeddings=len(b.embeddings["video_id"]),
        clusters=len(b.clusters),
        scene_blobs=0,
        media_blobs=0,
        reloaded=None,
    )
    if dry_run:
        result.scene_blobs = 0 if skip_blob else len(b.ok_videos)
        result.media_blobs = 0 if skip_blob else len(b.media)
        return result

    database_url = env.get("DATABASE_URL")
    if not database_url:
        raise PublishError("DATABASE_URL が設定されていません")
    conn_str = env.get("STORAGE_CONNECTION_STRING")
    if not skip_blob and not conn_str:
        raise PublishError(
            "STORAGE_CONNECTION_STRING が設定されていません(ローカルでは --skip-blob)"
        )
    if not skip_blob:
        assert conn_str
        result.scene_blobs, result.media_blobs = write_blobs(conn_str, b)
    with psycopg.connect(database_url) as conn:  # 例外なら rollback、抜ければ commit
        write_db(conn, b)

    url, token = env.get("RECSYS_URL"), env.get("INTERNAL_TOKEN")
    if url and token:
        try:
            reload_recsys(url, token)
            result.reloaded = True
        except (OSError, ValueError) as e:  # URLError は OSError
            result.reloaded = False
            msg = (
                f"recsys の reload に失敗しました(公開は完了): {e}"
                "(届かないときは `make recsys-reload` で recsys を再起動する)"
            )
            log.warning(msg)
            result.warnings.append(msg)
    return result


def format_result(r: PublishResult, dry_run: bool = False) -> str:
    head = "[dry-run] 公開する内容(書き込みはしていません)" if dry_run else "公開しました"
    lines = [
        head,
        f"  datasets: {r.datasets} / videos: ok {r.videos_ok}, excluded {r.videos_excluded}",
        f"  embeddings: {r.embeddings} / clusters: {r.clusters}",
        f"  Blob: scenes {r.scene_blobs}, media {r.media_blobs}",
    ]
    if r.reloaded is True:
        lines.append("  recsys: reload しました")
    lines += [f"警告: {w}" for w in r.warnings]
    return "\n".join(lines)
