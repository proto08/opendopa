import math

import pandas as pd
import pytest

from opendopa_pipeline.stats import StatError, apply_stats, known_stat_ops


def run(make_dataset, df: pd.DataFrame, *stats: dict):
    df = df.copy()
    df.index = pd.RangeIndex(1, len(df) + 1, name="row_id")
    before = df.copy(deep=True)
    out, numbers = apply_stats(df, make_dataset(stats=list(stats)))
    pd.testing.assert_frame_equal(df, before)  # 入力は変わらない
    return out, numbers


def isnull(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def test_rank_in_group_ties_and_nulls(make_dataset) -> None:
    df = pd.DataFrame({"g": ["a", "a", "a", "b", "b"], "v": [10.0, 10.0, 5.0, 1.0, None]})
    out, numbers = run(
        make_dataset, df, {"name": "r", "op": "rank_in_group", "value": "v", "group": "g"}
    )
    assert list(out["r"][:4]) == [1, 1, 3, 1]  # 同順位は同じ順位、次は飛ぶ
    assert isnull(out["r"].iloc[4])
    assert list(out["r_n"][:3]) == [3, 3, 3] and out["r_n"].iloc[3] == 1  # 欠損は数えない
    rec = numbers[3][0]
    assert rec["name"] == "r" and rec["op"] == "rank_in_group"
    assert rec["columns"] == ["v", "g"]
    assert rec["inputs"] == {"v": 5.0, "n": 3} and rec["value"] == 3 and rec["display"] == "3位"
    assert 5 not in numbers  # 欠損の行は記録しない


def test_rank_asc_and_whole_table(make_dataset) -> None:
    df = pd.DataFrame({"v": [3, 1, 2]})
    out, _ = run(
        make_dataset, df, {"name": "r", "op": "rank_in_group", "value": "v", "order": "asc"}
    )
    assert list(out["r"]) == [3, 1, 2]


def test_yoy(make_dataset) -> None:
    df = pd.DataFrame(
        {
            "co": ["A", "A", "A", "B", "B"],
            "year": [2021, 2022, 2023, 2022, 2023],
            "v": [100.0, 110.0, 99.0, 0.0, 50.0],
        }
    )
    out, numbers = run(
        make_dataset,
        df,
        {"name": "d", "op": "yoy_diff", "value": "v", "group_by": ["co"], "year": "year"},
        {"name": "r", "op": "yoy_ratio", "value": "v", "group_by": "co", "year": "year"},
    )
    assert isnull(out["d"].iloc[0])  # 前年がない行は欠損
    assert list(out["d"][1:3]) == [10.0, -11.0]
    assert isnull(out["d"].iloc[3])  # B の最初の年
    assert out["d"].iloc[4] == 50.0
    assert out["r"].iloc[1] == pytest.approx(10.0)
    assert out["r"].iloc[2] == pytest.approx(-10.0)
    assert isnull(out["r"].iloc[4])  # 前年が 0 なら率は欠損
    assert numbers[2][1]["display"] == "10%"
    assert numbers[2][0]["inputs"] == {"v": 110.0, "prev": 100.0}
    assert 1 not in numbers


def test_share_of_total(make_dataset) -> None:
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1.0, 3.0, 0.0]})
    out, numbers = run(
        make_dataset, df, {"name": "s", "op": "share_of_total", "value": "v", "group": "g"}
    )
    assert list(out["s"][:2]) == [25.0, 75.0]
    assert isnull(out["s"].iloc[2])  # 合計 0
    assert numbers[2][0]["display"] == "75%"


def test_sum_mean_count_by(make_dataset) -> None:
    df = pd.DataFrame({"g": ["a", "a", "b", None], "v": [1.0, 3.0, None, 5.0]})
    out, _ = run(
        make_dataset,
        df,
        {"name": "s", "op": "sum_by", "group": "g", "value": "v"},
        {"name": "m", "op": "mean_by", "group": "g", "value": "v"},
        {"name": "c", "op": "count_by", "group": "g"},
        {"name": "cv", "op": "count_by", "group": "g", "value": "v"},
    )
    assert list(out["s"][:2]) == [4.0, 4.0] and list(out["m"][:2]) == [2.0, 2.0]
    assert isnull(out["s"].iloc[2]) and isnull(out["m"].iloc[2])  # 全部欠損
    assert list(out["c"][:3]) == [2, 2, 1] and isnull(out["c"].iloc[3])  # グループが欠損の行
    assert list(out["cv"][:3]) == [2, 2, 0]


def test_series_max_12_up_to_current_row(make_dataset) -> None:
    df = pd.DataFrame({"co": ["A"] * 15, "year": list(range(2009, 2024)), "v": list(range(15))})
    df = df.sample(frac=1, random_state=1)  # 並びは年順でなくてよい
    out, _ = run(
        make_dataset,
        df,
        {"name": "ts", "op": "series", "value": "v", "group_by": "co", "order": "year"},
    )
    last = out[df["year"].to_numpy() == 2023]["ts"].iloc[0]
    assert last == list(range(3, 15)) and len(last) == 12
    first = out[df["year"].to_numpy() == 2010]["ts"].iloc[0]
    assert first == [0, 1]  # その年より後は含めない
    with pytest.raises(StatError, match="max_points"):
        run(
            make_dataset,
            df,
            {
                "name": "x",
                "op": "series",
                "value": "v",
                "group_by": "co",
                "order": "year",
                "max_points": 13,
            },
        )


