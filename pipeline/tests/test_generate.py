import csv
import json
import shutil
from pathlib import Path

import pytest

from opendopa_pipeline.generate import format_summary, run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]
YAML = REPO / "datasets" / "accident.yaml"
REAL_CSV = REPO / "data" / "raw" / "accident" / "02_jikojyouhou.csv"

HEADER = [
    "No.",
    "OCCURRENCE_DATE",
    "OCCURRENCE_LOCATION",
    "OPERATOR",
    "MODEL_OR_MANUFACTURER",
    "INCIDENT_SUMMARY",
    "CASUALTIES_SUMMARY",
    "AIRCRAFT_DAMAGE_SUMMARY",
    "RECURRENCE_PREVENTION_MEASURES",
    "REMARKS",
]
LONG = (
    "機体は強風にあおられながら飛行を続け、その後に操縦者の指示に反応しなくなり、" * 4
    + "着陸した。"
)
ROWS = [
    # 1: 物件(接触) / 負傷なし
    [
        1,
        "2022/12/6 11:20",
        "東京都港区(芝公園)",
        "事業者",
        "X",
        "建物の壁に接触した。その後、着陸した。",
        "なし",
        "プロペラの破損",
        "飛行前の点検を徹底する。",
        "事故に該当する。",
    ],
    # 2: 制御不能
    [
        2,
        "2022/12/7 9:00",
        "大阪府大阪市",
        "個人",
        "X",
        "制御不能となり墜落した。",
        "なし",
        "全損",
        "操作を確認する。",
        "重大インシデントに該当する。",
    ],
    # 3: 負傷者あり(部位は読まない)
    [
        3,
        "2022/12/8 10:05",
        "東京都新宿区",
        "個人",
        "X",
        "着陸時に人に接触した。",
        "右手首を骨折",
        "なし",
        "周囲の確認を行う。",
        "事故に該当する。",
    ],
    # 4: 概要が空(filters で除外)
    [4, "2022/12/9 10:00", "東京都新宿区", "個人", "X", "", "なし", "なし", "", "事故に該当する。"],
    # 5: 電話番号(pii で除外)
    [
        5,
        "2022/12/10 10:00",
        "北海道札幌市",
        "個人",
        "X",
        "操縦者が03-1234-5678に連絡した。",
        "なし",
        "なし",
        "",
        "事故に該当する。",
    ],
    # 6: 禁止表現
    [
        6,
        "2022/12/11 10:00",
        "北海道札幌市",
        "個人",
        "X",
        "原因は不明である。",
        "なし",
        "なし",
        "",
        "事故に該当する。",
    ],
    # 7: 都道府県が取れない海外
    [
        7,
        "2022/12/12 10:00",
        "海外(アメリカ)",
        "事業者",
        "X",
        "機体が落下した。",
        "なし",
        "全損",
        "",
        "事故に該当する。",
    ],
    # 8: 概要だけで30秒に収まらない
    [
        8,
        "2022/12/13 10:00",
        "東京都港区",
        "事業者",
        "X",
        LONG,
        "なし",
        "なし",
        "",
        "事故に該当する。",
    ],
    # 9: 東京都の2件目以降
    [
        9,
        "2022/12/14 10:00",
        "東京都千代田区",
        "事業者",
        "X",
        "電線に接触した。",
        "なし",
        "なし",
        "",
        "事故に該当する。",
    ],
]


