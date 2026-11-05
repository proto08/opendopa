import warnings

import pytest

from opendopa_pipeline.script import (
    fill,
    fillable_types,
    line_durations,
    write_script,
)


@pytest.fixture(autouse=True)
def _quiet_type_count():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # 型が1つだけの定義は、テストでは構わない
        yield


def ds(make_dataset, templates):
    groups = [{"id": "g", "label": "g", "templates": templates}]
    return make_dataset(
        template_groups=groups, decisions=[], template_select=None, fallback_rules={}
    )


def short(lines, id_="s"):
    return {"id": id_, "short": True, "lines": lines}


def test_fill_empty_hole_is_none() -> None:
    assert fill("{a}と{b}", {"a": "X", "b": 3}) == "Xと3"
    assert fill("{a}と{b}", {"a": "X", "b": None}) is None
    assert fill("{a}", {"a": "  "}) is None
    assert fill("{a}", {"a": 2.0}) == "2"


def test_required_hole_empty_drops_template_and_optional_line_is_omitted(make_dataset) -> None:
    d = ds(
        make_dataset,
        [
            {"id": "full", "lines": ["{a}です。", "{b}です。"]},
            {"id": "opt", "lines": ["{a}です。", {"text": "{b}です。", "optional": True}]},
            short(["{a}だけ。"]),
        ],
    )
    g = d.template_groups[0]
    r = write_script(d, g, {"a": "A", "b": "B"}, "k")
    assert r.script.template_id == "full" and r.script.lines == ["Aです。", "Bです。"]
    r = write_script(d, g, {"a": "A", "b": None}, "k")
    assert r.script.template_id == "opt"  # full は外れ、任意の行は省かれる
    assert r.script.lines == ["Aです。"] and r.script.omitted_empty == 1
    assert fillable_types(d, {"a": None, "b": None}) == []
    assert fillable_types(d, {"a": "A", "b": None}) == ["g"]
    r = write_script(d, g, {"a": None, "b": None}, "k")
    assert r.script is None and r.excluded == "no_template"


def test_too_long_steps_in_order(make_dataset) -> None:
    long = "あ" * 100  # 100 字 = 15.4 秒
    d = ds(
        make_dataset,
        [
            {
                "id": "std",
                "lines": [
                    long,
                    long,
                    {"text": long, "optional": True},
                    {"text": "末尾", "optional": True},
                ],
            },
            short(["短い版。"]),
        ],
    )
    g = d.template_groups[0]
    # 1. 任意の行を後ろから省く: 末尾 → 3行目の順に省かれ、必須の2行(30.8秒)でも超える
    r = write_script(d, g, {}, "k")
    assert r.script.template_id == "s"  # 2. 短い版
    assert r.script.short and r.script.lines == ["短い版。"]

    # 任意の行を省くだけで収まるとき
    d = ds(
        make_dataset,
        [
            {
                "id": "std",
                "lines": [
                    "あ" * 100,
                    "い" * 90,
                    {"text": "う" * 20, "optional": True},
                    {"text": "え" * 20, "optional": True},
                ],
            },
            short(["短い版。"]),
        ],
    )
    r = write_script(d, d.template_groups[0], {}, "k")
    assert r.script.template_id == "std" and not r.script.short
    assert r.script.dropped_optional == 2 and len(r.script.lines) == 2

    # 3. 短い版でも超える → too_long
    d = ds(
        make_dataset, [{"id": "std", "lines": [long, long, long]}, short([long, long, long], "s2")]
    )
    r = write_script(d, d.template_groups[0], {}, "k")
    assert r.script is None and r.excluded == "too_long" and "g" in r.detail


def test_first_fitting_in_definition_order_and_variants_by_hash(make_dataset) -> None:
    d = ds(
        make_dataset,
        [
            {"id": "needs_b", "lines": ["{a}{b}"]},
            {"id": "v1", "lines": ["{a}一"]},
            {"id": "v2", "lines": ["{a}二"]},
            {"id": "other_holes", "lines": ["{a}{c}"]},
            short(["{a}"]),
        ],
    )
    g = d.template_groups[0]
    row = {"a": "A", "b": None, "c": "C"}
    chosen = {write_script(d, g, row, f"k{i}").script.template_id for i in range(40)}
    assert chosen == {"v1", "v2"}  # needs_b は外れる。同じ穴の v1 と v2 だけがハッシュで選ばれる
    assert write_script(d, g, row, "k7") == write_script(d, g, row, "k7")  # 同じ key なら同じ


def test_short_row_extends_last_line_to_15_seconds() -> None:
    durations, total = line_durations(["あ" * 13, "い" * 13])  # 4 秒
    assert total == 15.0
    assert durations[0] == 2.0 and abs(sum(durations) - 15.0) < 1e-9
    d2, t2 = line_durations(["あ" * 195])
    assert t2 == 30.0 and d2 == [30.0]
    d3, t3 = line_durations(["あ" * 100, "い" * 50])  # 23.08 秒
    assert t3 == 23.08 and abs(sum(d3) - t3) < 1e-9
