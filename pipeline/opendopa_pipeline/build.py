"""選定 → 判断 → 台本 → シーン → 検証 → 出力(設計書 §8.2 の 4〜7)。

品質ゲート(§8.6 の検査)と `generate` コマンドとしての接続は #34。ここで除外するのは、
台本が作れない行(`no_template` / `too_long`)、型を選べない行、判断(`pii`)で除外になった行、
大きな数字が作れない行だけ。組み立てたシーンがスキーマに合わないのは生成側のバグなので、
除外ではなくエラー(`SceneError`)にする。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

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

    return [
        _build_one(dataset, prepared, f"{dataset.id}-{n:04d}", rid, row, decs)
        for n, (rid, row, decs) in enumerate(zip(ids, rows, decisions, strict=True), start=1)
    ]


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

    flagged = next((d_id for d_id, rec in decs.items() if rec.get("excluded")), None)
    if flagged is not None:
        base.excluded_why = f"decision:{flagged}"
        return base
    type_id = _choose_type(dataset, row, decs)
    if type_id is None:
        base.excluded_why = "no_template"
        return base
    group = next(g for g in dataset.template_groups if g.id == type_id)
    result = write_script(dataset, group, row, video_id)
    if result.script is None:
        base.excluded_why = result.excluded
        return base
    bignum = big_number(dataset, row)
    if bignum is None:
        base.excluded_why = "no_big_number"
        return base

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
