import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import psycopg
import pytest
import yaml

from opendopa_pipeline import publish as pub
from opendopa_pipeline.publish import PublishError, run_publish

REPO = Path(__file__).parents[2]
DIM = 1024


def make_root(tmp_path: Path, n_ok: int = 3, n_excluded: int = 1, audio: bool = False):
    """datasets/<id>.yaml と out/ を持つ最小の作業ディレクトリ。"""
    root = tmp_path / "root"
    (root / "datasets").mkdir(parents=True)
    data = yaml.safe_load((REPO / "datasets" / "_example.yaml").read_text(encoding="utf-8"))
    data["id"] = "demo"
    (root / "datasets" / "demo.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
    )
    out = root / "out"
    d = out / "demo"
    d.mkdir(parents=True)
    videos, scenes, ids = [], [], []
    for i in range(n_ok + n_excluded):
        ok = i < n_ok
        vid = f"demo-{i:04d}"
        videos.append(
            {
                "id": vid,
                "dataset_id": "demo",
                "csv_row": [["列", i]],
                "source_ref": f"行 #{i}",
                "search_text": f"文 {i}",
                "decisions": {"pii": {"choice": "no"}},
                "status": "ok" if ok else "excluded",
                "excluded_why": None if ok else "no_template",
            }
        )
        if ok:
            ids.append(vid)
            line: dict = {"text": "字幕"}
            if audio:
                line["audio"] = {"url": f"{vid}/0.mp3", "durationSec": 1.0}
                (d / "media" / vid).mkdir(parents=True)
                (d / "media" / vid / "0.mp3").write_bytes(b"mp3")
            scenes.append(
                {
                    "videoId": vid,
                    "datasetId": "demo",
                    "kind": "event",
                    "categoryName": "カテゴリ",
                    "headline": f"見出し{i}",
                    "durationSec": 20,
                    "lines": [line],
                }
            )
    (d / "videos.jsonl").write_text(
        "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in videos), encoding="utf-8"
    )
    (d / "scenes.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in scenes), encoding="utf-8"
    )
    rng = np.random.default_rng(0)
    emb = rng.normal(size=(len(ids), DIM)).astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    np.savez(
        out / "embeddings.npz",
        video_id=np.array(ids),
        embedding=emb,
        x=np.linspace(0, 1, len(ids)).astype(np.float32),
        y=np.linspace(1, 0, len(ids)).astype(np.float32),
        cluster_id=np.zeros(len(ids), dtype=np.int32),
        model=np.array("stub/a"),
    )
    cluster = {
        "id": 0,
        "name": "クラスタ",
        "color": "#112233",
        "centroid": emb.mean(axis=0).tolist(),
        "cx": 0.5,
        "cy": 0.5,
    }
    (out / "clusters.json").write_text(json.dumps([cluster]), encoding="utf-8")
    (out / "centroid.json").write_text(
        json.dumps({"model": "stub/a", "centroid": emb.mean(axis=0).tolist()}), encoding="utf-8"
    )
    return root, out


@pytest.fixture
def db_url():
    """TEST_DATABASE_URL の DB に、テストごとのスキーマを作る(なければスキップ)。"""
    import os

    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        pytest.skip("TEST_DATABASE_URL が未設定(pgvector 入りの PostgreSQL が必要)")
    schema = f"t_{uuid.uuid4().hex[:8]}"
    sep = "&" if "?" in base else "?"
    url = f"{base}{sep}options=-csearch_path%3D{schema},public"
    with psycopg.connect(base, autocommit=True) as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute(f"CREATE SCHEMA {schema}")
    sql = (REPO / "db/migrations/20261104000002_create_core_tables.sql").read_text()
    up = sql.split("-- migrate:up")[1].split("-- migrate:down")[0]
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(up)
    yield url
    with psycopg.connect(base, autocommit=True) as c:
        c.execute(f"DROP SCHEMA {schema} CASCADE")


