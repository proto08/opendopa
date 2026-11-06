"""選定 → 判断 → 台本 → シーン → 品質ゲート → 出力(設計書 §8.2 の 4〜7)。

除外する行は、台本が作れない行(`no_template` / `too_long`)、型を選べない行、判断(`pii`)で
除外になった行、大きな数字が作れない行、品質ゲート(`gate.py`、docs/data.md §8.6)に通らない行。
組み立てたシーンがスキーマに合わないのは生成側のバグなので、除外ではなくエラー(`SceneError`)にする。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from opendopa_pipeline import gate
from opendopa_pipeline.comments import generate_comments
from opendopa_pipeline.decider import DecisionEngine, create_decider
from opendopa_pipeline.ingest import row_dict
from opendopa_pipeline.prepare import Prepared
from opendopa_pipeline.scene import (
    big_number,
    build_scene,
    scene_duration,
    source_ref,
    validate_scene,
)
from opendopa_pipeline.script import fill_lenient, fillable_types, write_script
from opendopa_pipeline.select import select_rows
from opendopa_pipeline.spec import DatasetDef
from opendopa_pipeline.util import jsonable


class SceneError(RuntimeError):
    """組み立てたシーンがスキーマに合わない(生成側のバグ)。"""


@dataclass
class Video:
    """1本分の結果。`videos.jsonl`(DB の `videos` 行)の元。"""

    video_id: str
    dataset_id: str
    row_id: Any
    scene: dict[str, Any] | None  # 除外のときは None
    csv_row: list[list[Any]]
    source_ref: str
    search_text: str
    decisions: dict[str, dict[str, Any]]
    status: str = "ok"  # 'ok' | 'excluded'
    excluded_why: str | None = None
    excluded_detail: str = ""  # 除外の説明(excluded.csv 用。DB には入れない)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.video_id,
            "dataset_id": self.dataset_id,
            "csv_row": self.csv_row,
            "source_ref": self.source_ref,
            "search_text": self.search_text,
            "decisions": self.decisions,
            "status": self.status,
            "excluded_why": self.excluded_why,
        }


def _csv_row(dataset: DatasetDef, frame: pd.DataFrame, row_id: Any) -> list[list[Any]]:
    """元の行を `[[列名, 値], ...]` にする。`derived` / `stats` の列と `hide` の列は除く。"""
    skip = dataset.defined_names() | set(dataset.hide)
    return [[str(c), jsonable(frame.at[row_id, c])] for c in frame.columns if c not in skip]


def build_dataset(
    dataset: DatasetDef, prepared: Prepared, engine: DecisionEngine | None = None
) -> list[Video]:
    """選定した行ごとに、シーンと DB 用の情報を作る。`engine` がなければ `rules` で判断する。

    `videoId` は `<dataset_id>-<4桁の連番>`。連番は選定の順(除外した行も数える)なので、
    除外の条件を変えても、残る動画の ID は変わらない。
    """
    frame = prepared.frame
    ids = select_rows(frame, dataset)
    rows = [row_dict(frame.loc[i]) for i in ids]

    def fillable(row: Any) -> list[str]:
        return fillable_types(dataset, row)

    if dataset.decisions:
        engine = engine or DecisionEngine(dataset, create_decider("rules", dataset))
        decisions = engine.run(rows, fillable)
    else:
        decisions = [{} for _ in rows]

    for row, decs in zip(rows, decisions, strict=True):
        _apply_drops(dataset, row, decs)

    videos = [
        _build_one(dataset, prepared, f"{dataset.id}-{n:04d}", rid, row, decs)
        for n, (rid, row, decs) in enumerate(zip(ids, rows, decisions, strict=True), start=1)
    ]
    _drop_duplicates(videos)
    return videos


def _apply_drops(dataset: DatasetDef, row: dict[str, Any], decs: dict[str, dict[str, Any]]) -> None:
    """判断で `dropped` になった列(広告らしい文など)を、その行だけ欠損にする。"""
    for d in dataset.decisions:
        if d.drop and decs.get(d.id, {}).get("dropped"):
            row[d.drop] = None


def _drop_duplicates(videos: list[Video]) -> None:
    """同じ原稿の動画は、最初の1本だけ残す(品質ゲートの「重複」)。"""
    keys = [
        gate.script_text_key([x["text"] for x in v.scene["lines"]]) if v.scene else None
        for v in videos
    ]
    for v, dup, first in zip(videos, gate.check_duplicates(keys), _first_index(keys), strict=True):
        if dup:
            v.scene, v.status, v.excluded_why = None, "excluded", "duplicate"
            v.excluded_detail = f"{videos[first].video_id} と同じ原稿"


def _first_index(keys: list[str | None]) -> list[int]:
    firsts: dict[str, int] = {}
    return [firsts.setdefault(k, i) if k is not None else i for i, k in enumerate(keys)]


def _choose_type(dataset: DatasetDef, row: dict[str, Any], decs: dict[str, Any]) -> str | None:
    """決定モデルが選んだ型。選べない(なし・埋められない型)ときは、埋められる最初の型。"""
    ok = fillable_types(dataset, row)
    if dataset.template_select is not None:
        choice = decs.get(dataset.template_select.decision, {}).get("choice")
        if choice in ok:
            return choice
    return ok[0] if ok else None


def _build_one(
    dataset: DatasetDef,
    prepared: Prepared,
    video_id: str,
    row_id: Any,
    row: dict[str, Any],
    decs: dict[str, dict[str, Any]],
) -> Video:
    ref = source_ref(dataset, row_id, row)
    base = Video(
        video_id,
        dataset.id,
        row_id,
        None,
        _csv_row(dataset, prepared.frame, row_id),
        ref,
        fill_lenient(dataset.embed_text, row),
        jsonable(decs),
        "excluded",
    )

    def exclude(why: str, detail: str = "") -> Video:
        base.excluded_why, base.excluded_detail = why, detail
        return base

    flagged = next((d_id for d_id, rec in decs.items() if rec.get("excluded")), None)
    if flagged is not None:
        return exclude(f"decision:{flagged}", "; ".join(gate.check_decisions(decs)))
    missing = gate.check_required(dataset.required, row)
    if missing:
        return exclude("missing", "; ".join(missing))
    type_id = _choose_type(dataset, row, decs)
    if type_id is None:
        return exclude("no_template", "埋められるテンプレートがある型がありません")
    group = next(g for g in dataset.template_groups if g.id == type_id)
    result = write_script(dataset, group, row, video_id)
    if result.script is None:
        return exclude(result.excluded or "no_template", result.detail)
    bignum = big_number(dataset, row)
    if bignum is None:
        return exclude("no_big_number", "大きな数字が作れません")

    script = result.script
    scene = build_scene(
        dataset,
        video_id=video_id,
        row=row,
        script=script,
        bignum=bignum,
        numbers=jsonable(prepared.numbers.get(row_id, [])),
        comments=generate_comments(dataset, row, video_id, scene_duration(script)),
        source_ref=ref,
    )
    errors = validate_scene(scene)
    if errors:
        raise SceneError(f"{video_id}: シーンがスキーマに合いません:\n  " + "\n  ".join(errors))
    failed = gate.check_all(
        lines=[x["text"] for x in scene["lines"]],
        duration_sec=scene["durationSec"],
        row=row,
        numbers=scene["numbers"],
        required=dataset.required,
    )
    if failed:
        # 理由コードは、最初に不合格になった検査。説明には全部を残す
        return exclude(next(iter(failed)), "; ".join(m for ms in failed.values() for m in ms))
    base.scene, base.status = scene, "ok"
    return base


def write_outputs(videos: list[Video], out_dir: Path | str) -> None:
    """`scenes.jsonl`(通った動画のシーン)と `videos.jsonl`(DB の `videos` 行用。除外も含む)。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    def dump(path: Path, items: list[dict[str, Any]]) -> None:
        path.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8"
        )

    dump(out / "scenes.jsonl", [v.scene for v in videos if v.scene is not None])
    dump(out / "videos.jsonl", [v.to_row() for v in videos])
