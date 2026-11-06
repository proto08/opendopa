from pathlib import Path

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from opendopa_pipeline import cli
from opendopa_pipeline.draft import (
    SAMPLE_ROWS,
    build_prompt,
    check_draft,
    draft_yaml,
    schema_text,
    strip_fence,
)
from opendopa_pipeline.profile import build_profile

runner = CliRunner()

EXAMPLE = Path(__file__).parents[2] / "datasets" / "_example.yaml"

COLUMNS = ["No.", "SUMMARY", "LOCATION", "REMARKS", "OCCURRENCE_DATE"]


def good_draft(extra_line: str | None = None) -> str:
    """_example.yaml(COLUMNS の列だけで埋まる)に、任意の1行を足した下書き。"""
    doc = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    if extra_line:
        doc["template_groups"][0]["templates"][0]["lines"].append(extra_line)
    return yaml.safe_dump(doc, allow_unicode=True)


def make_df() -> pd.DataFrame:
    n = 15
    return pd.DataFrame(
        {
            "No.": range(1, n + 1),
            "SUMMARY": [f"概要{i}。" for i in range(n)],
            "LOCATION": [f"東京都{i}" for i in range(n)],
            "REMARKS": ["事故に該当"] * n,
            "OCCURRENCE_DATE": ["2024-01-01"] * n,
        }
    )


class StubLlm:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


def test_good_draft_has_no_violations() -> None:
    assert check_draft(good_draft(), COLUMNS) == []


def test_unknown_hole_is_detected() -> None:
    violations = check_draft(good_draft("{foo}"), COLUMNS)
    assert any("{foo}" in v for v in violations)


def test_derived_name_is_a_known_hole() -> None:
    raw = yaml.safe_load(good_draft("{summary_2}"))
    raw["derived"]["summary_2"] = {"from": "SUMMARY", "op": "sentence", "n": 2}
    assert check_draft(yaml.safe_dump(raw, allow_unicode=True), COLUMNS) == []


def test_invalid_yaml_is_detected() -> None:
    violations = check_draft("id: [unclosed\n  foo: : bar", COLUMNS)
    assert violations and "YAML" in violations[0]


def test_prose_instead_of_yaml_is_detected() -> None:
    assert check_draft("以下が下書きです。", COLUMNS)


def test_missing_short_is_detected() -> None:
    raw = yaml.safe_load(good_draft())
    raw["template_groups"][1]["templates"][0]["short"] = False
    violations = check_draft(yaml.safe_dump(raw, allow_unicode=True), COLUMNS)
    assert any("short" in v for v in violations)


def test_strip_fence() -> None:
    assert strip_fence("```yaml\nid: a\n```") == "id: a"
    assert strip_fence("id: a") == "id: a"


def test_prompt_contains_profile_samples_and_rules() -> None:
    df = make_df()
    system, user = build_prompt(build_profile("demo", df, ["a.csv"]), [{"LOCATION": "東京都0"}])
    assert "REMARKS" in user and "missing_rate" in user  # プロファイル
    assert '"LOCATION": "東京都0"' in user  # サンプル
    assert "推測は書かない" in system  # 禁止事項
    assert "YAML だけ" in system
    assert "free_text" in system  # 自由記述の方針
    assert "### 8.3" in system  # スキーマの説明
    assert "{{" not in system + user  # 置き換え漏れなし
    assert "<!--" not in system


def test_schema_text_is_section_8_3() -> None:
    text = schema_text()
    assert text.startswith("### 8.3 ") and "8.3a" not in text.splitlines()[0]


def test_draft_yaml_passes_samples_and_marks_violations() -> None:
    llm = StubLlm("```yaml\n" + good_draft("{foo}") + "```")
    text, violations = draft_yaml(llm, build_profile("demo", make_df(), ["a.csv"]), make_df())
    assert len(violations) == 1
    assert text.startswith("# 機械検査で 1 件の違反")
    assert "{foo}" in text.splitlines()[1]
    assert len(llm.calls[0][1].split("# サンプル 10 行")[1].strip().splitlines()) >= SAMPLE_ROWS


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    (tmp_path / "datasets").mkdir()
    raw = tmp_path / "data" / "raw" / "demo"
    raw.mkdir(parents=True)
    make_df().to_csv(raw / "a.csv", index=False)
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    return tmp_path


def test_provider_none_prints_guidance_without_calling_llm(fake_repo, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "none")
    result = runner.invoke(cli.app, ["draft-yaml", "--dataset", "demo"])
    assert result.exit_code == 1
    assert "LLM が使えません" in result.output
    assert not (fake_repo / "datasets" / "demo.draft.yaml").exists()


def test_cli_writes_draft_and_reports_violations(fake_repo, monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setattr(cli, "create_llm", lambda: StubLlm(good_draft("{foo}")))
    result = runner.invoke(cli.app, ["draft-yaml", "--dataset", "demo"])
    assert result.exit_code == 0, result.output
    assert "{foo}" in result.output
    out = fake_repo / "datasets" / "demo.draft.yaml"
    assert out.read_text(encoding="utf-8").startswith("# 機械検査で")
    # 人が直した下書きを守る
    assert runner.invoke(cli.app, ["draft-yaml", "--dataset", "demo"]).exit_code == 2
    assert runner.invoke(cli.app, ["draft-yaml", "--dataset", "demo", "--force"]).exit_code == 0
