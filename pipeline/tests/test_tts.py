import json
import wave
from pathlib import Path
from typing import Any

import lameenc
import pytest
from typer.testing import CliRunner

from opendopa_pipeline.cli import app
from opendopa_pipeline.scene import validate_scene
from opendopa_pipeline.tts.providers import (
    Azure,
    TtsError,
    VoiceVox,
    create_synthesizer,
    mp3_duration,
    wav_to_mp3,
)
from opendopa_pipeline.tts.run import run_tts, voice_scene
from opendopa_pipeline.tts.speak import apply_dict, load_dict

FIXTURE = Path(__file__).parents[2] / "packages" / "shared" / "fixtures" / "accident-0001.json"


def silent_mp3(sec: float) -> bytes:
    """指定の長さの無音の mp3(16kHz モノ)。"""
    enc = lameenc.Encoder()
    enc.set_bit_rate(32)
    enc.set_in_sample_rate(16000)
    enc.set_channels(1)
    enc.set_quality(7)
    return bytes(enc.encode(b"\x00\x00" * int(16000 * sec)) + enc.flush())


class StubTts:
    """1 文字あたり `sec_per_char` 秒の無音を返す。渡された文を記録する。"""

    def __init__(self, sec_per_char: float = 0.1) -> None:
        self.sec_per_char = sec_per_char
        self.spoken: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.spoken.append(text)
        return silent_mp3(len(text) * self.sec_per_char)


def scene_dict(texts: list[str] | None = None) -> dict[str, Any]:
    scene = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if texts is not None:
        scene["lines"] = [{"text": t, "audio": None, "durationSec": 1.0} for t in texts]
    return scene


def make_out(tmp_path: Path, scenes: list[dict[str, Any]]) -> Path:
    ds = tmp_path / "out" / "accident"
    ds.mkdir(parents=True)
    (ds / "scenes.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in scenes), encoding="utf-8"
    )
    videos = [
        {"id": s["videoId"], "dataset_id": "accident", "status": "ok", "excluded_why": None}
        for s in scenes
    ]
    (ds / "videos.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in videos), encoding="utf-8"
    )
    return ds


def read_scenes(ds: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (ds / "scenes.jsonl").read_text(encoding="utf-8").splitlines()]


# ---- 辞書 ----


def test_dict_replaces_and_leaves_unknown_words() -> None:
    words = {"無人航空機": "むじんこうくうき", "航空機": "ひこうき"}
    assert apply_dict("無人航空機が航空機と接触", words) == "むじんこうくうきがひこうきと接触"
    assert apply_dict("ドローンが飛んだ", words) == "ドローンが飛んだ"


def test_shipped_dict_has_example() -> None:
    assert load_dict()["無人航空機"] == "むじんこうくうき"


def test_load_dict_rejects_bad_shape(tmp_path) -> None:
    p = tmp_path / "d.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_dict(p)


# ---- 音声の付与 ----


def test_voice_scene_sets_audio_and_duration(tmp_path) -> None:
    scene = scene_dict(["無人航空機の事故です。" * 3, "二行目です。" * 4])
    stub = StubTts(0.2)
    voiced, n = voice_scene(scene, stub, {"無人航空機": "むじんこうくうき"}, tmp_path / "v")
    assert n == 2
    for i, line in enumerate(voiced["lines"]):
        assert line["audio"]["url"] == f"{scene['videoId']}/{i}.mp3"
        assert (tmp_path / "v" / f"{i}.mp3").exists()
        assert line["audio"]["durationSec"] == pytest.approx(len(stub.spoken[i]) * 0.2, abs=0.15)
    # 辞書を適用した文だけ speak に入る。字幕は元の表記のまま
    assert voiced["lines"][0]["speak"].startswith("むじんこうくうき")
    assert voiced["lines"][0]["text"].startswith("無人航空機")
    assert "speak" not in voiced["lines"][1]
    assert validate_scene(voiced) == []
    total = sum(x["durationSec"] for x in voiced["lines"])
    assert voiced["durationSec"] == pytest.approx(total)


