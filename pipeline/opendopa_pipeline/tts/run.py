"""`tts`: `out/<id>/scenes.jsonl` の各行に音声を付ける(設計書 §8.8)。

1 行ずつ `out/<id>/media/<videoId>/<n>.mp3` に合成し、`lines[i].audio`(`{url, durationSec}`)と
`lines[i].durationSec`(音声の長さ)を入れる。`url` は `<videoId>/<n>.mp3` の相対パスで、
`publish` が MEDIA_BASE_URL を前に付ける。
音声を入れたあとの長さで、品質ゲートの長さの検査をやり直す。
"""

from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opendopa_pipeline import gate
from opendopa_pipeline.scene import validate_scene
from opendopa_pipeline.script import MIN_SEC
from opendopa_pipeline.tts.providers import Synthesizer, TtsError, mp3_duration
from opendopa_pipeline.tts.speak import apply_dict

# 行の durationSec に足す余白(秒)。再生開始の遅れ(読み込み・デコード・出力遅延)で、
# 切り替えのときに音声の末尾が切られないようにする。audio.durationSec は実際の長さのまま
LINE_PAD_SEC = 0.3


@dataclass
class TtsResult:
    voiced: int = 0
    files: int = 0
    excluded: dict[str, str] = field(default_factory=dict)  # videoId → 理由の説明
    skipped: bool = False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8"
    )


def voice_scene(
    scene: dict[str, Any], synth: Synthesizer, words: dict[str, str], media_dir: Path
) -> tuple[dict[str, Any], int]:
    """1 本のシーンに音声を付けた新しい dict と、作ったファイル数。`media_dir` は `<videoId>` の中。

    行の秒数は音声の長さ + `LINE_PAD_SEC`。
    15 秒に満たないときは、最後の字幕の秒数を延ばして 15 秒にする(音声の長さはそのまま)。
    """
    media_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for n, line in enumerate(scene["lines"]):
        speak = apply_dict(line["text"], words)
        data = synth.synthesize(speak)
        (media_dir / f"{n}.mp3").write_bytes(data)
        sec = mp3_duration(data)
        if sec <= 0:
            raise TtsError(f"{scene['videoId']} の {n} 行目の音声の長さが 0 です")
        new = {
            **line,
            "audio": {"url": f"{scene['videoId']}/{n}.mp3", "durationSec": sec},
            "durationSec": round(sec + LINE_PAD_SEC, 2),
        }
        if speak != line["text"]:
            new["speak"] = speak
        else:
            new.pop("speak", None)
        lines.append(new)
    total = sum(x["durationSec"] for x in lines)
    if total < MIN_SEC:  # 契約: durationSec は lines の合計。最後の字幕を延ばす
        lines[-1]["durationSec"] = round(lines[-1]["durationSec"] + MIN_SEC - total, 2)
        total = MIN_SEC
    total = round(total, 2)
    # 音声のほうが短くなったとき、動画の終わりより後ろに残るコメントは落とす
    comments = [c for c in scene["comments"] if c["t"] < total]
    return {**scene, "lines": lines, "durationSec": total, "comments": comments}, len(lines)


def run_tts(dataset_dir: Path | str, synth: Synthesizer | None, words: dict[str, str]) -> TtsResult:
    """`synth` が `None`(TTS_PROVIDER=none)なら何もしない(音声ファイルも作らない)。"""
    out = Path(dataset_dir)
    result = TtsResult()
    if synth is None:
        result.skipped = True
        return result
    scenes = _read_jsonl(out / "scenes.jsonl")
    new_scenes: list[dict[str, Any]] = []
    shutil.rmtree(out / "media", ignore_errors=True)  # 前回の音声を残さない
    for scene in scenes:
        vid = scene["videoId"]
        voiced, n = voice_scene(scene, synth, words, out / "media" / vid)
        problems = gate.check_length(voiced["durationSec"])  # スキーマ(30 秒まで)より先に調べる
        if problems:
            shutil.rmtree(out / "media" / vid, ignore_errors=True)
            result.excluded[vid] = "; ".join(problems)
            continue
        errors = validate_scene(voiced)
        if errors:
            raise TtsError(f"{vid}: 音声を入れたシーンがスキーマに合いません: {errors[0]}")
        new_scenes.append(voiced)
        result.voiced += 1
        result.files += n
    _write_jsonl(out / "scenes.jsonl", new_scenes)
    if result.excluded:
        _mark_excluded(out, result.excluded)
    return result


def _mark_excluded(out: Path, excluded: dict[str, str]) -> None:
    """長さの検査に通らなくなった動画を、`videos.jsonl` と `excluded.csv` で除外にする。"""
    videos = _read_jsonl(out / "videos.jsonl")
    rows = []
    for v in videos:
        if v["id"] in excluded:
            v["status"], v["excluded_why"] = "excluded", "length"
            rows.append(v)
    _write_jsonl(out / "videos.jsonl", videos)
    path = out / "excluded.csv"
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["row_id", "video_id", "stage", "reason", "detail"])
        for v in rows:
            w.writerow(["", v["id"], "tts", "length", excluded[v["id"]]])


def format_result(r: TtsResult, provider: str) -> str:
    if r.skipped:
        return f"TTS_PROVIDER={provider}: 音声は作りません(字幕の秒数は 1 秒 6.5 文字の見積もり)"
    lines = [f"音声を付けた動画: {r.voiced} 本({r.files} ファイル)"]
    lines += [f"  除外 {vid}: {why}" for vid, why in r.excluded.items()]
    if r.excluded:
        lines.append(
            "除外が出たので、embed を(まだなら tts のあとに)やり直してください。"
            "除外した動画の埋め込みが残ると publish が失敗します"
        )
    return "\n".join(lines)
