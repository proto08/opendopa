"""空き家バンク(akiya_reg・akiya_sold)の列定義と、生成の結果(#51)。

小さな合成 CSV の単体テストと、実データがあるときだけの照合テスト。
"""

import csv
import json
import shutil
from pathlib import Path

import pytest

from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]
REG_YAML = REPO / "datasets" / "akiya_reg.yaml"
SOLD_YAML = REPO / "datasets" / "akiya_sold.yaml"
REG_CSV = REPO / "data" / "raw" / "akiya_reg" / "01_tourokubukken.csv"
SOLD_CSV = REPO / "data" / "raw" / "akiya_sold" / "02_seiyakubukken.csv"

REG_HEADER = [
    "PROPERTY_NUMBER_ID", "PROPERTY_CATEGORY", "PREFECTURE", "CITY", "NEAREST_STATION",
    "AMOUNT/RENT", "DATE_OF_CONSTRUCTION", "CONSTRUCTION", "OCCUPATION_AREA", "LAYOUT",
    "SIZE_OF_LOT", "STRONG_POINTS", "TOILET_NOTE", "GARDEN", "RETAIL_PREMISES",
]  # fmt: skip
SOLD_HEADER = [
    "CONTRACT_INFO_DATE", "CONTRACT_INFO_AMOUNT/RENT", "ID", "PROPERTY_CATEGORY", "PREFECTURE",
    "CITY", "NEAREST_STATION", "AMOUNT/RENT", "DATE_OF_CONSTRUCTION", "OCCUPATION_AREA",
    "CONSTRUCTION", "SIZE_OF_LOT", "STRONG_POINTS", "TOILET_NOTE", "BATH_NOTE", "GARDEN",
    "RETAIL_PREMISES",
]  # fmt: skip


def reg_row(n, **kw):
    base = {
        "PROPERTY_NUMBER_ID": 7000000 + n, "PROPERTY_CATEGORY": "売買居住用",
        "PREFECTURE": "山梨県",
        "CITY": f"甲府市{n}", "NEAREST_STATION": "", "AMOUNT/RENT": 3500000,
        "DATE_OF_CONSTRUCTION": "1980/3/1", "CONSTRUCTION": "木造", "OCCUPATION_AREA": 987.65,
        "LAYOUT": "4LDK", "SIZE_OF_LOT": 1234.5, "STRONG_POINTS": "", "TOILET_NOTE": "",
        "GARDEN": "", "RETAIL_PREMISES": "無し",
    }  # fmt: skip
    base.update(kw)
    return [base[c] for c in REG_HEADER]


def sold_row(n, **kw):
    base = {
        "CONTRACT_INFO_DATE": "2026/3/28", "CONTRACT_INFO_AMOUNT/RENT": 900000, "ID": 9000000 + n,
        "PROPERTY_CATEGORY": "売買居住用", "PREFECTURE": "栃木県", "CITY": f"鹿沼市{n}",
        "NEAREST_STATION": "鹿沼", "AMOUNT/RENT": 1000000, "DATE_OF_CONSTRUCTION": "1976/9/1",
        "OCCUPATION_AREA": 987.65, "CONSTRUCTION": "木造", "SIZE_OF_LOT": 1234.5,
        "STRONG_POINTS": "", "TOILET_NOTE": "", "BATH_NOTE": "", "GARDEN": "",
        "RETAIL_PREMISES": "無",
    }  # fmt: skip
    base.update(kw)
    return [base[c] for c in SOLD_HEADER]


def write_csv(root, dataset_id, filename, header, rows):
    path = root / "data" / "raw" / dataset_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def generate(root, yaml_path, dataset_id):
    return run_generate(load_dataset(yaml_path), root, root / "out" / dataset_id)


def script_of(video):
    return "".join(x["text"] for x in video.scene["lines"])


# ---- akiya_reg ----


