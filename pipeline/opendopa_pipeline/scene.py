"""シーンJSONの組み立てと検証。スキーマ(`packages/shared/schema/`)を正として読む(ADR-0012 A2)。"""

import json
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from opendopa_pipeline.expr import eval_expr, parse_expr
from opendopa_pipeline.script import Script, fill, line_durations
from opendopa_pipeline.spec import BigNumber, DatasetDef, MapPlace
from opendopa_pipeline.util import jsonable

SHARED = Path(__file__).resolve().parents[2] / "packages" / "shared"
SCENE_SCHEMA = SHARED / "schema" / "scene.schema.json"


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCENE_SCHEMA.read_text(encoding="utf-8")))


def validate_scene(data: Any) -> list[str]:
    """スキーマに合わない箇所を `パス メッセージ` の一覧で返す。空なら合格。"""
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(map(str, e.absolute_path))} {e.message}" for e in errors]


HEADLINE_MAX = 40
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _number(s: str) -> int | float:
    return float(s) if "." in s else int(s)


def big_number(dataset: DatasetDef, row: Mapping[str, Any]) -> dict[str, Any] | None:
    """`primary`(`when` が真で穴が埋まるとき)、なければ `fallback`。どちらも無理なら `None`。"""
    candidates: list[BigNumber] = [dataset.big_number.primary]
    if dataset.big_number.fallback is not None:
        candidates.append(dataset.big_number.fallback)
    for i, bn in enumerate(candidates):
        if i == 0 and bn.when is not None and not eval_expr(parse_expr(bn.when), row):
            continue
        text, unit, label = fill(bn.text, row), fill(bn.unit, row), fill(bn.label, row)
        if text is None or unit is None or label is None:
            continue
        plain = text.replace(",", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", plain):  # 数だけなら、カウントアップする
            return {
                "value": _number(plain),
                "text": text,
                "unit": unit,
                "label": label,
                "countUp": True,
            }
        m = _NUMBER.search(text)
        value: int | float | str = _number(m.group().replace(",", "")) if m else text
        return {"value": value, "text": text, "unit": unit, "label": label, "countUp": False}
    return None


def headline(dataset: DatasetDef, row: Mapping[str, Any], lines: list[str]) -> str:
    """YAML の `headline`(穴が埋まるとき)、なければ先頭の字幕の最初の文。40字以内。"""
    text = fill(dataset.headline, row) if dataset.headline else None
    if text is None:
        text = lines[0].split("。")[0]
    return text if len(text) <= HEADLINE_MAX else text[: HEADLINE_MAX - 1] + "…"


def _place(p: MapPlace, row: Mapping[str, Any]) -> dict[str, Any] | None:
    name, lat, lon = fill(p.name, row), row.get(p.lat), row.get(p.lon)
    nums = all(isinstance(x, int | float) and not isinstance(x, bool) for x in (lat, lon))
    return {"name": name, "lat": lat, "lon": lon} if name and nums else None


def scene_map(dataset: DatasetDef, row: Mapping[str, Any]) -> dict[str, Any] | None:
    """YAML の `map` の指定から地図を作る。地点の穴・緯度経度が欠けるときは `None`。"""
    spec = dataset.map
    if spec is None:
        return None
    if spec.type == "route":
        assert spec.from_ is not None and spec.to is not None
        a, b = _place(spec.from_, row), _place(spec.to, row)
        return {"type": "route", "from": a, "to": b} if a and b else None
    if spec.type == "polygon":
        rings = row.get(spec.rings) if spec.rings else None
        if not isinstance(rings, list) or not rings:
            return None
        markers = [m for m in (_place(p, row) for p in spec.markers) if m]
        return {"type": "polygon", "rings": rings, "markers": markers}
    points = [_place(p, row) for p in spec.points]
    return {"type": "points", "points": points} if points and all(points) else None


def sparkline(dataset: DatasetDef, row: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    """`series` の stat の値(最大12点)を、x = 0, 1, ... の点列にする。"""
    values = row.get(dataset.sparkline) if dataset.sparkline else None
    if not isinstance(values, list) or not values:
        return None
    return [{"x": i, "y": y} for i, y in enumerate(values[-12:])]


_SINGLE_HOLE = re.compile(r"\{([^{}]+)\}")


def _chips(dataset: DatasetDef, row: Mapping[str, Any]) -> list[str]:
    """`chips` の各項目を穴埋めする。穴が 1 つだけで、その値がリストなら、1 項目ずつに分ける。"""
    out: list[str | None] = []
    for c in dataset.chips:
        m = _SINGLE_HOLE.fullmatch(c)
        value = row.get(m.group(1)) if m else None
        if isinstance(value, list):
            out += [str(x) for x in value]
        else:
            out.append(fill(c, row))
    return [c for c in dict.fromkeys(out) if c]


def build_scene(
    dataset: DatasetDef,
    *,
    video_id: str,
    row: Mapping[str, Any],
    script: Script,
    bignum: dict[str, Any],
    numbers: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    source_ref: str,
) -> dict[str, Any]:
    """シーンJSON(設計書 §9)の dict。コメントは動画の長さで決まるので、
    先に `scene_duration` で長さを求めてから作って渡す。"""
    durations, total = line_durations(script.lines)
    chips = _chips(dataset, row)
    return jsonable(
        {
            "videoId": video_id,
            "datasetId": dataset.id,
            "kind": dataset.kind or ("event" if dataset.grain == "row" else "stat"),
            "categoryName": dataset.label,
            "wmChar": dataset.wm_char,
            "color": dataset.color,
            "headline": headline(dataset, row, script.lines),
            "bigNumber": bignum,
            "lines": [
                {"text": t, "audio": None, "durationSec": d}
                for t, d in zip(script.lines, durations, strict=True)
            ],
            "durationSec": total,
            "map": scene_map(dataset, row),
            "sparkline": sparkline(dataset, row),
            "chips": chips,
            "tags": [],  # タグの付与は別 Issue(docs/hashtag_design.md §3.3)
            "comments": comments,
            "source": {"datasetName": dataset.source_name, "ref": source_ref},
            "numbers": numbers,
        }
    )


def scene_duration(script: Script) -> float:
    return line_durations(script.lines)[1]


def source_ref(dataset: DatasetDef, row_id: Any, row: Mapping[str, Any]) -> str:
    """出典の参照。行は `行 #<番号>`、グループは `YEAR=2023 / 事業者名` のような集計条件。"""
    if dataset.grain == "row":
        return f"行 #{row_id}"
    return " / ".join(f"{c}={row.get(c)}" for c in dataset.group_by)
