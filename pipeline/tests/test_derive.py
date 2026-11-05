from pathlib import Path

import pandas as pd
import pytest

from opendopa_pipeline.derive import (
    DeriveError,
    derive,
    derive_op,
    extract_pref,
    known_derive_ops,
    sentences,
    strip_parenthesis,
)
from opendopa_pipeline.ingest import load_frame


def run(make_dataset, col: pd.Series, **d) -> pd.Series:
    ds = make_dataset(derived={"out": {"from": "c", **d}})
    return derive(pd.DataFrame({"c": col}), ds)["out"]


def test_format_datetime(make_dataset) -> None:
    s = run(
        make_dataset,
        pd.Series(["2022/12/6 11:20", "2022/12/6 11:00", None]),
        op="format_datetime",
        fmt="ymdhm",
    )
    assert list(s) == ["2022年12月6日11時20分", "2022年12月6日11時", None]


def test_strip_parenthesis(make_dataset) -> None:
    assert strip_parenthesis("東京都（羽田空港）付近") == "東京都付近"
    assert strip_parenthesis("A(B(C))D") == "AD"
    s = run(make_dataset, pd.Series(["埼玉県さいたま市(北区)", None]), op="strip_parenthesis")
    assert list(s) == ["埼玉県さいたま市", None]


def test_extract_pref(make_dataset) -> None:
    assert extract_pref("北海道札幌市") == "北海道"
    assert extract_pref("神奈川県横浜市") == "神奈川県"
    assert extract_pref("京都府京都市") == "京都府"
    assert extract_pref("海外(アメリカ合衆国)で発生") is None
    assert extract_pref("横浜市神奈川県") is None  # 先頭だけ見る


def test_classify(make_dataset) -> None:
    rules = [{"contains": "事故に該当", "value": "事故"}, {"else": "重大インシデント"}]
    s = run(make_dataset, pd.Series(["事故に該当する", "その他", None]), op="classify", rules=rules)
    assert list(s) == ["事故", "重大インシデント", "重大インシデント"]
    with pytest.raises(DeriveError, match="else"):
        run(make_dataset, pd.Series(["a"]), op="classify", rules=[{"contains": "a", "value": 1}])


def test_sentence_keeps_original_text(make_dataset) -> None:
    text = "機体が落下した。操縦者は無事だった！「原因は調査中。」"
    assert sentences(text) == ["機体が落下した。", "操縦者は無事だった！", "「原因は調査中。」"]
    s2 = run(make_dataset, pd.Series([text, "一文のみ", None]), op="sentence", n=2)
    assert list(s2) == ["操縦者は無事だった！", None, None]
    s1 = run(make_dataset, pd.Series(["一文のみ"]), op="sentence", n=1)
    assert list(s1) == ["一文のみ"]
    with pytest.raises(DeriveError, match="n"):
        run(make_dataset, pd.Series(["a"]), op="sentence", n=0)


def test_map_with_else(make_dataset) -> None:
    s = run(
        make_dataset,
        pd.Series(["なし", "右手を負傷", None]),
        op="map",
        map={"なし": "報告にありません。"},
        **{"else": "報告があります。"},
    )
    assert list(s) == ["報告にありません。", "報告があります。", None]


def test_format(make_dataset) -> None:
    s = run(make_dataset, pd.Series([2_008_428_041, 5, None]), op="format", fmt="sen_yen")
    assert list(s) == ["約2兆円", "5,000円", None]
    with pytest.raises(DeriveError, match="fmt"):
        run(make_dataset, pd.Series([1]), op="format", fmt="bogus")


def test_unknown_op_is_error(make_dataset) -> None:
    with pytest.raises(DeriveError, match="未知の op 'nope'"):
        run(make_dataset, pd.Series(["a"]), op="nope")


def test_missing_column_and_collision(make_dataset) -> None:
    ds = make_dataset(derived={"out": {"from": "zzz", "op": "strip_parenthesis"}})
    with pytest.raises(DeriveError, match="zzz"):
        derive(pd.DataFrame({"c": ["a"]}), ds)
    ds = make_dataset(derived={"c": {"from": "c", "op": "strip_parenthesis"}})
    with pytest.raises(DeriveError, match="同じ名前"):
        derive(pd.DataFrame({"c": ["a"]}), ds)


def test_registry_is_extensible(make_dataset) -> None:
    @derive_op("test_upper")
    def _upper(col: pd.Series, d) -> pd.Series:
        return col.str.upper()

    assert "test_upper" in known_derive_ops()
    assert list(run(make_dataset, pd.Series(["a"]), op="test_upper")) == ["A"]


def test_derive_does_not_change_input(make_dataset) -> None:
    df = pd.DataFrame({"c": ["a(b)"]})
    before = df.copy(deep=True)
    derive(df, make_dataset(derived={"out": {"from": "c", "op": "strip_parenthesis"}}))
    pd.testing.assert_frame_equal(df, before)


ACCIDENT = Path(__file__).parents[2] / "data" / "raw" / "accident" / "02_jikojyouhou.csv"


@pytest.mark.skipif(not ACCIDENT.exists(), reason="data/raw/accident がない")
def test_accident_extract_pref_null_count(make_dataset) -> None:
    df = load_frame(make_dataset(files=[str(ACCIDENT)], null_values=["", "不明"]))
    pref = derive(
        df, make_dataset(derived={"pref": {"from": "OCCURRENCE_LOCATION", "op": "extract_pref"}})
    )["pref"]
    assert len(df) == 194
    assert pref.isna().sum() == 3