def test_seq_in_group_is_date_order(make_dataset) -> None:
    # 文字列の順だと 2022/12/10 < 2022/12/6 になってしまう。日付として並べる
    df = pd.DataFrame(
        {
            "pref": ["東京都", "東京都", "東京都", "大阪府", None, "東京都"],
            "d": [
                "2022/12/10 9:00",
                "2022/12/6 11:20",
                "2023/1/1 0:00",
                "2022/1/1",
                "2022/1/1",
                None,
            ],
        }
    )
    out, numbers = run(
        make_dataset, df, {"name": "n", "op": "seq_in_group", "group": "pref", "order": "d"}
    )
    assert out["n"].iloc[1] == 1 and out["n"].iloc[0] == 2 and out["n"].iloc[2] == 3
    assert out["n"].iloc[3] == 1
    assert isnull(out["n"].iloc[4])  # グループが欠損
    assert out["n"].iloc[5] == 4  # 順序が欠損の行は最後
    assert numbers[1][0]["value"] == 2 and numbers[1][0]["display"] == "2件"


def test_seq_ties_keep_row_order(make_dataset) -> None:
    df = pd.DataFrame({"g": ["a", "a"], "d": [1, 1]})
    out, _ = run(make_dataset, df, {"name": "n", "op": "seq_in_group", "group": "g", "order": "d"})
    assert list(out["n"]) == [1, 2]


def test_is_first_time(make_dataset) -> None:
    df = pd.DataFrame(
        {
            "co": ["A"] * 4 + ["B"] * 2 + ["C"] * 3,
            "year": [2020, 2021, 2022, 2023, 2020, 2021, 2020, 2021, 2022],
            "v": [-5.0, -1.0, 3.0, 4.0, 5.0, 6.0, 2.0, -1.0, -2.0],
        }
    )
    out, _ = run(
        make_dataset,
        df,
        {"name": "f", "op": "is_first_time", "value": "v", "group_by": "co", "order": "year"},
        {
            "name": "g",
            "op": "is_first_time",
            "value": "v",
            "group_by": "co",
            "order": "year",
            "condition": "negative",
        },
    )
    assert list(out["f"]) == [
        False,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
    ]  # B は最初から黒字
    assert list(out["g"]) == [False, False, False, False, False, False, False, True, False]


def test_per(make_dataset) -> None:
    df = pd.DataFrame({"a": [100.0, 5.0, None], "b": [4.0, 0.0, 2.0]})
    out, numbers = run(make_dataset, df, {"name": "p", "op": "per", "num": "a", "den": "b"})
    assert out["p"].iloc[0] == 25.0
    assert isnull(out["p"].iloc[1]) and isnull(out["p"].iloc[2])  # 分母 0、分子欠損
    assert numbers[1][0]["inputs"] == {"a": 100.0, "b": 4.0}


def test_fmt_adds_text_column(make_dataset) -> None:
    df = pd.DataFrame({"a": [2_008_428_041.0, None], "b": [1.0, 1.0]})
    out, numbers = run(
        make_dataset, df, {"name": "p", "op": "per", "num": "a", "den": "b", "fmt": "sen_yen"}
    )
    assert out["p_text"].iloc[0] == "約2兆円" and out["p_text"].iloc[1] is None
    assert numbers[1][0]["display"] == "約2兆円"
    ds = make_dataset(stats=[{"name": "p", "op": "per", "num": "a", "den": "b", "fmt": "sen_yen"}])
    assert "p_text" in ds.defined_names()


def test_errors(make_dataset) -> None:
    df = pd.DataFrame({"v": [1]})
    with pytest.raises(StatError, match="未知の op 'nope'"):
        run(make_dataset, df, {"name": "x", "op": "nope"})
    with pytest.raises(StatError, match="'value' が必要"):
        run(make_dataset, df, {"name": "x", "op": "rank_in_group"})
    with pytest.raises(StatError, match="列 'zz' がありません"):
        run(make_dataset, df, {"name": "x", "op": "rank_in_group", "value": "zz"})
    with pytest.raises(StatError, match="同じ名前"):
        run(make_dataset, df, {"name": "v", "op": "rank_in_group", "value": "v"})
    with pytest.raises(StatError, match="fmt"):
        run(make_dataset, df, {"name": "x", "op": "rank_in_group", "value": "v", "fmt": "bogus"})


def test_all_ops_are_registered() -> None:
    assert set(known_stat_ops()) >= {
        "rank_in_group",
        "yoy_diff",
        "yoy_ratio",
        "share_of_total",
        "sum_by",
        "mean_by",
        "count_by",
        "series",
        "seq_in_group",
        "is_first_time",
        "per",
    }
