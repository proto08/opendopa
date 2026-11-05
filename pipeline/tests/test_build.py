import json
import warnings

import pytest

from opendopa_pipeline.build import SceneError, build_dataset, write_outputs
from opendopa_pipeline.prepare import prepare
from opendopa_pipeline.scene import validate_scene
from opendopa_pipeline.spec import DatasetDef

CSV = """No.,SUMMARY,LOCATION,OCCURRENCE_DATE,REMARKS,PHONE,LAT,LON
1,負傷者が出た。次の文。,東京都千代田区,2022/12/10 9:00,備考あり,090-0000-0000,35.7,139.7
2,制御不能になり墜落した。,東京都港区(羽田),2022/12/6 11:20,,090-1111-1111,35.6,139.8
3,,大阪府大阪市,2022/1/1 0:00,x,,,
4,車両に衝突した。,海外で発生,2022/2/1 0:00,x,,,
5,原因不明の事象。,東京都新宿区,2022/3/1 0:00,y,,34.0,135.0
"""


@pytest.fixture
def built(tmp_path, make_dataset):
    csv = tmp_path / "data" / "raw" / "example" / "example.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text(CSV, encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        d = make_dataset(
            files=["data/raw/example/example.csv"],
            derived={
                "place": {"from": "LOCATION", "op": "strip_parenthesis"},
                "pref": {"from": "LOCATION", "op": "extract_pref"},
                "summary_1": {"from": "SUMMARY", "op": "sentence", "n": 1},
            },
            stats=[
                {
                    "name": "pref_seq",
                    "op": "seq_in_group",
                    "group": "pref",
                    "order": "OCCURRENCE_DATE",
                }
            ],
            big_number={
                "primary": {
                    "text": "{pref}で{pref_seq}件目",
                    "label": "報告",
                    "when": "pref != null",
                },
                "fallback": {"text": "第{No.}号", "label": "番号"},
            },
            select={"cap": 10, "order_by": "No."},
            chips=["{pref}", "{REMARKS}"],
            hide=["PHONE"],
            map={"type": "points", "points": [{"name": "{place}", "lat": "LAT", "lon": "LON"}]},
            comments={
                "pool_calm": ["気をつけたい", "安全第一"],
                "rule": "contains(SUMMARY, ['負傷']) -> none; else calm",
            },
        )
    prepared = prepare(d, tmp_path)
    return d, prepared, tmp_path


def test_scenes_pass_schema_and_ids_and_fields(built) -> None:
    d, prepared, _ = built
    videos = build_dataset(d, prepared)
    assert [v.video_id for v in videos] == [f"example-000{i}" for i in (1, 2, 3, 4)]
    by_id = {v.video_id: v for v in videos}
    for v in videos:
        assert v.scene is not None and validate_scene(v.scene) == []
        assert 15 <= v.scene["durationSec"] <= 30
        assert abs(sum(x["durationSec"] for x in v.scene["lines"]) - v.scene["durationSec"]) < 1e-6

    s1, s2, s3 = (by_id[f"example-000{i}"].scene for i in (1, 2, 3))
    assert s1["source"]["ref"] == "行 #1" and s1["kind"] == "event"
    assert s1["categoryName"] == "例" and s1["wmChar"] == "例"
    assert s1["bigNumber"]["text"] == "東京都で3件目" and s1["bigNumber"]["value"] == 3
    assert s3["bigNumber"]["text"] == "第4号"  # pref が取れない行は fallback(when が偽)
    assert s1["chips"] == ["東京都", "備考あり"] and s2["chips"] == ["東京都"]
    assert s1["map"]["points"][0] == {"name": "東京都千代田区", "lat": 35.7, "lon": 139.7}
    assert s3["map"] is None and s1["sparkline"] is None
    assert s1["lines"][0]["text"].startswith("東京都千代田区で、人の負傷が")
    assert s1["numbers"][0]["name"] == "pref_seq"
    assert s1["comments"] == [] and 6 <= len(s2["comments"]) <= 12  # 負傷は none
    assert s1["durationSec"] == 15 and s1["lines"][-1]["durationSec"] > 0


def test_reproducible(built, tmp_path) -> None:
    d, prepared, _ = built
    a = [v.scene for v in build_dataset(d, prepared)]
    b = [v.scene for v in build_dataset(d, prepared)]
    assert a == b and json.dumps(a) == json.dumps(b)


