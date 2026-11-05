import pandas as pd
import pytest

from opendopa_pipeline.clean import apply_filters, write_excluded
from opendopa_pipeline.ingest import IngestError, load_frame, register_loader, row_dict

CSV = "No.,SUMMARY,AMOUNT,CODE,OLD\n1,概要A,100,01100,x\n2,,0,02200,不明\n3,概要C,300,03300,y\n"


def write_csv(tmp_path, text=CSV, name="a.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8-sig")  # BOM 付き
    return p


def test_load_bom_rename_null_zero(tmp_path, make_dataset) -> None:
    write_csv(tmp_path)
    d = make_dataset(
        files=["a.csv"],
        rename={"OLD": "NEW"},
        null_values=["", "不明"],
        zero_is_null=["AMOUNT"],
    )
    df = load_frame(d, tmp_path)
    assert list(df.columns) == ["No.", "SUMMARY", "AMOUNT", "CODE", "NEW"]  # BOM が列名に残らない
    assert list(df.index) == [1, 2, 3]
    assert df.loc[2, "SUMMARY"] is None  # null_values
    assert df.loc[3, "NEW"] == "y" and df.loc[2, "NEW"] is None
    assert pd.isna(df.loc[2, "AMOUNT"]) and df.loc[1, "AMOUNT"] == 100  # zero_is_null、数値化
    assert df.loc[1, "CODE"] == "01100"  # 先頭 0 の符号は文字列のまま
    assert row_dict(df.loc[1])["No."] == 1


def test_zero_is_null_unknown_column(tmp_path, make_dataset) -> None:
    write_csv(tmp_path)
    with pytest.raises(IngestError, match="NOPE"):
        load_frame(make_dataset(files=["a.csv"], zero_is_null=["NOPE"]), tmp_path)


def test_missing_file_and_loader(tmp_path, make_dataset) -> None:
    with pytest.raises(IngestError, match="ファイルがありません"):
        load_frame(make_dataset(files=["nope.csv"]), tmp_path)
    (tmp_path / "x.geojson").write_text("{}")
    with pytest.raises(IngestError, match="ローダがありません"):
        load_frame(make_dataset(files=["x.geojson"]), tmp_path)


def test_register_loader(tmp_path, make_dataset) -> None:
    (tmp_path / "x.tsv").write_text("a\tb\n1\t2\n")
    register_loader(".tsv", lambda p: pd.read_csv(p, sep="\t", dtype=str, keep_default_na=False))
    df = load_frame(make_dataset(files=["x.tsv"], null_values=[]), tmp_path)
    assert list(df["b"]) == [2]


def test_multiple_files_are_concatenated(tmp_path, make_dataset) -> None:
    write_csv(tmp_path, "a,b\n1,2\n", "1.csv")
    write_csv(tmp_path, "a,b\n3,4\n", "2.csv")
    df = load_frame(make_dataset(files=["1.csv", "2.csv"]), tmp_path)
    assert list(df["a"]) == [1, 3] and list(df.index) == [1, 2]


def test_filters_record_excluded_and_keep_original(tmp_path, make_dataset) -> None:
    write_csv(tmp_path)
    d = make_dataset(
        files=["a.csv"],
        null_values=[""],
        zero_is_null=["AMOUNT"],
        filters=[{"col": "SUMMARY", "not_null": True}, "AMOUNT > 100"],
    )
    df = load_frame(d, tmp_path)
    before = df.copy(deep=True)

    kept, excluded = apply_filters(df, d)

    pd.testing.assert_frame_equal(df, before)  # 元の DataFrame は変わらない
    assert list(kept.index) == [3]  # 行 2 は SUMMARY 欠損、行 1 は AMOUNT > 100 を満たさない
    assert [(e.row_id, e.reason) for e in excluded] == [
        (2, "SUMMARY が欠損"),
        (1, "filters を満たさない: AMOUNT > 100"),
    ]

    out = tmp_path / "out" / "example" / "excluded.csv"
    write_excluded(out, excluded)
    assert out.read_text(encoding="utf-8").splitlines() == [
        "row_id,reason",
        "2,SUMMARY が欠損",
        "1,filters を満たさない: AMOUNT > 100",
    ]


def test_write_excluded_empty_has_header(tmp_path) -> None:
    out = tmp_path / "excluded.csv"
    write_excluded(out, [])
    assert out.read_text(encoding="utf-8").strip() == "row_id,reason"
