import warnings
from pathlib import Path

import pytest
import yaml

from opendopa_pipeline.spec import DatasetError, load_dataset, validate_against_columns

EXAMPLE = Path(__file__).parents[2] / "datasets" / "_example.yaml"
COLUMNS = ["No.", "SUMMARY", "LOCATION", "OCCURRENCE_DATE", "REMARKS"]


def write(tmp_path: Path, mutate) -> Path:
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    mutate(data)
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_example_loads_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        d = load_dataset(EXAMPLE, columns=COLUMNS)
    assert d.id == "example"
    assert d.grain == "row"
    assert [g.id for g in d.template_groups][0] == "injury"
    lines = d.template_groups[0].templates[0].lines
    assert [(x.text, x.optional) for x in lines][-1] == ("{REMARKS}", True)
    assert lines[0].optional is False


def test_undefined_hole_is_reported_with_path_type_and_line(tmp_path: Path) -> None:
    def mutate(d: dict) -> None:
        d["template_groups"][0]["templates"][0]["lines"][1] = "{foo}"

    p = write(tmp_path, mutate)
    d = load_dataset(p)  # 列名はデータを読むまで分からないので、ここでは通る
    with pytest.raises(DatasetError) as e:
        validate_against_columns(d, COLUMNS)
    msg = str(e.value)
    assert str(p) in msg and "injury" in msg and "2行目" in msg and "{foo}" in msg
    with pytest.raises(DatasetError, match=r"\{foo\}"):
        load_dataset(p, columns=COLUMNS)


def test_hole_may_use_derived_and_stats_names() -> None:
    # {place}(derived)と {place_seq}(stats)は、列になくても通る
    validate_against_columns(load_dataset(EXAMPLE), ["No.", "SUMMARY", "LOCATION", "REMARKS"])
    d = load_dataset(EXAMPLE)
    with pytest.raises(DatasetError, match="LOCATION"):
        validate_against_columns(d, ["No.", "SUMMARY", "REMARKS"])


def test_expr_with_unknown_column_is_reported() -> None:
    d = load_dataset(EXAMPLE)
    with pytest.raises(DatasetError, match="fallback_rules.keyword"):
        validate_against_columns(d, ["No.", "LOCATION", "REMARKS"])  # SUMMARY がない


def test_type_without_short_template_fails(tmp_path: Path) -> None:
    def mutate(d: dict) -> None:
        d["template_groups"][0]["templates"][1]["short"] = False

    with pytest.raises(DatasetError, match="short: true"):
        load_dataset(write(tmp_path, mutate))


def test_invalid_grain_fails(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="grain"):
        load_dataset(write(tmp_path, lambda d: d.update(grain="table")))


def test_missing_required_key_fails(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="embed_text"):
        load_dataset(write(tmp_path, lambda d: d.pop("embed_text")))


def test_unknown_key_fails(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="typo_key"):
        load_dataset(write(tmp_path, lambda d: d.update(typo_key=1)))


def test_bad_expression_fails_at_load(tmp_path: Path) -> None:
    def mutate(d: dict) -> None:
        d["big_number"]["primary"]["when"] = "__import__('os')"

    with pytest.raises(DatasetError, match="big_number.primary.when"):
        load_dataset(write(tmp_path, mutate))


def test_fallback_rule_must_point_to_existing_type(tmp_path: Path) -> None:
    def mutate(d: dict) -> None:
        d["fallback_rules"]["keyword"][-1] = {"else": "nothing"}

    with pytest.raises(DatasetError, match="nothing"):
        load_dataset(write(tmp_path, mutate))


@pytest.mark.parametrize("keep", [3, 7])
def test_type_count_outside_4_to_6_warns(tmp_path: Path, keep: int) -> None:
    def mutate(d: dict) -> None:
        groups = d["template_groups"]
        i = 0
        while len(groups) < keep:
            copy = yaml.safe_load(yaml.safe_dump(groups[0]))
            i += 1
            copy["id"] = f"extra{i}"
            for t in copy["templates"]:
                t["id"] = f"{t['id']}_{i}"
            groups.append(copy)
        del groups[keep:]
        d["fallback_rules"]["keyword"] = [{"else": "injury"}]

    with pytest.warns(UserWarning, match="型の数"):
        load_dataset(write(tmp_path, mutate))


def test_invalid_yaml_and_missing_file(tmp_path: Path) -> None:
    p = tmp_path / "x.yaml"
    p.write_text("a: [", encoding="utf-8")
    with pytest.raises(DatasetError, match="YAML"):
        load_dataset(p)
    with pytest.raises(DatasetError, match="読み込めません"):
        load_dataset(tmp_path / "none.yaml")
