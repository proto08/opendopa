"""鉄軌道の損益・貸借(rail_pl / rail_income / rail_bs)の列定義 YAML。

小さなフィクスチャで、黒字・赤字の言い方、初めて黒字・赤字になった年の強調、任意の行の省略、
品質ゲートを調べる。実データ(`data/raw/`)があれば、件数と数字の不一致も調べる。
"""

import csv
import json
import shutil
from pathlib import Path

import pytest

from opendopa_pipeline.fmt import format_sen_yen, parse_yen
from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]

PL_REV = "RAILWAY_OPERATING_REVENUE_TOTAL_TOTAL_THOUSAND_YEN"
PL_PROFIT = "RAILWAY_OPERATING_PROFIT_LOSS_THOUSAND_YEN"


def _generate(tmp_path: Path, dataset_id: str, rows: list[dict]):
    """rows(列名 → 値)を CSV にして、YAML の `files` に置き、generate する。"""
    dataset = load_dataset(REPO / "datasets" / f"{dataset_id}.yaml")
    path = tmp_path / dataset.files[0]
    path.parent.mkdir(parents=True)
    header = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    res = run_generate(dataset, tmp_path, tmp_path / "out" / dataset_id)
    return {v.row_id: v for v in res.videos}, res


def _lines(video) -> list[str]:
    return [x["text"] for x in video.scene["lines"]]


def _pl(year, name, profit, revenue=1_000_000, category="中小", ratio=95.0):
    return {
        "YEAR": year,
        "CORPORATION_NAME": name,
        "JURISDICTION": "関東運輸局",
        "CATEGORY": category,
        PL_REV: revenue,
        PL_PROFIT: profit,
        "OPERATING_RATIO_POST_DEPR_PERCENT": ratio,
    }


# ---- rail_pl ----


def test_rail_pl_sign_first_time_and_previous_year(tmp_path):
    rows = [
        _pl(2021, "甲鉄道", -100_000),  # 1: 最初の年(前年なし)
        _pl(2022, "甲鉄道", -50_000),  # 2
        _pl(2023, "甲鉄道", 300_000),  # 3: 初めて黒字
        _pl(2021, "乙鉄道", 100_000),  # 4: 最初から黒字(初めてとは言わない)
        _pl(2022, "乙鉄道", 120_000),  # 5
        _pl(2023, "乙鉄道", -40_000),  # 6: 初めて赤字
        _pl(2022, "丙鉄道", 5_000),  # 7
        _pl(2023, "丙鉄道", 10_000),  # 8: 黒字が続く
        _pl(2023, "丁鉄道", 0),  # 9: 0 は黒字とも赤字とも言わない
    ]
    by, res = _generate(tmp_path, "rail_pl", rows)
    ok = {i for i, v in by.items() if v.status == "ok"}
    assert ok == {1, 2, 3, 4, 5, 6, 7, 8}
    assert res.report["summary"]["excluded_by_reason"] == {"filter": 1}

    choice = {i: by[i].decisions["template"]["choice"] for i in ok}
    # 符号どおり。初めて黒字になった年(前年が赤字・当年が黒字)だけが first_profit になる
    assert choice == {
        1: "loss",
        2: "loss",
        3: "first_profit",
        4: "profit",
        5: "profit",
        6: "first_loss",
        7: "profit",
        8: "profit",
    }
    assert _lines(by[3])[0] == "甲鉄道の2023年、鉄道事業の営業損益は黒字3億円でした。"
    assert any("初めてです" in x and "黒字" in x for x in _lines(by[3]))
    assert any("初めてです" in x and "赤字" in x for x in _lines(by[6]))
    assert not any("初めて" in x for i in (1, 2, 4, 5, 7, 8) for x in _lines(by[i]))

    # 前年の黒字・赤字。最初の年は、任意の行として省かれる
    assert "前年は赤字でした。" in _lines(by[3])
    assert "前年は黒字でした。" in _lines(by[6])
    assert not any("前年" in x for x in _lines(by[1]))

    # 赤字の額は大きさだけを読む(符号は「赤字」)。大きな数字・見出し・出典
    assert "赤字4,000万円" in _lines(by[6])[0]
    assert by[6].scene["bigNumber"]["text"] == "4,000万円"
    assert by[3].scene["headline"] == "甲鉄道の2023年、鉄道事業は黒字"
    assert [p["y"] for p in by[3].scene["sparkline"]] == [-100_000, -50_000, 300_000]
    assert by[3].scene["kind"] == "stat"
    for v in by.values():
        if v.scene:
            assert 15 <= v.scene["durationSec"] <= 30


