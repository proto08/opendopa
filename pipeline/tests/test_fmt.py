import pytest

from opendopa_pipeline.fmt import (
    format_count,
    format_datetime,
    format_decimal,
    format_percent,
    format_rank,
    format_sen_yen,
    format_value,
    format_yen,
    parse_yen,
)


def test_sen_yen_to_cho() -> None:
    # 2,008,428,041 千円は、「約2兆84億円」ではなく「約2兆円」
    assert format_sen_yen(2_008_428_041) == "約2兆円"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12_340_000, "1,234万円"),
        (9_999, "9,999円"),
        (0, "0円"),
        (10_000, "1万円"),
        (150_000_000, "1.5億円"),
        (-12_340_000, "マイナス1,234万円"),
        # 1桁の丸めでは誤差が 0.5% を超えるので、下の単位まで書く
        (104_000_000, "1億400万円"),
        (10_400, "1万400円"),
        (1_040_000_000_000, "1兆400億円"),
        (1_004_000_000_000, "約1兆円"),
        # 丸めて次の単位に繰り上がる
        (99_999_999, "約1億円"),
    ],
)
def test_format_yen(value: int, expected: str) -> None:
    assert format_yen(value) == expected


def test_format_yen_rounded_has_yaku() -> None:
    assert format_yen(12_345_678) == "約1,234.6万円"
    assert format_yen(None) is None


@pytest.mark.parametrize(
    "yen",
    [
        1,
        9_999,
        10_001,
        10_400,
        12_345_678,
        99_999_999,
        104_000_000,
        1_234_567_890,
        2_008_428_041_000,
    ]
    + [10**k * m for k in range(4, 13) for m in (1, 12, 104, 999, 1004)],
)
def test_format_yen_error_within_half_percent(yen: int) -> None:
    text = format_yen(yen)
    assert abs(parse_yen(text) - yen) / yen <= 0.005, text
    # 約 が付かないのは、元の値と一致するときだけ
    assert text.startswith("約") == (parse_yen(text) != yen)


def test_datetime() -> None:
    assert format_datetime("2022/12/6 11:20") == "2022年12月6日11時20分"
    assert format_datetime("2022/12/6 11:00") == "2022年12月6日11時"
    assert format_datetime("2022/12/6 0:00") == "2022年12月6日0時"
    assert format_datetime("1980/3/1") == "1980年3月1日"
    assert format_datetime("2022/12/6 11:20", "ymd") == "2022年12月6日"
    assert format_datetime("不明") is None
    assert format_datetime("2022/13/40") is None
    with pytest.raises(ValueError):
        format_datetime("2022/12/6", "bogus")


def test_percent_rank_count() -> None:
    assert format_percent(12.3456) == "12.3%"
    assert format_percent(12.0) == "12%"
    assert format_percent(0.05) == "0.1%"
    assert format_percent(-3.25) == "-3.3%"
    assert format_rank(3) == "3位"
    assert format_rank(3.0) == "3位"
    assert format_count(1234) == "1,234件"


def test_format_value() -> None:
    assert format_value("percent", 12.3456) == "12.3%"
    assert format_value("rank", float("nan")) is None
    with pytest.raises(ValueError):
        format_value("bogus", 1)


def test_decimal() -> None:
    assert format_decimal(3.456) == "3.5"
    assert format_decimal(12.0) == "12"
    assert format_decimal(1234.5) == "1,234.5"
    assert format_decimal(None) is None
    assert format_value("decimal", 4.84) == "4.8"


@pytest.mark.parametrize(
    "sen_yen",
    [285_711_829, 38_916_061, 6_938_290, 2_008_428_041, 663_251_400, 104_000, 12_345, 1_040_000_000]
    + [10**k * m for k in range(1, 10) for m in (1, 12, 104, 999, 1004)],
)
def test_format_sen_yen_error_within_half_percent(sen_yen: int) -> None:
    """千円の列(営業損益・営業収益など)を億円・兆円にしても、元の値から 0.5% 以内。"""
    text = format_sen_yen(sen_yen)
    assert abs(parse_yen(text) - sen_yen * 1000) / (sen_yen * 1000) <= 0.005, text


def test_format_sen_yen_units() -> None:
    assert format_sen_yen(285_711_829) == "約2,857.1億円"
    assert format_sen_yen(38_916_061) == "約389.2億円"
    assert format_sen_yen(-6_938_290) == "マイナス約69.4億円"