def test_short_audio_is_padded_to_min_length(tmp_path) -> None:
    scene = scene_dict(["短い。", "もう一つ。"])
    voiced, _ = voice_scene(scene, StubTts(0.1), {}, tmp_path)
    assert voiced["durationSec"] == 15.0
    assert sum(x["durationSec"] for x in voiced["lines"]) == pytest.approx(15.0)
    # 音声そのものの長さは、そのまま
    assert voiced["lines"][-1]["audio"]["durationSec"] < 2
    assert all(c["t"] < 15.0 for c in voiced["comments"])


def test_run_tts_excludes_videos_over_30_seconds(tmp_path) -> None:
    ok, long_ = scene_dict(["ふつうの文です" * 5]), scene_dict(["長い文です" * 20])
    ok["videoId"], long_["videoId"] = "accident-0001", "accident-0002"
    ds = make_out(tmp_path, [ok, long_])
    res = run_tts(ds, StubTts(0.25), {})  # long: 100字 → 約25秒で収まる
    assert res.excluded == {}
    ds = make_out(tmp_path / "b", [ok, long_])
    res = run_tts(ds, StubTts(0.4), {})  # long: 100字 → 約40秒で超える
    assert list(res.excluded) == ["accident-0002"]
    assert [s["videoId"] for s in read_scenes(ds)] == ["accident-0001"]
    videos = [json.loads(x) for x in (ds / "videos.jsonl").read_text().splitlines()]
    assert [(v["id"], v["status"], v["excluded_why"]) for v in videos] == [
        ("accident-0001", "ok", None),
        ("accident-0002", "excluded", "length"),
    ]
    assert not (ds / "media" / "accident-0002").exists()
    assert (ds / "media" / "accident-0001" / "0.mp3").exists()
    assert "accident-0002,tts,length" in (ds / "excluded.csv").read_text()


def test_none_provider_creates_no_files(tmp_path) -> None:
    ds = make_out(tmp_path, [scene_dict()])
    before = (ds / "scenes.jsonl").read_text()
    res = run_tts(ds, create_synthesizer("none"), {})
    assert res.skipped
    assert not (ds / "media").exists()
    assert (ds / "scenes.jsonl").read_text() == before


def test_audio_url_matches_publish_layout(tmp_path) -> None:
    """publish は `media/<videoId>/<n>.mp3` を上げ、相対の url に MEDIA_BASE_URL を付ける。"""
    from opendopa_pipeline.publish import _with_media_urls

    ds = make_out(tmp_path, [scene_dict(["あ" * 90])])
    run_tts(ds, StubTts(0.2), {})
    scene = read_scenes(ds)[0]
    url = scene["lines"][0]["audio"]["url"]
    assert (ds / "media" / url).is_file()
    assert _with_media_urls(scene, "http://m/media/")["lines"][0]["audio"]["url"] == (
        f"http://m/media/{url}"
    )


# ---- プロバイダー ----


def silent_wav(sec: float, rate: int = 24000) -> bytes:
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * sec))
    return buf.getvalue()


def test_wav_to_mp3_keeps_length() -> None:
    assert mp3_duration(wav_to_mp3(silent_wav(2.0))) == pytest.approx(2.0, abs=0.1)


def test_voicevox_calls_query_then_synthesis() -> None:
    calls: list[tuple[str, bytes]] = []

    def post(url: str, body: bytes, headers: Any) -> bytes:
        calls.append((url, body))
        return b'{"speedScale": 1.0}' if "audio_query" in url else silent_wav(1.0)

    mp3 = VoiceVox("http://vv:50021/", speaker=8, speed=1.2, post=post).synthesize("こんにちは")
    assert "audio_query?" in calls[0][0] and "speaker=8" in calls[0][0]
    assert "%E3%81%93" in calls[0][0]  # text は URL エンコード
    assert calls[1][0] == "http://vv:50021/synthesis?speaker=8"
    assert json.loads(calls[1][1])["speedScale"] == 1.2
    assert mp3_duration(mp3) == pytest.approx(1.0, abs=0.1)


