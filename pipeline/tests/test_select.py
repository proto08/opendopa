import pandas as pd
import pytest

from opendopa_pipeline.select import SelectError, select_rows


def frame(n: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pref": ["A", "A", "A", "A", "B", "B", "C", "C", "C", "C", "C", None][:n],
            "amount": [10, 50, 30, 20, 40, 60, 5, 15, 25, 35, 45, None][:n],
            "x": [-9, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11][:n],
        },
        index=pd.RangeIndex(1, n + 1, name="row_id"),
    )


def test_cap_and_default_order(make_dataset) -> None:
    d = make_dataset(select={"cap": 3})
    assert select_rows(frame(), d) == [1, 2, 3]


def test_rank_desc_and_abs_weighted_score(make_dataset) -> None:
    d = make_dataset(
        select={"cap": 3, "score": [{"expr": "rank_desc(amount)", "weight": 1.0}]},
    )
    assert select_rows(frame(), d) == [6, 2, 11]  # 60, 50, 45
    d = make_dataset(select={"cap": 2, "score": [{"expr": "abs(x)", "weight": 1.0}]})
    assert select_rows(frame(), d) == [12, 11]  # 11, 10
    d = make_dataset(select={"cap": 1, "score": [{"expr": "abs(x)"}, {"expr": "x", "weight": -1}]})
    assert select_rows(frame(), d) == [1]  # |-9| - (-9) = 18


def test_ties_use_order_by_then_row_order(make_dataset) -> None:
    df = frame()
    df["flat"] = 1
    d = make_dataset(select={"cap": 3, "score": [{"expr": "flat"}], "order_by": "x"})
    assert select_rows(df, d) == [1, 2, 3]
    d = make_dataset(select={"cap": 2, "score": [{"expr": "flat"}]})
    assert select_rows(df, d) == [1, 2]


def test_diversify_round_robin(make_dataset) -> None:
    d = make_dataset(
        select={
            "cap": 6,
            "score": [{"expr": "amount"}],
            "diversify_by": ["pref"],
        }
    )
    # グループは最高点の順: B(60) → A(50) → C(45) → 欠損(0)。1周目は各グループの最高点、2周目は次点
    assert select_rows(frame(), d) == [6, 2, 11, 12, 5, 3]
    d = make_dataset(select={"cap": 3, "diversify_by": "pref", "score": [{"expr": "amount"}]})
    assert select_rows(frame(), d) == [6, 2, 11]


def test_seed_is_reproducible_and_differs_by_seed(make_dataset) -> None:
    def pick(seed: int) -> list:
        return select_rows(frame(), make_dataset(select={"cap": 5, "seed": seed}))

    assert pick(42) == pick(42)
    assert len(set(pick(42))) == 5
    assert any(pick(s) != pick(42) for s in range(1, 6))


def test_filters_before_scoring(make_dataset) -> None:
    d = make_dataset(
        select={
            "cap": 2,
            "filters": [{"col": "amount", "not_null": True}, "x > 3"],
            "score": [{"expr": "amount"}],
        }
    )
    assert select_rows(frame(), d) == [6, 11]


def test_default_cap_is_150(make_dataset) -> None:
    df = pd.DataFrame({"v": range(200)}, index=pd.RangeIndex(1, 201, name="row_id"))
    assert len(select_rows(df, make_dataset(select={}))) == 150


def test_unknown_column_and_bad_expr(make_dataset) -> None:
    with pytest.raises(SelectError):
        select_rows(frame(), make_dataset(select={"score": [{"expr": "nope"}]}))
    with pytest.raises(SelectError):
        select_rows(frame(), make_dataset(select={"score": [{"expr": "amount * 2"}]}))
    with pytest.raises(SelectError):
        select_rows(frame(), make_dataset(select={"diversify_by": ["nope"]}))