def snapshot(url: str) -> dict:
    with psycopg.connect(url) as c:
        q = lambda s: c.execute(s).fetchall()  # noqa: E731
        return {
            "datasets": q("SELECT id, label FROM datasets ORDER BY id"),
            "videos": q(
                "SELECT id, kind, headline, scene::text, csv_row::text, decisions::text, status,"
                " excluded_why FROM videos ORDER BY id"
            ),
            "embeddings": q(
                "SELECT video_id, embedding::text, x, y, cluster_id, model FROM embeddings"
                " ORDER BY video_id"
            ),
            "clusters": q("SELECT id, name, centroid::text FROM clusters ORDER BY id"),
            "meta": q("SELECT key, value::text FROM meta ORDER BY key"),
        }


def env_for(url: str, **extra: str) -> dict[str, str]:
    return {"DATABASE_URL": url, **extra}


def test_dry_run_counts_without_connections(tmp_path) -> None:
    root, out = make_root(tmp_path)
    r = run_publish(root, out, dry_run=True, env={})
    assert (r.videos_ok, r.videos_excluded, r.embeddings, r.clusters) == (3, 1, 3, 1)
    assert r.scene_blobs == 3


def test_publish_counts_excluded_and_meta(tmp_path, db_url) -> None:
    root, out = make_root(tmp_path)
    run_publish(root, out, skip_blob=True, env=env_for(db_url))
    with psycopg.connect(db_url) as c:
        ok = c.execute("SELECT count(*) FROM videos WHERE status='ok'").fetchone()[0]
        emb = c.execute("SELECT count(*) FROM embeddings").fetchone()[0]
        assert ok == emb == 3
        row = c.execute("SELECT status, excluded_why FROM videos WHERE id='demo-0003'").fetchone()
        assert row == ("excluded", "no_template")
        assert c.execute("SELECT count(*) FROM clusters").fetchone()[0] == 1
        assert (
            c.execute("SELECT jsonb_array_length(value) FROM meta WHERE key='centroid'").fetchone()[
                0
            ]
            == DIM
        )
        assert c.execute("SELECT decisions FROM videos WHERE id='demo-0000'").fetchone()[0]


def test_publish_twice_is_identical(tmp_path, db_url) -> None:
    root, out = make_root(tmp_path)
    run_publish(root, out, skip_blob=True, env=env_for(db_url))
    first = snapshot(db_url)
    run_publish(root, out, skip_blob=True, env=env_for(db_url))
    assert snapshot(db_url) == first


def test_failure_rolls_back(tmp_path, db_url) -> None:
    root, out = make_root(tmp_path)
    run_publish(root, out, skip_blob=True, env=env_for(db_url))
    before = snapshot(db_url)
    # 2 回目は、存在しないクラスタを指す(外部キー違反。動画の更新のあとで失敗する)
    root2, out2 = make_root(tmp_path / "b", n_ok=2)
    with np.load(out2 / "embeddings.npz") as z:
        data = {k: z[k] for k in z.files}
    data["cluster_id"] = np.array([0, 99], dtype=np.int32)
    np.savez(out2 / "embeddings.npz", **data)
    with pytest.raises(psycopg.Error):
        run_publish(root2, out2, skip_blob=True, env=env_for(db_url))
    assert snapshot(db_url) == before


def test_videos_missing_from_new_output_are_unpublished(tmp_path, db_url) -> None:
    root, out = make_root(tmp_path, n_ok=3)
    run_publish(root, out, skip_blob=True, env=env_for(db_url))
    root2, out2 = make_root(tmp_path / "b", n_ok=2, n_excluded=0)
    run_publish(root2, out2, skip_blob=True, env=env_for(db_url))
    with psycopg.connect(db_url) as c:
        row = c.execute("SELECT status, excluded_why FROM videos WHERE id='demo-0002'").fetchone()
    assert row == ("excluded", pub.UNPUBLISHED)


