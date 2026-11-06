"""GeoJSON ローダと、flightplan のデータセット(#56)。実データは使わず、合成した GeoJSON で試す。"""

import json
from pathlib import Path

import pandas as pd
import pytest

from opendopa_pipeline.derive import derive
from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.ingest import IngestError, load_frame, load_path, read_geojson
from opendopa_pipeline.scene import validate_scene
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]
YAML = REPO / "datasets" / "flightplan.yaml"

SQUARE = [[[135.0, 35.0], [135.1, 35.0], [135.1, 35.1], [135.0, 35.1], [135.0, 35.0]]]

_D = load_dataset(YAML).derived
FLAGS = [
    *_D["purpose"].model_extra["labels"],
    *_D["features"].model_extra["labels"],
    "FLIGHT_AIRSPACE_NONE",
    "FLIGHT_METHOD_NEAR_DANGER_ZONE",
    "FLIGHT_METHOD_NONE",
]


def feature(no, *on, start="2026-06-29 05:30:00", end="2026-06-29 08:00:00", geometry=None):
    props = {"No": no, "FLIGHT_PLAN_ID_NEW": f"FlightPlanID_{9000 + no}"}
    props.update({f: (1 if f in on else 0) for f in FLAGS})
    props.update(
        FLIGHT_DATETIME_START=start,
        FLIGHT_DATETIME_END=end,
        DEPARTURE_LOCATION=f"滋賀県野洲市{'ABC'[no % 3]}",
        DEPARTURE_LATITUDE=35.06747,
        DEPARTURE_LONGITUDE=136.02588,
        DESTINATION_LOCATION="滋賀県守山市",
        DESTINATION_LATITUDE=35.05866,
        DESTINATION_LONGITUDE=135.99402,
        FLIGHT_ALTITUDE=7777,
        FLIGHT_SPEED=8888,
        MANUFACTURING_NUMBER=123456,
        REGISTRATION_DATE_Y="2026/06/26 09:03:53",
        UPDATE_DATE_Y="2026/06/26 09:03:53",
        AIRCRAFT_TYPE="回転翼航空機(マルチローター)",
    )
    geometry = geometry or {"type": "Polygon", "coordinates": SQUARE}
    return {"type": "Feature", "properties": props, "geometry": geometry}


def write_geojson(root: Path, features: list[dict]) -> Path:
    path = root / "data" / "raw" / "flightplan" / "01_hikoukeikaku.geojson"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "name": "t", "features": features}),
        encoding="utf-8",
    )
    return path


AG = "FLIGHT_PURPOSE_BUSINESS_AGRICULTURE"


@pytest.fixture
def root(tmp_path):
    write_geojson(
        tmp_path,
        [
            feature(
                1, AG, "FLIGHT_METHOD_NIGHT", "FLIGHT_AIRSPACE_DID", "FLIGHT_METHOD_WITHIN_30M"
            ),
            feature(2, AG),  # 特徴のフラグが 1 つもない
            feature(3, AG, "FLIGHT_METHOD_NEAR_DANGER_ZONE"),  # 対応表にない特徴だけ
            feature(
                4,
                AG,
                "FLIGHT_METHOD_BVLOS",
                start="2026-06-29 05:00:00",
                end="2026-06-29 07:30:00",
                geometry={
                    "type": "MultiPolygon",
                    "coordinates": [
                        SQUARE,
                        [[[136.0, 36.0], [136.1, 36.0], [136.1, 36.1], [136.0, 36.0]]],
                    ],
                },
            ),
            feature(
                5,
                AG,
                "FLIGHT_AIRSPACE_OVER_150M",
                start="2026-06-30 05:00:00",
                end="2026-06-30 07:00:00",
            ),
        ],
    )
    return tmp_path


def test_geojson_loader_flattens_properties_and_rings(root):
    df = load_path(root / "data/raw/flightplan/01_hikoukeikaku.geojson")
    assert len(df) == 5
    assert df.loc[0, "FLIGHT_PLAN_ID_NEW"] == "FlightPlanID_9001"
    assert df.loc[0, "FLIGHT_AIRSPACE_DID"] == "1"  # CSV と同じく文字列。数値化は normalize
    assert df.loc[0, "rings"] == SQUARE


