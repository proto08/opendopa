"""レンタカーの 2 データセット(rental_result・rental_fleet。#52)。

合成した小さな CSV を本物の列定義 YAML(`datasets/*.yaml`)に通して、集計・順位・原稿を確かめる。
"""

import csv
import json
from pathlib import Path

import pytest

from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]

RESULT_FILE = "data/raw/rental_result/01_yousiki1_kashiwatashijissekihoukokusho.csv"
RESULT_HEADER = [
    "FISCAL_YEAR",
    "REPORTING_PERIOD",
    "OPERATOR_ID",
    "PREFECTURE_NAME",
    "ADDRESS_LATITUDE",
    "ADDRESS_LONGITUDE",
    "TOTAL_VEHICLE_COUNT",
    "TOTAL_RENTAL_TIMES",
    "TOTAL_RENTAL_DAYS",
    "TOTAL_RENTAL_FEES",
]
PERIOD = "令和7年4月1日から令和8年3月31日まで"
RESULT_ROWS = [
    # A県は 2 事業者。合計は 回数150・台数15・日数450・売上450万円
    [2025, PERIOD, 9876543, "A県", 35.1, 139.1, 10, 100, 300, 3_000_000],
    [2025, PERIOD, 9876544, "A県", 35.1, 139.1, 5, 50, 150, 1_500_000],
    [2025, PERIOD, 1111111, "B県", 26.2, 127.7, 20, 400, 800, 4_000_000],
    [2025, PERIOD, 2222222, "C県", 34.0, 134.0, 5, 0, 0, 0],  # 貸出 0 は除く
    [2024, PERIOD, 3333333, "D県", 33.0, 130.0, 50, 999, 999, 9_990_000],  # 2025 以外は除く
    [2025, PERIOD, 4444444, "E県", 36.0, 138.0, 3, 30, 60, 300_000],
    [2025, PERIOD, 5555555, "F県", 37.0, 140.0, 2, 10, 20, 100_000],
]

FLEET_FILE = "data/raw/rental_fleet/02_yousiki2_haisyasyaryousuu.csv"
FLEET_HEADER = [
    "OFFICE_VEHICLE_ALLOCATION_LIST_TRANSPORT_BRANCH",
    "OFFICE_VEHICLE_ALLOCATION_LIST_LOCATION",
    "OWNED_VEHICLES_TOTAL",
    "TOTAL_SUM",
]
FLEET_ROWS = [
    ["甲", "A県", 111, 5000],
    ["甲", "", 222, 5000],  # 甲の合計は 333
    ["乙", "B県", 444, 6000],
    ["丙", "C県", "", ""],  # 車両数が欠損だけの運輸支局は動画にしない
    ["丁", "D県", 0, 0],  # 0 だけも同じ
    ["", "E県", 55, 55],  # 運輸支局が空の行は除く
]