def test_rail_pl_amounts_and_extreme_ratio(tmp_path):
    rows = [
        # JR 東日本 2018 年のような、約 2 兆円の営業収益
        _pl(2022, "大会社", 285_711_829, revenue=2_008_428_041, category="JR"),
        _pl(2023, "大会社", 285_711_829, revenue=2_008_428_041, category="JR", ratio=729_792.9),
    ]
    by, _ = _generate(tmp_path, "rail_pl", rows)
    lines = _lines(by[2])
    assert any("営業収益は約2兆円" in x for x in lines)
    assert "同じ区分の1社中1位です。" in "".join(lines)
    # 桁が極端な営業係数は、読まない(任意の行が省かれる)
    assert not any("営業係数" in x for x in lines)
    assert any("営業係数は95%" in x for x in _lines(by[1]))


# ---- rail_income ----


def _income(year, name, net, revenue=5_000_000, rail=None, bus=None, re=None, ordinary=None):
    return {
        "YEAR": year,
        "COMPANY_NAME": name,
        "SUPERVISORY_OFFICE": "関東運輸局",
        "COMPANY_SIZE": "大手",
        "TOTAL_OPERATING_REVENUE_THOUSANDJPY": revenue,
        "ORDINARY_PROFITLOSS_THOUSANDJPY": ordinary if ordinary is not None else net,
        "NET_PROFITLOSS_THOUSANDJPY": net,
        "RAILWAY_OPERATING_PROFITLOSS_THOUSANDJPY": rail,
        "BUS_OPERATING_PROFITLOSS_THOUSANDJPY": bus,
        "REALESTATE_OPERATING_PROFITLOSS_THOUSANDJPY": re,
    }


def test_rail_income_business_lines_are_optional(tmp_path):
    rows = [
        _income(2023, "多角化鉄道", 500_000, rail=900_000, bus=-30_000, re=200_000),  # 1
        _income(2023, "鉄道だけ", -200_000, rail=-150_000),  # 2: バス・不動産の列が空
        _income(2023, "路線のみ", 120_000, rail=100_000, bus=0, re=-5_000),  # 3: バスは 0=事業なし
        _income(2023, "赤字多角化", -900_000, rail=-1, bus=-2, re=3),  # 4
        _income(2023, "純損益なし", None),  # 5: 純損益が空
    ]
    by, res = _generate(tmp_path, "rail_income", rows)
    assert {i for i, v in by.items() if v.status == "ok"} == {1, 2, 3, 4}
    assert res.report["summary"]["excluded_by_reason"] == {"filter": 1}

    assert [by[i].decisions["template"]["choice"] for i in (1, 2, 3, 4)] == [
        "profit_diversified",
        "loss_rail",
        "profit_diversified",
        "loss_diversified",
    ]
    assert _lines(by[1])[0] == "多角化鉄道の2023年、当期純利益は5億円でした。"
    assert "鉄道事業の営業損益は黒字です。" in _lines(by[1])
    assert "バス事業の営業損益は赤字です。" in _lines(by[1])
    assert "不動産事業の営業損益は黒字です。" in _lines(by[1])
    assert _lines(by[2])[0] == "鉄道だけの2023年、当期純損失は2億円でした。"
    # 空(または 0)の事業の行だけが省かれる
    assert not any("バス" in x or "不動産" in x for x in _lines(by[2]))
    assert not any("バス" in x for x in _lines(by[3]))
    assert "不動産事業の営業損益は赤字です。" in _lines(by[3])
    assert by[2].scene["bigNumber"] == {
        "value": 2,
        "text": "2億円",
        "unit": "",
        "label": "当期純損失",
        "countUp": False,
    }