def test_outputs_videos_jsonl(built) -> None:
    d, prepared, root = built
    videos = build_dataset(d, prepared)
    out = root / "out" / "example"
    write_outputs(videos, out)
    scenes = [
        json.loads(x) for x in (out / "scenes.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows = [json.loads(x) for x in (out / "videos.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [s["videoId"] for s in scenes] == [r["id"] for r in rows]
    r1 = rows[0]
    assert r1["status"] == "ok" and r1["excluded_why"] is None and r1["source_ref"] == "行 #1"
    cols = [c for c, _ in r1["csv_row"]]
    assert "PHONE" not in cols and "pref" not in cols and "pref_seq" not in cols  # hide・derived
    assert cols[:2] == ["No.", "SUMMARY"] and ["LAT", 35.7] in r1["csv_row"]
    assert r1["search_text"] == "例 東京都千代田区 負傷者が出た。"
    assert r1["decisions"]["template"]["choice"] == "injury"
    assert r1["decisions"]["template"]["provider"] == "rules"


def test_unfillable_rows_are_excluded_with_reason(built, make_dataset) -> None:
    d, prepared, _ = built
    # row 3 は filters で落ちるので、選定には入らない。place が空の行を作って、型が選べない例にする
    prepared.frame.loc[5, "place"] = None
    videos = {v.row_id: v for v in build_dataset(d, prepared)}
    assert videos[5].status == "excluded" and videos[5].excluded_why == "no_template"
    assert videos[5].scene is None and videos[5].csv_row  # 除外でも csv_row は残る
    assert videos[5].video_id == "example-0004"  # 連番は除外した行も数える


def test_too_long_is_excluded(built, make_dataset) -> None:
    d, prepared, _ = built
    prepared.frame.loc[1, "place"] = "あ" * 300  # 短い版も30秒に収まらない
    v = next(v for v in build_dataset(d, prepared) if v.row_id == 1)
    assert v.status == "excluded" and v.excluded_why == "too_long"


def test_pii_decision_excludes(built, make_dataset) -> None:
    d, prepared, _ = built
    data = d.model_dump(by_alias=True)
    data["decisions"].append(
        {
            "id": "pii",
            "kind": "noul",
            "question": "q",
            "state": ["SUMMARY"],
            "exclude_if_probability_above": 0.5,
            "fallback": {"rule": "regex_pii"},
        }
    )
    d2 = DatasetDef.model_validate(data)
    prepared.frame.loc[2, "SUMMARY"] = "連絡は090-1234-5678まで。"
    prepared.frame.loc[2, "summary_1"] = "連絡先あり。"
    v = next(v for v in build_dataset(d2, prepared) if v.row_id == 2)
    assert v.status == "excluded" and v.excluded_why == "decision:pii"


def test_schema_violation_is_an_error_not_an_exclusion(built) -> None:
    d, prepared, _ = built
    d = d.model_copy(update={"color": "赤"})  # 生成側のバグを模す(YAML の読み込み後に壊れた)
    with pytest.raises(SceneError):
        build_dataset(d, prepared)


def test_group_source_ref(make_dataset) -> None:
    from opendopa_pipeline.scene import source_ref

    d = make_dataset(grain="group", group_by=["YEAR", "NAME"], aggregate={})
    assert source_ref(d, 3, {"YEAR": 2023, "NAME": "A社"}) == "YEAR=2023 / NAME=A社"


def test_sparkline_and_route_map_and_headline(built) -> None:
    d, prepared, _ = built
    data = d.model_dump(by_alias=True)
    data["sparkline"] = "trend"
    data["stats"].append(
        {
            "name": "trend",
            "op": "series",
            "value": "No.",
            "group_by": "pref",
            "order": "OCCURRENCE_DATE",
        }
    )
    data["map"] = {
        "type": "route",
        "from": {"name": "出発", "lat": "LAT", "lon": "LON"},
        "to": {"name": "{place}", "lat": "LAT", "lon": "LON"},
    }
    data["headline"] = "備考:{REMARKS}"
    data["kind"] = "geo"
    d2 = DatasetDef.model_validate(data)
    prepared2 = prepare(d2, built[2])
    v, v2 = build_dataset(d2, prepared2)[:2]
    assert validate_scene(v.scene) == []
    assert v.scene["kind"] == "geo" and v.scene["map"]["type"] == "route"
    assert v.scene["sparkline"] and set(v.scene["sparkline"][0]) == {"x", "y"}
    assert v.scene["headline"] == "備考:備考あり"
    assert v2.scene["headline"] == "東京都港区で、制御不能が報告されました"  # 穴が空 → 先頭の字幕


def test_spec_rejects_unknown_sparkline_and_map_column(built) -> None:
    d, _, _ = built
    data = d.model_dump(by_alias=True)
    with pytest.raises(ValueError, match="sparkline"):
        DatasetDef.model_validate({**data, "sparkline": "nope"})