@pytest.fixture
def accident_root(tmp_path):
    csv_path = tmp_path / "data" / "raw" / "accident" / "02_jikojyouhou.csv"
    csv_path.parent.mkdir(parents=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(ROWS)
    return tmp_path


def run(root):
    return run_generate(load_dataset(YAML), root, root / "out" / "accident")


def test_generate_accident_synthetic(accident_root):
    res = run(accident_root)
    by_no = {v.row_id: v for v in res.videos}
    out = accident_root / "out" / "accident"

    ok = [v for v in res.videos if v.status == "ok"]
    assert {v.row_id for v in ok} == {1, 2, 3, 7, 9}
    reasons = {v.row_id: v.excluded_why for v in res.videos if v.status == "excluded"}
    assert reasons == {5: "decision:pii", 6: "forbidden", 8: "too_long"}
    assert res.report["summary"]["excluded_by_reason"] == {
        "decision:pii": 1,
        "filter": 1,
        "forbidden": 1,
        "too_long": 1,
    }

    # 負傷者ありは、コメントなし・負傷の内容を原稿にも元の行にも出さない
    injured = by_no[3].scene
    assert injured["comments"] == []
    assert "骨折" not in json.dumps(injured, ensure_ascii=False)
    assert all(c != "CASUALTIES_SUMMARY" for c, _ in by_no[3].csv_row)
    assert any("負傷者の報告があります" in x["text"] for x in injured["lines"])
    assert by_no[1].scene["comments"]

    # 型(rules)と大きな数字
    assert by_no[1].decisions["template"]["choice"] == "object_damage"
    assert by_no[2].decisions["template"]["choice"] == "loss_of_control"
    assert by_no[3].decisions["template"]["choice"] == "injury"
    assert by_no[1].scene["bigNumber"]["text"] == "東京都で1件目"
    assert by_no[7].scene["bigNumber"]["text"] == "第7号"

    # すべて 15〜30 秒
    for v in ok:
        assert 15 <= v.scene["durationSec"] <= 30

    # 出力ファイル
    for name in ("scenes.jsonl", "videos.jsonl", "excluded.csv", "decisions_report.json"):
        assert (out / name).exists()
    assert len((out / "scenes.jsonl").read_text().splitlines()) == 5
    rows = list(csv.DictReader((out / "excluded.csv").open(encoding="utf-8")))
    assert {(r["row_id"], r["reason"]) for r in rows} == {
        ("4", "filter"),
        ("5", "decision:pii"),
        ("6", "forbidden"),
        ("8", "too_long"),
    }
    report = json.loads((out / "decisions_report.json").read_text())
    assert report["summary"]["generated"] == 5
    assert report["summary"]["estimated_sec"]["max"] <= 30
    assert "生成: 5 本" in format_summary(report)


def test_duplicate_scripts_are_dropped(accident_root):
    # 同じ日時・場所・概要の行は、同じ原稿になる(No. は原稿に出ない: 都道府県が取れる行)
    path = accident_root / "data" / "raw" / "accident" / "02_jikojyouhou.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerow(ROWS[0])
        w.writerow([10, *ROWS[0][1:]])
    res = run(accident_root)
    # 大きな数字(件目)は原稿に出ないので、原稿は同じになる
    assert [v.status for v in res.videos] == ["ok", "excluded"]
    assert res.videos[1].excluded_why == "duplicate"


def test_fallback_rate_warning(accident_root):
    # rules は used_fallback=False なので警告は出ない
    res = run(accident_root)
    assert res.report["warnings"] == []


@pytest.mark.skipif(not REAL_CSV.exists(), reason="data/raw/accident がありません")
def test_generate_accident_real(tmp_path):
    shutil.copytree(REPO / "data" / "raw" / "accident", tmp_path / "data" / "raw" / "accident")
    res = run_generate(load_dataset(YAML), tmp_path, tmp_path / "out" / "accident")
    s = res.report["summary"]
    assert 185 <= s["generated"] <= 194
    sec = s["estimated_sec"]
    assert 18 <= sec["min"] <= 20 and 25.5 <= sec["median"] <= 26.5 and sec["max"] <= 30
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert s["excluded_by_reason"].get("too_long") == 2
    t = s["by_type"]
    assert t.get("object_damage", 0) > t.get("loss_of_control", 0) > 0
    for v in res.videos:
        if v.scene and v.decisions["template"]["choice"] == "injury":
            assert v.scene["comments"] == []