def test_multipolygon_rings_are_merged_and_altitude_dropped(tmp_path):
    z = [[[1.0, 2.0, 30.0], [1.5, 2.0, 30.0], [1.0, 2.5, 30.0], [1.0, 2.0, 30.0]]]
    path = write_geojson(
        tmp_path,
        [
            feature(1, geometry={"type": "MultiPolygon", "coordinates": [z, z]}),
            feature(2, geometry={"type": "Point", "coordinates": [1, 2]}),
        ],
    )
    df = read_geojson(path)
    assert len(df.loc[0, "rings"]) == 2
    assert df.loc[0, "rings"][0][0] == [1.0, 2.0]
    assert df.loc[1, "rings"] is None  # Polygon 以外は欠損


def test_geojson_loader_rejects_non_feature_collection(tmp_path):
    p = tmp_path / "x.geojson"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(IngestError):
        read_geojson(p)


def test_derive_flags_and_hours(root):
    ds = load_dataset(YAML)
    out = derive(load_frame(ds, root), ds)
    assert out.loc[1, "features"] == ["夜間", "30m以内", "人口集中地区"]
    assert out.loc[2, "features"] is None  # フラグなし
    assert out.loc[3, "features"] is None  # 対応表にないフラグだけ
    assert out.loc[1, "flight_hours"] == 2.5  # 5:30 → 8:00
    assert out.loc[4, "flight_hours"] == 2.5  # 5:00 → 7:30


def test_hours_between_is_missing_when_end_before_start():
    from opendopa_pipeline.derive import _FRAME_OPS
    from opendopa_pipeline.spec import Derived

    df = pd.DataFrame({"a": ["2026-01-01 10:00:00"], "b": ["2026-01-01 09:00:00"]})
    d = Derived.model_validate({"from": "a", "op": "hours_between", "to": "b"})
    assert _FRAME_OPS["hours_between"](df, d)[0] is None


def test_generate_excludes_rows_without_features_and_builds_polygon_maps(root, tmp_path_factory):
    ds = load_dataset(YAML)
    out = tmp_path_factory.mktemp("out")
    result = run_generate(ds, root, out, provider="rules")

    assert result.report["summary"]["generated"] == 3  # 1, 4, 5
    assert result.report["summary"]["excluded"] == 2  # 2, 3(特徴なし)
    assert result.report["summary"]["excluded_by_reason"] == {"filter": 2}
    excluded = (out / "excluded.csv").read_text(encoding="utf-8")
    assert "features != null" in excluded

    scenes = {
        s["videoId"]: s for s in map(json.loads, (out / "scenes.jsonl").read_text().splitlines())
    }
    assert len(scenes) == 3
    for s in scenes.values():
        assert validate_scene(s) == []
        assert s["kind"] == "geo"
        assert s["map"]["type"] == "polygon"
        assert [m["name"] for m in s["map"]["markers"]] == ["出発", "到着"]

    first = next(s for s in scenes.values() if "夜間" in s["chips"])
    assert first["chips"] == [
        "農業",
        "夜間",
        "30m以内",
        "人口集中地区",
    ]  # 目的 + 対応表どおりの特徴
    assert first["map"]["rings"] == SQUARE
    assert first["bigNumber"]["text"] == "2.5" and first["bigNumber"]["unit"] == "時間"

    multi = next(s for s in scenes.values() if "目視外" in s["chips"])
    assert len(multi["map"]["rings"]) == 2  # MultiPolygon の輪が全部入る


def test_unused_attributes_do_not_leak(root, tmp_path_factory):
    ds = load_dataset(YAML)
    out = tmp_path_factory.mktemp("out")
    run_generate(ds, root, out, provider="rules")

    scene_text = (out / "scenes.jsonl").read_text(encoding="utf-8")
    for secret in ("FlightPlanID_", "123456", "7777", "8888"):  # ID・製造番号・高度・速度
        assert secret not in scene_text
    for line in (out / "videos.jsonl").read_text(encoding="utf-8").splitlines():
        csv_row = json.loads(line)["csv_row"]
        cols = {name for name, _ in csv_row}
        assert not cols & {
            "FLIGHT_PLAN_ID_NEW",
            "MANUFACTURING_NUMBER",
            "REGISTRATION_DATE_Y",
            "UPDATE_DATE_Y",
            "FLIGHT_ALTITUDE",
            "FLIGHT_SPEED",
            "rings",
        }