def write_csv(root: Path, rel: str, header: list[str], rows: list[list]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def generate(root: Path, dataset_id: str):
    return run_generate(
        load_dataset(REPO / "datasets" / f"{dataset_id}.yaml"), root, root / "out" / dataset_id
    )


@pytest.fixture
def result(tmp_path):
    write_csv(tmp_path, RESULT_FILE, RESULT_HEADER, RESULT_ROWS)
    return generate(tmp_path, "rental_result")


@pytest.fixture
def fleet(tmp_path):
    write_csv(tmp_path, FLEET_FILE, FLEET_HEADER, FLEET_ROWS)
    return generate(tmp_path, "rental_fleet")


def by_pref(res):
    return {v.scene["source"]["ref"].split("=")[1]: v.scene for v in res.videos if v.scene}


def texts(scene) -> str:
    return "".join(x["text"] for x in scene["lines"])


def test_rental_result_aggregates_by_prefecture(result):
    # 2025 年度で貸出があるのは A・B・E・F。C(貸出 0)と D(2024 年度)は除かれ、都道府県ごとに 1 本
    scenes = by_pref(result)
    assert set(scenes) == {"A県", "B県", "E県", "F県"}
    assert all(v.status == "ok" for v in result.videos)
    assert len(result.videos) == 4

    a = scenes["A県"]
    assert a["bigNumber"] == {
        "value": 150,
        "text": "150",
        "unit": "回",
        "label": "年間の貸出回数",
        "countUp": True,
    }
    # 合計・順位・導出が手計算と一致する(回数 B > A > E > F、車両あたりの売上 A > B > E > F)
    text = texts(a)
    assert "貸出は年間150回" in text
    assert "4都道府県の中で2位" in text
    assert "車両あたりの売上は30万円で、1位" in text  # 450万円 ÷ 15台
    assert "平均の日数は、3日" in text  # 450日 ÷ 150回
    assert "合わせて15台" in text
    assert "貸出は年間400回" in texts(scenes["B県"])
    assert "1位" in texts(scenes["B県"])


def test_rental_result_map_is_points(result):
    m = by_pref(result)["A県"]["map"]
    assert m["type"] == "points"
    assert m["points"] == [{"name": "A県", "lat": 35.1, "lon": 139.1}]
    json.dumps(m)


def test_rental_result_script_hides_operator_and_period(result):
    for scene in by_pref(result).values():
        text = texts(scene)
        assert not any(w in text for w in ("令和", "4月", "9876543", "1111111", "OPERATOR"))
    for v in result.videos:
        cols = [c for c, _ in v.csv_row]
        assert "OPERATOR_ID" not in cols
        assert "REPORTING_PERIOD" not in cols
        assert "令和" not in json.dumps(v.csv_row, ensure_ascii=False)


def test_rental_result_types_and_length(result):
    types = {v.decisions["template"]["choice"] for v in result.videos}
    assert types <= {"top_times", "top_fleet", "top_per_vehicle", "standard"}
    # 貸出回数が 3 位以内の B 県は top_times
    by = {v.scene["source"]["ref"]: v.decisions["template"]["choice"] for v in result.videos}
    assert by["PREFECTURE_NAME=B県"] == "top_times"
    for v in result.videos:
        assert 15 <= v.scene["durationSec"] <= 30
    assert result.report["summary"]["generated"] == 4


def test_rental_fleet_one_video_per_branch(fleet):
    refs = {v.scene["source"]["ref"] for v in fleet.videos if v.scene}
    assert refs == {"BRANCH=甲", "BRANCH=乙"}
    assert len(fleet.videos) == 2
    assert all(v.status == "ok" for v in fleet.videos)


def test_rental_fleet_shows_only_rank_and_share(fleet):
    scenes = {v.scene["source"]["ref"]: v.scene for v in fleet.videos}
    kou, otsu = scenes["BRANCH=甲"], scenes["BRANCH=乙"]
    # 乙(444)が 1 位、甲(333)が 2 位。割合は 444/777 = 57.1%、333/777 = 42.9%
    assert otsu["bigNumber"]["text"] == "1" and otsu["bigNumber"]["unit"] == "位"
    assert kou["bigNumber"]["text"] == "2"
    assert "2の運輸支局の中で1位" in texts(otsu)
    assert "57.1%" in texts(otsu)
    assert "42.9%" in texts(kou)
    # 車両数の絶対値は、原稿・大きな数字・見出し・元の行のどこにも出ない
    for scene in (kou, otsu):
        shown = (
            texts(scene) + scene["headline"] + json.dumps(scene["bigNumber"], ensure_ascii=False)
        )
        assert not any(n in shown for n in ("111", "222", "333", "444", "777", "5000", "6000"))
    for v in fleet.videos:
        assert "OWNED_VEHICLES_TOTAL" not in [c for c, _ in v.csv_row]
        assert not any(w in texts(v.scene) for w in ("台",))
    assert kou["map"] is None