def test_azure_posts_ssml_with_escaped_text() -> None:
    seen: dict[str, Any] = {}

    def post(url: str, body: bytes, headers: Any) -> bytes:
        seen.update(url=url, body=body.decode(), headers=headers)
        return silent_mp3(1.0)

    Azure("k", "japaneast", post=post).synthesize("A<B&C")
    assert seen["url"] == "https://japaneast.tts.speech.microsoft.com/cognitiveservices/v1"
    assert "A&lt;B&amp;C" in seen["body"]
    assert seen["headers"]["Ocp-Apim-Subscription-Key"] == "k"
    assert "mp3" in seen["headers"]["X-Microsoft-OutputFormat"]


def test_create_synthesizer_validates_env() -> None:
    assert create_synthesizer("none") is None
    assert isinstance(create_synthesizer("voicevox", {}), VoiceVox)
    with pytest.raises(TtsError):
        create_synthesizer("azure", {})
    with pytest.raises(TtsError):
        create_synthesizer("nope", {})
    with pytest.raises(TtsError):
        create_synthesizer("voicevox", {"VOICEVOX_SPEAKER": "x"})


def test_cli_tts_none_skips(tmp_path) -> None:
    ds = make_out(tmp_path, [scene_dict()])
    result = CliRunner().invoke(
        app, ["tts", "--dataset", "accident", "--out-dir", str(ds.parent), "--provider", "none"]
    )
    assert result.exit_code == 0
    assert "音声は作りません" in result.output
    assert not (ds / "media").exists()


def test_tts_output_excluded_video_is_not_embedded(tmp_path) -> None:
    # all は tts のあとに embed する。embed が読む動画は、tts の除外を反映している
    from opendopa_pipeline.embed.run import load_videos

    ok, long_ = scene_dict(["ふつうの文です" * 5]), scene_dict(["長い文です" * 20])
    ok["videoId"], long_["videoId"] = "accident-0001", "accident-0002"
    ds = make_out(tmp_path, [ok, long_])
    videos = [json.loads(x) for x in (ds / "videos.jsonl").read_text().splitlines()]
    for v in videos:
        v["search_text"] = v["id"]
    (ds / "videos.jsonl").write_text("".join(json.dumps(v) + "\n" for v in videos))
    run_tts(ds, StubTts(0.4), {})
    ids, _, _ = load_videos(ds.parent)
    assert ids == ["accident-0001"]


def test_all_runs_tts_before_embed(tmp_path, monkeypatch) -> None:
    import opendopa_pipeline.cli as cli

    calls: list[str] = []
    monkeypatch.setattr(cli, "dataset_ids", lambda: ["accident"])
    monkeypatch.setattr(cli, "provider_name_from_env", lambda: "voicevox")
    monkeypatch.setattr(cli, "generate", lambda d, *a: calls.append("generate"))
    monkeypatch.setattr(cli, "tts", lambda d, *a: calls.append("tts"))
    monkeypatch.setattr(cli, "embed", lambda *a: calls.append("embed"))
    monkeypatch.setattr(cli, "_publish", lambda *a, **k: calls.append("publish"))
    result = CliRunner().invoke(app, ["all", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert calls == ["generate", "tts", "embed", "publish"]


def test_tts_result_tells_to_redo_embed_when_excluded() -> None:
    from opendopa_pipeline.tts.run import TtsResult, format_result

    out = format_result(TtsResult(voiced=1, excluded={"accident-0002": "長すぎる"}), "voicevox")
    assert "embed を" in out and "やり直してください" in out
    assert "embed" not in format_result(TtsResult(voiced=1), "voicevox")
