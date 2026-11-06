"""内航海運の 2 データセット(naiko_route・naiko_ship。#55)。

合成した小さな CSV を本物の列定義 YAML(`datasets/*.yaml`)に通して、除外・補完・原稿を確かめる。
"""

import csv
import json
from pathlib import Path

import pytest

from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]

ROUTE_FILE = "data/raw/naiko_route/02_naikousenpakuyusoutoukeichousa.csv"
ROUTE_HEADER = [
    "YEAR",
    "LOADING PORT_NAME",
    "LOADING PORT_PREFECTURE NAME",
    "UNLOADING PORT_NAME",
    "UNLOADING PORT_PREFECTURE NAME",
    "SAMPLE SIZE",
    "AVERAGE_GROSS TONNAGE",
    "AVERAGE_LOADING RATIO",
    "AVERAGE_CARGO WEIGHT",
    "AVERAGE_TRANSPORT DISTANCE",
    "LOADING PORT_LATITUDE",
    "LOADING PORT_LONGITUDE",
    "DISCHARGE PORT_LATITUDE",
    "DISCHARGE PORT_LONGITUDE",
]
ROUTE_ROWS = [
    # 1: 標準。座標あり。積載率 0.62 → 62%。距離 987・貨物 54321 は原稿に出ない
    [2023, "甲港", "A県", "乙港", "B県", 500, 747.0, 0.62, 54321, 987, 34.1, 132.1, 34.7, 135.2],
    # 2: 2013〜2016 は除く
    [2015, "甲港", "A県", "乙港", "B県", 900, 747.0, 0.50, 1, 1, 34.1, 132.1, 34.7, 135.2],
    # 3: 積み港の座標が欠損。同じ港名の別の行(1 行目)から補う
    [2022, "甲港", "A県", "丙港", "C県", 400, 800.0, 0.40, 1, 1, "", "", 35.0, 136.0],
    # 4: 降ろし港の座標が欠損だが、積み港として他の行に座標がある(丙港は 3 行目の降ろし側から)
    [2022, "丙港", "C県", "甲港", "A県", 300, 800.0, 0.45, 1, 1, "", "", 34.1, 132.1],
    # 5: 丁港は座標がどこにもない → 除く
    [2022, "丁港", "", "乙港", "B県", 700, 600.0, 0.30, 1, 1, "", "", 34.7, 135.2],
    # 6: 積載率が 1 を超える外れ値 → 除く
    [2021, "甲港", "A県", "乙港", "B県", 200, 700.0, 1.51, 1, 1, 34.1, 132.1, 34.7, 135.2],
    # 7: 積載率が高い型
    [2021, "乙港", "B県", "甲港", "A県", 100, 900.0, 0.85, 1, 1, 34.7, 135.2, 34.1, 132.1],
]