@pytest.fixture
def reg_result(tmp_path):
    rows = [
        reg_row(1),  # 売買 350万円
        reg_row(2, **{"AMOUNT/RENT": 0}),  # 価格 0
        reg_row(3, **{"AMOUNT/RENT": ""}),  # 価格が欠損
        reg_row(4, **{"AMOUNT/RENT": 1_000_000_000}),  # 10億円以上
        reg_row(5, **{"AMOUNT/RENT": 35000, "PROPERTY_CATEGORY": "賃貸居住用"}),  # 賃貸 月3.5万円
        reg_row(
            6, STRONG_POINTS="（有）マツバラ不動産が仲介します。のどかな場所です。"
        ),  # 広告の文
        reg_row(7, STRONG_POINTS="のどかな田園風景に囲まれた静かな住宅地です。駅も近いです。"),
        reg_row(8, STRONG_POINTS="静かな場所です。ご連絡は0996-36-5134まで。"),  # 電話番号
        reg_row(9, **{"DATE_OF_CONSTRUCTION": ""}),  # 築年の欠損
    ]
    write_csv(tmp_path, "akiya_reg", "01_tourokubukken.csv", REG_HEADER, rows)
    return generate(tmp_path, REG_YAML, "akiya_reg")


def test_reg_excludes_bad_prices(reg_result):
    by = {v.row_id: v for v in reg_result.videos}
    assert 2 not in by and 3 not in by and 4 not in by  # clean で落ちる(選定の前)
    excluded = reg_result.report["summary"]["excluded_by_reason"]
    assert excluded["filter"] == 3
    assert {v.row_id for v in reg_result.videos if v.status == "ok"} == {1, 5, 6, 7, 8, 9}


def test_reg_price_phrasing(reg_result):
    by = {v.row_id: v for v in reg_result.videos}
    assert by[1].scene["bigNumber"]["text"] == "350万円"
    assert "価格は350万円です。" in script_of(by[1])
    assert by[5].scene["bigNumber"]["text"] == "月3.5万円"
    assert "賃料は月3.5万円です。" in script_of(by[5])
    assert "築46年の建物です。" in script_of(by[1])
    assert "築" not in script_of(by[9])  # 築年が欠損なら、その行は出さない


def test_reg_ad_and_pii_sentences_not_used(reg_result):
    by = {v.row_id: v for v in reg_result.videos}
    assert "マツバラ" not in json.dumps(by[6].scene, ensure_ascii=False)
    assert "紹介文" not in script_of(by[6])
    assert "紹介文には、「のどかな田園風景に囲まれた静かな住宅地です。」とあります。" in script_of(
        by[7]
    )
    assert "紹介文" not in script_of(by[8])  # 電話番号らしい文字列があれば、記述ごと使わない
    # 自由記述は元の行としても出さない
    for v in by.values():
        cols = [c for c, _ in v.csv_row]
        assert "STRONG_POINTS" not in cols and "TOILET_NOTE" not in cols


def test_reg_area_numbers_never_read(reg_result):
    for v in reg_result.videos:
        if v.scene:
            text = json.dumps(v.scene["lines"], ensure_ascii=False)
            assert "987" not in text and "1234" not in text and "1,234" not in text


def test_reg_all_quality_gates(reg_result):
    for v in reg_result.videos:
        if v.status == "ok":
            assert 15 <= v.scene["durationSec"] <= 30
            assert v.scene["kind"] == "event"
    assert "number_mismatch" not in reg_result.report["summary"]["excluded_by_reason"]


def test_stronger_ad_drops_only_the_sentence(tmp_path):
    # 判断モデルが「広告らしい」と答えたら、行は残し、その文だけ使わない
    from opendopa_pipeline.decider.base import Decision
    from opendopa_pipeline.decider.registry import register

    class AdDecider:
        name = "ad_test"

        def __init__(self, dataset):
            self._rules = dataset

        def decide(self, kind, state, question, options=None, rubric=None):
            if kind == "noul":
                return Decision(confidence=1.0, provider=self.name, probability=0.9)
            return Decision(
                confidence=1.0,
                provider=self.name,
                choice=options[-1].id,
                distribution={o.id: 0.0 for o in options},
            )

    register("ad_test", AdDecider)
    write_csv(
        tmp_path, "akiya_reg", "01_tourokubukken.csv", REG_HEADER,
        [reg_row(1, STRONG_POINTS="のどかな田園風景の静かな住宅地です。")],
    )  # fmt: skip
    res = run_generate(
        load_dataset(REG_YAML), tmp_path, tmp_path / "out" / "akiya_reg", provider="ad_test"
    )
    v = res.videos[0]
    assert v.status == "ok"
    assert v.decisions["stronger_ad"]["dropped"] is True
    assert "紹介文" not in script_of(v)


