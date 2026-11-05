from pathlib import Path

import pandas as pd
import pytest

from opendopa_pipeline.ingest import IngestError
from opendopa_pipeline.prepare import aggregate_groups, prepare
from opendopa_pipeline.spec import DatasetError, load_dataset, validate_against_columns

CSV = """No.,SUMMARY,LOCATION,OCCURRENCE_DATE,REMARKS
1,概要1。次の文。,東京都千代田区,2022/12/10 9:00,x
2,概要2。,東京都港区(羽田),2022/12/6 11:20,x
3,,大阪府大阪市,2022/1/1 0:00,x
4,概要4。,海外で発生,2022/2/1 0:00,x
"""


def test_prepare_end_to_end(tmp_path, make_dataset) -> None:
    csv = tmp_path / "data" / "raw" / "example" / "example.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text(CSV, encoding="utf-8-sig")
    src_before = csv.read_bytes()
    d = make_dataset(
        derived={
            "place": {"from": "LOCATION", "op": "strip_parenthesis"},
            "pref": {"from": "LOCATION", "op": "extract_pref"},
            "summary_1": {"from": "SUMMARY", "op": "sentence", "n": 1},
        },
        big_number={
            "primary": {"text": "{pref}で{pref_seq}件目", "label": "x", "when": "pref != null"},
            "fallback": {"text": "第{No.}号", "label": "y"},
        },
        stats=[
            {"name": "pref_seq", "op": "seq_in_group", "group": "pref", "order": "OCCURRENCE_DATE"}
        ],
    )

    p = prepare(d, tmp_path, tmp_path / "out" / "example")

    assert csv.read_bytes() == src_before  # 元データは書き換えない
    assert list(p.frame.index) == [1, 2, 4]
    assert [(e.row_id, e.reason) for e in p.excluded] == [(3, "SUMMARY が欠損")]
    assert (tmp_path / "out" / "example" / "excluded.csv").read_text(
        encoding="utf-8"
    ).splitlines() == [
        "row_id,reason",
        "3,SUMMARY が欠損",
    ]
    assert p.frame.loc[2, "place"] == "東京都港区"
    assert p.frame.loc[1, "summary_1"] == "概要1。"
    assert p.frame.loc[1, "pref_seq"] == 2 and p.frame.loc[2, "pref_seq"] == 1
    assert pd.isna(p.frame.loc[4, "pref"]) and pd.isna(p.frame.loc[4, "pref_seq"])
    assert p.numbers[1][0]["inputs"] == {"pref": "東京都", "OCCURRENCE_DATE": "2022/12/10 9:00"}


def test_unknown_column_in_hole_is_caught_after_load(tmp_path, make_dataset) -> None:
    (tmp_path / "e.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(DatasetError):
        prepare(make_dataset(files=["e.csv"]), tmp_path)


@pytest.mark.filterwarnings("ignore:.*型の数")
def test_grain_group(tmp_path, make_dataset) -> None:
    text = (
        "PREF,YEAR,CARS,TIMES,FEES\n"
        "東京都,2025,10,100,1000\n東京都,2025,5,50,500\n東京都,2024,99,99,99\n"
        "大阪府,2025,8,40,800\n沖縄県,2025,2,0,0\n"
    )
    (tmp_path / "r.csv").write_text(text, encoding="utf-8")
    d = make_dataset(
        files=["r.csv"],
        grain="group",
        group_by=["PREF"],
        aggregate={"CARS": "sum", "TIMES": "sum", "FEES": "sum"},
        filters=["YEAR == 2025", "TIMES > 0"],
        derived={},
        stats=[
            {"name": "rank", "op": "rank_in_group", "value": "TIMES"},
            {"name": "fee_per_car", "op": "per", "num": "FEES", "den": "CARS"},
        ],
        big_number={"primary": {"text": "{PREF}", "label": "x"}},
        template_groups=[
            {
                "id": "t",
                "label": "t",
                "templates": [{"id": "s", "short": True, "lines": ["{PREF}"]}],
            }
        ],
        template_select=None,
        required=[],
        decisions=[],
        fallback_rules={},
        embed_text="{PREF}",
    )
    p = prepare(d, tmp_path)
    f = p.frame
    assert list(f["PREF"]) == ["大阪府", "東京都"]
    tokyo = f[f["PREF"] == "東京都"].iloc[0]
    assert (tokyo["CARS"], tokyo["TIMES"], tokyo["FEES"], tokyo["n_rows"]) == (15, 150, 1500, 2)
    assert tokyo["rank"] == 1 and tokyo["fee_per_car"] == 100
    assert [(e.reason) for e in p.excluded] == [
        "filters を満たさない: YEAR == 2025",
        "filters を満たさない: TIMES > 0",
    ]


def test_group_requires_group_by(make_dataset) -> None:
    with pytest.raises(ValueError, match="group_by"):
        make_dataset(grain="group")
    with pytest.raises(ValueError, match="grain: group のときだけ"):
        make_dataset(group_by=["a"])


def test_aggregate_all_null_sum_is_null(make_dataset) -> None:
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [None, None, 1.0]})
    d = make_dataset(grain="group", group_by=["g"], aggregate={"v": "sum"})
    out = aggregate_groups(df, d)
    assert pd.isna(out.loc[1, "v"]) and out.loc[2, "v"] == 1.0
    with pytest.raises(IngestError):
        aggregate_groups(df, make_dataset(grain="group", group_by=["zz"]))


def test_group_columns_are_checked_against_data(make_dataset) -> None:
    d = make_dataset(grain="group", group_by=["zz"])
    with pytest.raises(DatasetError, match="zz"):
        validate_against_columns(d, ["a"])


def test_example_yaml_still_loads() -> None:
    example = Path(__file__).parents[2] / "datasets" / "_example.yaml"
    assert load_dataset(example).grain == "row"