SHIP_FILE = "data/raw/naiko_ship/01_naikoukaiungyou_jigyougaikyouhoukoku.csv"
SHIP_HEADER = [
    "Ship_ID",
    "Business_Management_ID",
    "Address",
    "Usage",
    "Gross_Tonnage",
    "Deadweight_Tonnage",
    "Length",
    "Horsepower",
    "Ship_Type_1",
    "Launch_Year_(20",
    "Supervisory_Transport_Bureau",
]
SHIP_ROWS = [
    [
        "S0001",
        "B9999999",
        "東京都千代田区1-1-1",
        "営業船",
        499,
        1200,
        65.5,
        1300,
        "貨物船",
        "1980年～1999年",
        "関東",
    ],
    ["S0002", "B8888888", "", "営業船", 3000, 0, 95.0, 0, "油送船", "2000年～", "近畿"],
    ["S0003", "B7777777", "", "営業船", 120, 300, 40.0, 500, "引船", "1960年～1979年", "九州"],
    [
        "S0004",
        "B6666666",
        "",
        "営業船",
        "",
        0,
        30.0,
        0,
        "貨物船",
        "",
        "関東",
    ],  # 総トン数なし → 除く
    ["S0005", "B5555555", "", "営業船", 700, 0, "", 0, "貨物船", "", "関東"],  # 全長なしでも作れる
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
def route(tmp_path):
    write_csv(tmp_path, ROUTE_FILE, ROUTE_HEADER, ROUTE_ROWS)
    return generate(tmp_path, "naiko_route")


@pytest.fixture
def ship(tmp_path):
    write_csv(tmp_path, SHIP_FILE, SHIP_HEADER, SHIP_ROWS)
    return generate(tmp_path, "naiko_ship")


def texts(scene) -> str:
    return "".join(x["text"] for x in scene["lines"])


def by_row(res):
    return {v.row_id: v for v in res.videos if v.scene}


def test_route_excludes_outliers_and_unlocatable_rows(route):
    # 2015 年(2 行目)、座標が補えない丁港(5 行目)、積載率 1.51(6 行目)は動画にならない
    assert set(by_row(route)) == {1, 3, 4, 7}
    assert all(v.status == "ok" for v in route.videos)
    assert len(route.videos) == 4


def test_route_fills_port_coordinates_from_same_name(route):
    scenes = {rid: v.scene for rid, v in by_row(route).items()}
    # 3 行目: 甲港の座標は 1 行目から。丙港は自分の行にある
    assert scenes[3]["map"] == {
        "type": "route",
        "from": {"name": "甲港", "lat": 34.1, "lon": 132.1},
        "to": {"name": "丙港", "lat": 35.0, "lon": 136.0},
    }
    # 4 行目: 丙港(積み港)の座標は、3 行目の降ろし側から
    assert scenes[4]["map"]["from"] == {"name": "丙港", "lat": 35.0, "lon": 136.0}
    assert all(s["map"]["type"] == "route" and s["kind"] == "geo" for s in scenes.values())
    json.dumps([s["map"] for s in scenes.values()])


def test_route_ratio_in_percent(route):
    scene = by_row(route)[1].scene
    assert scene["bigNumber"] == {
        "value": 62,
        "text": "62",
        "unit": "%",
        "label": "平均の積載率",
        "countUp": True,
    }
    assert "平均の積載率は62%" in texts(scene)
    assert "平均の総トン数は747トン" in texts(scene)


def test_route_never_reads_distance_or_cargo_weight(route):
    for v in by_row(route).values():
        shown = texts(v.scene) + v.scene["headline"] + json.dumps(v.scene["bigNumber"])
        assert "54321" not in shown and "987" not in shown
        assert "距離" not in shown and "貨物の重さ" not in shown


def test_route_types_and_length(route):
    by = {rid: v.decisions["template"]["choice"] for rid, v in by_row(route).items()}
    assert by[7] == "high_load"  # 積載率 0.85
    assert by[1] == "standard"
    for v in route.videos:
        assert 15 <= v.scene["durationSec"] <= 30
    assert route.report["summary"]["generated"] == 4


def test_ship_one_video_per_ship_with_total_ton(ship):
    assert len(ship.videos) == 4
    assert all(v.status == "ok" for v in ship.videos)
    scenes = {v.row_id: v.scene for v in ship.videos}
    assert set(scenes) == {1, 2, 3, 5}  # 4 行目(総トン数なし)は除く
    s = scenes[1]
    assert s["bigNumber"]["text"] == "499" and s["bigNumber"]["unit"] == "トン"
    assert "建造は1980年～1999年です" in texts(s) and "全長は65.5メートル" in texts(s)
    assert s["kind"] == "event" and s["map"] is None
    assert "全長" not in texts(scenes[5])  # 全長が欠損なら、その行だけ省く


def test_ship_hides_operator_and_ship_id(ship):
    for v in ship.videos:
        cols = [c for c, _ in v.csv_row]
        for hidden in ("Address", "Business_Management_ID", "Ship_ID"):
            assert hidden not in cols
        dumped = json.dumps(v.csv_row, ensure_ascii=False) + texts(v.scene)
        assert not any(w in dumped for w in ("千代田", "B9999999", "S0001"))
    # 建造年代は、列名が切れていたものを LAUNCH_BAND に置き換えて使う
    assert any("LAUNCH_BAND" in [c for c, _ in v.csv_row] for v in ship.videos)


@pytest.mark.skipif(not (REPO / ROUTE_FILE).exists(), reason="data/raw/naiko_route がありません")
def test_route_real_data(tmp_path):
    dest = tmp_path / ROUTE_FILE
    dest.parent.mkdir(parents=True)
    dest.write_bytes((REPO / ROUTE_FILE).read_bytes())
    res = generate(tmp_path, "naiko_route")
    assert res.report["summary"]["generated"] == 150
    assert all(v.status == "ok" for v in res.videos)
    assert all(v.scene["map"]["type"] == "route" for v in res.videos)
