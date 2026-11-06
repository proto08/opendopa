"""鉄軌道 3 データセット(rail_traffic1 / rail_traffic2 / rail_km)の generate(#53)。

元の CSV は git に入れないので、小さなフィクスチャで品質ゲートを通ることを確かめる。
実データがあれば、数字の不一致が 0 であることも確かめる。
"""

import csv
import json
import re
import shutil
from pathlib import Path

import pytest

from opendopa_pipeline.generate import run_generate
from opendopa_pipeline.spec import load_dataset

REPO = Path(__file__).parents[2]

# (事業者, 区分, 管轄) 。「公営の1社」は、区分に1事業者しかないので選ばれない
OPERATORS = [
    ("甲鉄道", "中小", "関東運輸局"),
    ("乙電鉄", "中小", "関東運輸局"),
    ("丙電気鉄道", "中小", "近畿運輸局"),
    ("新規鉄道", "中小", "近畿運輸局"),  # 2023 年だけ(前年比が出ない)
    ("丁急行電鉄", "大手", "関東運輸局"),
    ("戊鉄道", "大手", "近畿運輸局"),
    ("市営地下鉄", "公営", "関東運輸局"),
]


def _write(root: Path, rel: str, header: list[str], rows: list[list]) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _rows(make):
    """`make(i, name, year, is_2023)` が値の列を返す。"""
    out = []
    for i, (name, cat, jur) in enumerate(OPERATORS, start=1):
        for year in (2022, 2023):
            if name == "新規鉄道" and year == 2022:
                continue
            out.append([year, name, jur, cat, *make(i, name, year)])
    return out


def _traffic1(i, name, year):
    total = 123456 * i + (1000 * i if year == 2023 else 0)
    ratio = 40 + 7 * i
    tonnage = 777 * i if name in ("丁急行電鉄", "戊鉄道") else 0
    return [total, ratio, total * 2, tonnage]


def _traffic2(i, name, year):
    # 2023 年に増える事業者と、減る事業者がある
    k = 1 if year == 2023 and i % 2 else (-1 if year == 2023 else 0)
    return [4000 + 100 * i + 20 * k, 6.5 + i + 0.3 * k, 90000 * i + 3000 * k]


def _km(i, name, year):
    km = round(10.3 * i + 0.5, 1)
    cargo = round(5.5 * i, 1) if name in ("丁急行電鉄", "戊鉄道") else 0
    return [
        km,
        cargo,
        100 * i + (3 * i if year == 2023 else 0),
        400 * i - (5 * i if year == 2023 else 0),
    ]


FIXTURES = {
    "rail_traffic1": (
        "data/raw/rail_traffic1/01_tetsudou_unyuseiseki1.csv",
        [
            "YEAR",
            "CORPORATION_NAME",
            "JURISDICTION",
            "CATEGORY",
            "TRANSPORTED_NUMBER_TOTAL",
            "TRANSPORTED_NUMBER_COMMUTER_PASS_RATIO",
            "TRANSPORTED_NUMBER_NON_COMMUTER_PASS",
            "TRANSPORTED_TONNAGE_TOTAL",
        ],
        _traffic1,
    ),
    "rail_traffic2": (
        "data/raw/rail_traffic2/02_tetsudou_unyuseiseki2.csv",
        [
            "YEAR",
            "COMPANY_NAME",
            "JURISDICTION",
            "CATEGORY",
            "AVERAGE_PASSAGE_AMOUNT_PASSENGER",
            "AVERAGE_TRANSPORTED_KILOMETER_PASSENGER",
            "TOTAL_DAY_KILOMETER_PASSENGER",
        ],
        _traffic2,
    ),
    "rail_km": (
        "data/raw/rail_km/03_tetsudou_eigyoukiro.csv",
        [
            "YEAR",
            "OPERATOR_NAME",
            "JURISDICTION",
            "CATEGORY",
            "FISCAL_YEAR_TOTAL_OPERATING_KILOMETERS_PASSENGER",
            "FISCAL_YEAR_TOTAL_OPERATING_KILOMETERS_CARGO",
            "TOTAL_TRAIN_TOTAL",
            "TOTAL_CARS_TOTAL",
        ],
        _km,
    ),
}


@pytest.fixture
def root(tmp_path):
    for rel, header, make in FIXTURES.values():
        _write(tmp_path, rel, header, _rows(make))
    return tmp_path


def run(root: Path, dataset_id: str):
    ds = load_dataset(REPO / "datasets" / f"{dataset_id}.yaml")
    return run_generate(ds, root, root / "out" / dataset_id)


def _text(v) -> str:
    return "".join(x["text"] for x in v.scene["lines"])


def _ok(res):
    return [v for v in res.videos if v.status == "ok"]


@pytest.mark.parametrize("dataset_id", list(FIXTURES))
def test_gate_passes_on_fixture(root, dataset_id):
    res = run(root, dataset_id)
    ok = _ok(res)
    # 2023 年の 6 社(区分に1社の公営を除く)。新規鉄道も、前年比なしで通る
    assert {v.scene["headline"].split("の")[0] for v in ok} >= {"新規鉄道", "甲鉄道", "丁急行電鉄"}
    assert len(ok) == 6
    s = res.report["summary"]
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert s["excluded_by_reason"].get("unreplaced", 0) == 0
    for v in ok:
        assert 15 <= v.scene["durationSec"] <= 30
        assert v.scene["kind"] == "event"  # grain: row の既定
    assert not res.report["warnings"]