# ---- akiya_sold ----


@pytest.fixture
def sold_result(tmp_path):
    rows = [
        sold_row(1),  # 成約 90万円、10% 下がった
        sold_row(2, **{"CONTRACT_INFO_AMOUNT/RENT": ""}),  # 成約価格の欠損
        sold_row(3, **{"CONTRACT_INFO_AMOUNT/RENT": 400000}),  # 60% 下がった(±50% 超)
        sold_row(4, **{"CONTRACT_INFO_AMOUNT/RENT": 1600000}),  # 60% 上がった(±50% 超)
        sold_row(5, **{"CONTRACT_INFO_AMOUNT/RENT": 1100000}),  # 10% 上がった(下げ率の文は出さない)
        sold_row(
            6,
            PROPERTY_CATEGORY="賃貸居住用",
            **{"AMOUNT/RENT": 60000, "CONTRACT_INFO_AMOUNT/RENT": 50000},
        ),
        sold_row(7, CONTRACT_INFO_DATE=""),  # 成約日の欠損
        sold_row(8, **{"AMOUNT/RENT": 0}),
    ]
    write_csv(tmp_path, "akiya_sold", "02_seiyakubukken.csv", SOLD_HEADER, rows)
    return generate(tmp_path, SOLD_YAML, "akiya_sold")


def test_sold_discount_outliers_excluded(sold_result):
    ids = {v.row_id for v in sold_result.videos}
    assert ids == {1, 5, 6, 7}  # 2(成約価格なし)・3・4(±50% 超)・8(売り出し価格 0)は clean で落ちる
    assert sold_result.report["summary"]["excluded_by_reason"] == {"filter": 4}


def test_sold_phrasing(sold_result):
    by = {v.row_id: v for v in sold_result.videos}
    s1 = script_of(by[1])
    assert "鹿沼市1の売買居住用が、90万円で成約しました。" in s1
    assert "売り出し時の価格は100万円でした。" in s1
    assert "売り出し時より10%低い価格での成約です。" in s1
    assert "成約日は2026年3月28日です。" in s1
    assert by[1].scene["bigNumber"]["text"] == "90万円"
    assert "低い価格" not in script_of(by[5])  # 成約価格のほうが高いときは言わない
    assert "月5万円で成約しました" in script_of(by[6])
    assert "成約日" not in script_of(by[7])  # 欠損の行は省く
    assert "ID" not in [c for c, _ in by[1].csv_row]


def test_sold_area_numbers_never_read(sold_result):
    for v in sold_result.videos:
        text = json.dumps(v.scene["lines"], ensure_ascii=False)
        assert "987" not in text and "1234" not in text and "1,234" not in text


# ---- 実データ(あるときだけ) ----


@pytest.mark.skipif(not REG_CSV.exists(), reason="data/raw/akiya_reg がありません")
def test_generate_akiya_reg_real(tmp_path):
    shutil.copytree(REPO / "data" / "raw" / "akiya_reg", tmp_path / "data" / "raw" / "akiya_reg")
    res = generate(tmp_path, REG_YAML, "akiya_reg")
    s = res.report["summary"]
    assert 100 <= s["generated"] <= 150
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert s["estimated_sec"]["max"] <= 30
    for v in res.videos:
        if v.scene:
            assert "STRONG_POINTS" not in [c for c, _ in v.csv_row]
            lines = json.dumps(v.scene["lines"], ensure_ascii=False)
            assert "㎡" not in lines and "平米" not in lines


@pytest.mark.skipif(not SOLD_CSV.exists(), reason="data/raw/akiya_sold がありません")
def test_generate_akiya_sold_real(tmp_path):
    shutil.copytree(REPO / "data" / "raw" / "akiya_sold", tmp_path / "data" / "raw" / "akiya_sold")
    res = generate(tmp_path, SOLD_YAML, "akiya_sold")
    s = res.report["summary"]
    assert 100 <= s["generated"] <= 150
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert s["estimated_sec"]["max"] <= 30
