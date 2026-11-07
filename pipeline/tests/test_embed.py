import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from opendopa_pipeline.cli import app
from opendopa_pipeline.embed.cluster import Meta, clean_llm_name, mechanical_name
from opendopa_pipeline.embed.project import project
from opendopa_pipeline.embed.providers import LocalEmbed, normalize
from opendopa_pipeline.embed.run import EmbedError, run_embed


class StubEmbed:
    """テキストから決まるベクトル(外部サービスを使わない)。"""

    def __init__(self, model: str = "stub/a", dim: int = 16) -> None:
        self.model, self.dim = model, dim
        self.seen: list[str] = []

    def embed(self, texts, kind="passage"):
        self.seen += texts
        out = []
        for t in texts:
            rng = np.random.default_rng(abs(hash_text(t)) % (2**32))
            group = int(t.split("-")[-1]) % 3  # 3 つの塊
            base = np.zeros(self.dim)
            base[group] = 5.0
            out.append(base + rng.normal(size=self.dim))
        return normalize(np.array(out))


def hash_text(t: str) -> int:
    return sum(ord(c) * (i + 1) for i, c in enumerate(t))


class StubLlm:
    def __init__(self, reply: str = "ドローンの事故") -> None:
        self.reply, self.calls = reply, []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(user)
        return self.reply


def write_dataset(root: Path, ds: str, n: int, color: str, name: str, excluded: int = 0) -> None:
    d = root / ds
    d.mkdir(parents=True)
    videos, scenes = [], []
    for i in range(n + excluded):
        ok = i < n
        vid = f"{ds}-{i:04d}"
        videos.append(
            {
                "id": vid,
                "dataset_id": ds,
                "search_text": f"{name}-{i}",
                "status": "ok" if ok else "excluded",
            }
        )
        if ok:
            scenes.append(
                {
                    "videoId": vid,
                    "headline": f"見出し{i}",
                    "categoryName": name,
                    "color": color,
                    "chips": ["東京都" if i % 2 else "北海道", "事故"],
                }
            )
    (d / "videos.jsonl").write_text("".join(json.dumps(v) + "\n" for v in videos))
    (d / "scenes.jsonl").write_text("".join(json.dumps(s) + "\n" for s in scenes))


@pytest.fixture
def out(tmp_path: Path) -> Path:
    write_dataset(tmp_path, "a", 30, "#FF0000", "事故等報告", excluded=3)
    write_dataset(tmp_path, "b", 12, "#0000FF", "空港")
    return tmp_path


def load(out: Path):
    return np.load(out / "embeddings.npz", allow_pickle=False)


def test_outputs_unit_vectors_and_centroid(out: Path) -> None:
    run_embed(out, StubEmbed(), None, k=4)
    z = load(out)
    assert len(z["video_id"]) == 42  # excluded は入らない
    assert np.allclose(np.linalg.norm(z["embedding"], axis=1), 1.0, atol=1e-5)
    assert str(z["model"]) == "stub/a"
    c = json.loads((out / "centroid.json").read_text())
    assert np.isclose(np.linalg.norm(c["centroid"]), 1.0)
    clusters = json.loads((out / "clusters.json").read_text())
    assert len(clusters) == 4
    for cl in clusters:
        assert np.isclose(np.linalg.norm(cl["centroid"]), 1.0)


def test_coords_in_range_and_deterministic(out: Path) -> None:
    run_embed(out, StubEmbed(), None, k=4)
    a = {k: load(out)[k] for k in ("x", "y", "cluster_id")}
    assert 0.05 - 1e-6 <= a["x"].min() and a["x"].max() <= 0.95 + 1e-6
    assert 0.05 - 1e-6 <= a["y"].min() and a["y"].max() <= 0.95 + 1e-6
    run_embed(out, StubEmbed(), None, k=4)
    b = load(out)
    for key in a:
        assert np.array_equal(a[key], b[key])


def test_cluster_center_and_color(out: Path) -> None:
    run_embed(out, StubEmbed(), None, k=3)
    z = load(out)
    clusters = json.loads((out / "clusters.json").read_text())
    for cl in clusters:
        m = z["cluster_id"] == cl["id"]
        assert np.isclose(cl["cx"], z["x"][m].mean(), atol=1e-5)
        assert np.isclose(cl["cy"], z["y"][m].mean(), atol=1e-5)
        assert cl["color"] in ("#FF0000", "#0000FF")