class _Hook(BaseHTTPRequestHandler):
    calls: list[tuple[str, str | None]] = []
    code = 200

    def do_POST(self):  # noqa: N802
        type(self).calls.append((self.path, self.headers.get("X-Internal-Token")))
        self.send_response(type(self).code)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def hook():
    _Hook.calls, _Hook.code = [], 200
    srv = HTTPServer(("127.0.0.1", 0), _Hook)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", _Hook
    srv.shutdown()


def test_reload_called_with_token(tmp_path, db_url, hook) -> None:
    url, h = hook
    root, out = make_root(tmp_path)
    env = env_for(db_url, RECSYS_URL=url, INTERNAL_TOKEN="tok")
    r = run_publish(root, out, skip_blob=True, env=env)
    assert h.calls == [("/internal/reload", "tok")]
    assert r.reloaded is True


def test_reload_failure_is_a_warning(tmp_path, db_url, hook) -> None:
    url, h = hook
    h.code = 500
    root, out = make_root(tmp_path)
    r = run_publish(
        root, out, skip_blob=True, env=env_for(db_url, RECSYS_URL=url, INTERNAL_TOKEN="tok")
    )
    assert r.reloaded is False and r.warnings
    with psycopg.connect(db_url) as c:
        assert c.execute("SELECT count(*) FROM videos").fetchone()[0] == 4


def test_reload_skipped_without_settings(tmp_path, db_url) -> None:
    root, out = make_root(tmp_path)
    assert run_publish(root, out, skip_blob=True, env=env_for(db_url)).reloaded is None


def test_blob_scene_has_no_decisions_and_audio_url(tmp_path, db_url, monkeypatch) -> None:
    import azure.storage.blob as azblob

    uploaded: dict[str, dict[str, bytes]] = {}

    class Container:
        def __init__(self, name: str) -> None:
            self.files = uploaded.setdefault(name, {})

        def upload_blob(self, name, data, overwrite=False, content_settings=None):
            assert overwrite
            self.files[name] = data

    class Service:
        @staticmethod
        def from_connection_string(s):
            assert s == "conn"
            return Service()

        def get_container_client(self, name):
            return Container(name)

    monkeypatch.setattr(azblob, "BlobServiceClient", Service)
    root, out = make_root(tmp_path, audio=True)
    r = run_publish(
        root,
        out,
        env=env_for(db_url, STORAGE_CONNECTION_STRING="conn", MEDIA_BASE_URL="http://m/media/"),
    )
    assert (r.scene_blobs, r.media_blobs) == (3, 3)
    assert set(uploaded["scenes"]) == {f"demo-000{i}.json" for i in range(3)}
    assert uploaded["media"]["demo-0000/0.mp3"] == b"mp3"
    scene = json.loads(uploaded["scenes"]["demo-0000.json"])
    assert "decisions" not in scene
    assert scene["lines"][0]["audio"]["url"] == "http://m/media/demo-0000/0.mp3"
    with psycopg.connect(db_url) as c:
        db_scene = c.execute("SELECT scene FROM videos WHERE id='demo-0000'").fetchone()[0]
    assert db_scene == scene


def test_blob_requires_connection_string_or_skip(tmp_path) -> None:
    root, out = make_root(tmp_path)
    with pytest.raises(PublishError, match="skip-blob"):
        run_publish(root, out, env={"DATABASE_URL": "postgres://x"})


def test_embeddings_must_match_ok_videos(tmp_path) -> None:
    root, out = make_root(tmp_path)
    with np.load(out / "embeddings.npz") as z:
        data = {k: z[k][:2] if k != "model" else z[k] for k in z.files}
    np.savez(out / "embeddings.npz", **data)
    with pytest.raises(PublishError, match="一致しません"):
        run_publish(root, out, dry_run=True, env={})


def test_missing_embed_output(tmp_path) -> None:
    root, out = make_root(tmp_path)
    (out / "centroid.json").unlink()
    with pytest.raises(PublishError, match="embed"):
        run_publish(root, out, dry_run=True, env={})