# ---- rail_bs ----


def _bs(year, name, pct, assets=1_000_000, liabilities=600_000, category="公営"):
    return {
        "YEAR": year,
        "OPERATOR_NAME": name,
        "JURISDICTION": "近畿運輸局",
        "CATEGORY": category,
        "TOTAL_ASSETS": assets,
        "TOTAL_LIABILITIES": liabilities,
        "TOTAL_EQUITY_PERCENT": pct,
    }


def test_rail_bs_ratio_only_and_extremes(tmp_path):
    rows = [
        _bs(2023, "高比率", 75.5),  # 1
        _bs(2023, "低比率", 25.0),  # 2
        _bs(2023, "マイナス", -7.2, liabilities=1_072_000),  # 3
        _bs(2023, "超過", 187.6, liabilities=0),  # 4
        _bs(2023, "資産ゼロ", 0, assets=0, liabilities=0),  # 5: 比率が空
        _bs(2023, "小さな資産", 40.0, assets=500),  # 6: 絶対額は読まない
    ]
    by, res = _generate(tmp_path, "rail_bs", rows)
    assert {i for i, v in by.items() if v.status == "ok"} == {1, 2, 3, 4, 6}
    assert [by[i].decisions["template"]["choice"] for i in (1, 2, 3, 4, 6)] == [
        "equity_high",
        "equity_low",
        "equity_negative",
        "equity_over",
        "equity_low",
    ]
    assert _lines(by[1])[0] == "高比率の2023年、自己資本は総資産の75.5%でした。"
    assert "同じ区分の5社中、自己資本の比率が高い順で2位です。" in _lines(by[1])
    assert "負債は総資産の60%です。" in _lines(by[1])
    assert "総資産は10億円です。" in _lines(by[1])
    # マイナスは符号を言葉にする。総資産を上回る行は、順位・割合に切り替える
    assert "自己資本は総資産のマイナス7.2%でした。" in _lines(by[3])[0]
    assert not any("総資産は" in x for x in _lines(by[4]))
    assert "自己資本が、総資産を上回っています。" in _lines(by[4])
    # 総資産が極端に小さい行は、絶対額の行を省く
    assert not any("総資産は" in x for x in _lines(by[6]))
    assert by[1].scene["bigNumber"]["text"] == "75.5%"


# ---- 3データセット共通 ----


def test_format_sen_yen_for_headline_metrics():
    # 千円の列を億円・兆円にして、誤差 0.5% 以内
    for sen_yen in (2_008_428_041, 285_711_829, 38_916_061, 6_938_290, 104_000_000):
        text = format_sen_yen(sen_yen)
        assert abs(parse_yen(text) - sen_yen * 1000) / (sen_yen * 1000) <= 0.005


@pytest.mark.parametrize("dataset_id", ["rail_pl", "rail_income", "rail_bs"])
def test_real_data_passes_quality_gate(tmp_path, dataset_id):
    src = REPO / "data" / "raw" / dataset_id
    if not src.exists():
        pytest.skip(f"data/raw/{dataset_id} がありません")
    shutil.copytree(src, tmp_path / "data" / "raw" / dataset_id)
    res = run_generate(
        load_dataset(REPO / "datasets" / f"{dataset_id}.yaml"), tmp_path, tmp_path / "out"
    )
    s = res.report["summary"]
    assert 140 <= s["generated"] <= 150
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert res.report["warnings"] == []
    for v in res.videos:
        if v.scene:
            assert 15 <= v.scene["durationSec"] <= 30
            json.dumps(v.scene, ensure_ascii=False)