@pytest.mark.parametrize("dataset_id", list(FIXTURES))
def test_rank_is_per_category(root, dataset_id):
    """順位は区分ごと。大手(2社)の最大は 1 位、中小(4社)の最大も 1 位になる。"""
    res = run(root, dataset_id)
    frame_csv = {v.scene["headline"].split("の")[0]: v for v in _ok(res) if v.scene["numbers"]}
    rank_names = {
        "rail_traffic1": "traffic_rank",
        "rail_traffic2": "passage_rank",
        "rail_km": "km_rank",
    }
    ranks = {}
    for name, v in frame_csv.items():
        rec = next(n for n in v.scene["numbers"] if n["name"] == rank_names[dataset_id])
        ranks[name] = rec["value"]
    # 値は i が大きいほど大きい(戊鉄道 > 丁急行電鉄、丙電気鉄道 > 乙電鉄 > 甲鉄道)
    assert ranks["戊鉄道"] == 1 and ranks["丁急行電鉄"] == 2
    assert ranks["丙電気鉄道"] in (1, 2)  # 新規鉄道(i=4)が中小で最大
    assert ranks["新規鉄道"] == 1 and ranks["甲鉄道"] == 4
    # 公営は1社しかなく、選ばれない
    assert "市営地下鉄" not in ranks


def test_traffic1_has_no_absolute_value(root):
    res = run(root, "rail_traffic1")
    for v in _ok(res):
        text = _text(v)
        digits = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
        # 輸送人員(123456 の倍数)も貨物のトン数(777 の倍数)も出ない
        for d in digits:
            n = d.replace(",", "")
            assert not (n.isdigit() and len(n) >= 4 and n != "2023"), (v.video_id, text)
        assert "万" not in text and "億" not in text


def test_traffic2_has_no_absolute_value(root):
    res = run(root, "rail_traffic2")
    for v in _ok(res):
        text = _text(v)
        for d in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
            n = d.replace(",", "")
            assert not (n.isdigit() and len(n) >= 4 and n != "2023"), (v.video_id, text)


def test_rail_km_reads_operating_km(root):
    res = run(root, "rail_km")
    by_name = {v.scene["headline"].split("の")[0]: v for v in _ok(res)}
    # 営業キロの絶対値を読み上げる(列は km。10.3 * 1 + 0.5 = 10.8)
    kou = by_name["甲鉄道"]
    assert kou.decisions["template"]["choice"] == "km" and "10.8キロ" in _text(kou)
    km_videos = [v for v in _ok(res) if v.decisions["template"]["choice"] == "km"]
    assert km_videos
    for v in km_videos:
        assert "営業キロは" in _text(v) and "キロです" in _text(v)
        assert v.scene["bigNumber"]["unit"] == "キロ"
    # 列車数・車両数の型は、絶対値(100〜 の台数)を出さず、営業キロ以外の4桁以上もない
    for v in _ok(res):
        if v.decisions["template"]["choice"] in ("trains", "cars"):
            text = _text(v).replace("2023", "")
            assert not re.search(r"\d{3,}", text), (v.video_id, text)


@pytest.mark.parametrize("dataset_id", ["rail_traffic1", "rail_km"])
def test_no_yoy_sentence_without_previous_year(root, dataset_id):
    """2022 年の行がない事業者(新規鉄道)の原稿に、前年比の文が出ない(任意の行が省かれる)。"""
    res = run(root, dataset_id)
    new = next(v for v in _ok(res) if v.scene["headline"].startswith("新規鉄道"))
    assert "前年" not in _text(new)
    assert not any(
        n["name"].endswith("yoy_ratio") or n["name"].endswith("_yoy") for n in new.scene["numbers"]
    )
    # 前年がある事業者には前年比の文がある型もある
    assert any("前年" in _text(v) for v in _ok(res) if v is not new)


def test_traffic1_yoy_sentence_has_direction(root):
    res = run(root, "rail_traffic1")
    texts = [_text(v) for v in _ok(res) if "前年" in _text(v)]
    assert texts
    for t in texts:
        assert (
            re.search(r"前年に比べて\d+(?:\.\d+)?%(増えました|減りました)", t)
            or "前年に比べて、" in t
        )


def test_traffic1_freight_type(root):
    """貨物のある事業者が区分に複数あり、順位が上位なら freight 型になる(トン数は出さない)。"""
    res = run(root, "rail_traffic1")
    v = next(v for v in _ok(res) if v.scene["headline"].startswith("丁急行電鉄"))
    assert v.decisions["template"]["choice"] == "freight"
    assert "貨物" in _text(v) and "777" not in _text(v)


def test_outputs_are_written(root):
    res = run(root, "rail_km")
    out = root / "out" / "rail_km"
    assert len((out / "scenes.jsonl").read_text().splitlines()) == len(_ok(res))
    report = json.loads((out / "decisions_report.json").read_text())
    assert report["summary"]["generated"] == len(_ok(res))


@pytest.mark.parametrize(
    ("dataset_id", "rel"),
    [(k, v[0]) for k, v in FIXTURES.items()],
)
def test_real_data(tmp_path, dataset_id, rel):
    src = REPO / rel
    if not src.exists():
        pytest.skip(f"{rel} がありません")
    dst = tmp_path / rel
    dst.parent.mkdir(parents=True)
    shutil.copy(src, dst)
    res = run(tmp_path, dataset_id)
    s = res.report["summary"]
    assert s["generated"] > 0
    assert s["excluded_by_reason"].get("number_mismatch", 0) == 0
    assert s["estimated_sec"]["max"] <= 30
