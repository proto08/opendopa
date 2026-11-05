import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from opendopa_pipeline.cli import REPO_ROOT, app
from opendopa_pipeline.ingest import read_csv
from opendopa_pipeline.profile import build_profile, prepare_raw

runner = CliRunner()

LONG = "あ" * 31


@pytest.fixture
def small_csv(tmp_path: Path) -> Path:
    rows = ["No,DATE,KIND,FLAG,AMOUNT,SUMMARY,LAT,LON"]
    kinds = ["A", "A", "A", "B", "B", ""]
    for i in range(1, 7):
        rows.append(
            f"{i},2024/1/{i},{kinds[i - 1]},{i % 2},{i * 1.5},{LONG if i == 3 else '短い'},"
            f"35.{i},139.{i}"
        )
    path = tmp_path / "small.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _by_name(profile: dict) -> dict:
    return {c["name"]: c for c in profile["columns"]}


def test_profile_columns(small_csv: Path) -> None:
    cols = _by_name(build_profile("small", prepare_raw(read_csv(small_csv)), [str(small_csv)]))
    assert cols["No"]["role"] == "id"
    assert cols["No"]["dtype"] == "int"
    assert cols["FLAG"]["role"] == "flag"
    assert cols["SUMMARY"]["role"] == "free_text"
    assert cols["SUMMARY"]["max_len"] == 31
    assert cols["DATE"]["role"] == "date"
    assert cols["AMOUNT"]["role"] == "number"
    assert cols["LAT"]["role"] == "coordinate"
    assert cols["LON"]["role"] == "coordinate"
    kind = cols["KIND"]
    assert kind["role"] == "category"
    assert kind["missing_rate"] == pytest.approx(1 / 6, abs=1e-4)
    assert kind["n_unique"] == 2
    assert kind["top"] == [{"value": "A", "count": 3}, {"value": "B", "count": 2}]


def test_cli_profile_file_writes_json(small_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["profile", "--file", str(small_csv), "--out-dir", str(out)])
    assert result.exit_code == 0, result.output
    assert "SUMMARY" in result.output
    data = json.loads((out / "small" / "profile.json").read_text(encoding="utf-8"))
    assert data["n_rows"] == 6
    assert [c["name"] for c in data["columns"]][0] == "No"


def test_cli_profile_requires_target() -> None:
    assert runner.invoke(app, ["profile"]).exit_code == 2


def test_cli_profile_unknown_dataset() -> None:
    assert runner.invoke(app, ["profile", "--dataset", "no_such_dataset"]).exit_code == 2


@pytest.mark.skipif(
    not (REPO_ROOT / "data/raw/accident/02_jikojyouhou.csv").exists(),
    reason="accident の CSV(data/raw/accident/)がない",
)
def test_accident_profile(tmp_path: Path) -> None:
    result = runner.invoke(app, ["profile", "--dataset", "accident", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "accident" / "profile.json").read_text(encoding="utf-8"))
    cols = _by_name(data)
    assert cols["INCIDENT_SUMMARY"]["max_len"] == 165
    assert cols["INCIDENT_SUMMARY"]["role"] == "free_text"
    assert cols["CASUALTIES_SUMMARY"]["top"][0] == {"value": "なし", "count": 165}