def test_local_adds_passage_prefix() -> None:
    class St:
        def __init__(self) -> None:
            self.got: list[str] = []

        def encode(self, texts, **_):
            self.got += texts
            return np.ones((len(texts), 4))

    st = St()
    LocalEmbed(st).embed(["本文"], "passage")
    LocalEmbed(st).embed(["検索"], "query")
    assert st.got == ["passage: 本文", "query: 検索"]


def test_different_model_is_recomputed_not_mixed(out: Path) -> None:
    run_embed(out, StubEmbed("stub/old"), None, k=3)
    res = run_embed(out, StubEmbed("stub/new"), None, k=3)
    assert res.replaced_model == "stub/old"
    z = load(out)
    assert str(z["model"]) == "stub/new"
    assert len(z["video_id"]) == 42


def test_mechanical_name_without_llm(out: Path) -> None:
    run_embed(out, StubEmbed(), None, k=3)
    for cl in json.loads((out / "clusters.json").read_text()):
        assert cl["name"].startswith(("事故等報告", "空港"))
        assert "の" in cl["name"]


def test_llm_name_used_and_trimmed(out: Path) -> None:
    llm = StubLlm("「ドローンの事故と重大インシデントの話」\n説明")
    run_embed(out, StubEmbed(), llm, k=3)
    assert len(llm.calls) == 3
    assert all(len(c.splitlines()) <= 8 for c in llm.calls)
    for cl in json.loads((out / "clusters.json").read_text()):
        assert cl["name"] == "ドローンの事故と重大インシデント"[:12]


def test_llm_failure_falls_back(out: Path) -> None:
    class Boom:
        def complete(self, system, user):
            raise RuntimeError("x")

    run_embed(out, StubEmbed(), Boom(), k=3)
    assert all("の" in c["name"] for c in json.loads((out / "clusters.json").read_text()))


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8])
def test_few_videos_do_not_crash(tmp_path: Path, n: int) -> None:
    write_dataset(tmp_path, "a", n, "#FF0000", "事故等報告")
    res = run_embed(tmp_path, StubEmbed(), None, k=12)
    assert res.videos == n
    assert len(res.clusters) == min(12, n)
    z = load(tmp_path)
    assert z["x"].min() >= 0.05 - 1e-6 and z["x"].max() <= 0.95 + 1e-6


def test_project_identical_points() -> None:
    xy = project(np.ones((3, 4)))
    assert np.allclose(xy, 0.5)


def test_no_videos_is_error(tmp_path: Path) -> None:
    with pytest.raises(EmbedError):
        run_embed(tmp_path, StubEmbed(), None)


def test_helpers() -> None:
    assert clean_llm_name("  「空港の利用者数」。\n") == "空港の利用者数"
    assert mechanical_name([Meta(dataset_name="X")]) == "X"


def test_cli_embed_error_without_videos(tmp_path: Path) -> None:
    r = CliRunner().invoke(app, ["embed", "--out-dir", str(tmp_path), "--provider", "bogus"])
    assert r.exit_code == 2


def test_mechanical_name_avoids_taken() -> None:
    a = Meta(dataset_name="X", chips=("東京都", "事故"))
    b = Meta(dataset_name="X", chips=("事故", "東京都", "事故"))
    assert mechanical_name([b]) == "Xの事故"
    assert mechanical_name([b], frozenset({"Xの事故"})) == "Xの事故・東京都"
    assert mechanical_name([a], frozenset({"Xの事故", "Xの事故・東京都"})) == "Xの事故・東京都(2)"
    assert mechanical_name([Meta(dataset_name="X")], frozenset({"X"})) == "X(2)"


def test_埋め込みの既定のプロバイダーは_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    from opendopa_pipeline.embed.providers import provider_name_from_env

    monkeypatch.delenv("EMBED_PROVIDER", raising=False)
    assert provider_name_from_env() == "azure"
    monkeypatch.setenv("EMBED_PROVIDER", "local")
    assert provider_name_from_env() == "local"
