import json
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from opendopa_pipeline.decider import (
    Decision,
    DecisionEngine,
    Option,
    create_decider,
    provider_name_from_env,
    register,
)
from opendopa_pipeline.spec import DatasetDef, DatasetError, load_dataset

EXAMPLE = Path(__file__).parents[2] / "datasets" / "_example.yaml"
ALL = ["injury", "loss_of_control", "object_damage", "other"]


def make_dataset(tmp_path: Path, mutate=None) -> DatasetDef:
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["decisions"] = [
        {
            "id": "template",
            "kind": "choice",
            "question": "どの型ですか。",
            "state": ["CASUALTIES_SUMMARY", "INCIDENT_SUMMARY"],
            "options_from": "template_groups",
            "min_confidence": 0.55,
            "fallback": {"rule": "keyword", "default": "other"},
        },
        {
            "id": "pii",
            "kind": "noul",
            "question": "個人を特定できる記述がありますか。",
            "state": ["INCIDENT_SUMMARY"],
            "exclude_if_probability_above": 0.5,
            "fallback": {"rule": "regex_pii"},
        },
    ]
    data["fallback_rules"] = {
        "keyword": [
            {"if": "CASUALTIES_SUMMARY != 'なし'", "then": "injury"},
            {"if": "contains(INCIDENT_SUMMARY, ['不能'])", "then": "loss_of_control"},
            {"else": "other"},
        ]
    }
    if mutate:
        mutate(data)
    p = tmp_path / "ds.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return load_dataset(p)


def row(casualties="なし", summary="特になし", **extra) -> dict[str, Any]:
    return {"CASUALTIES_SUMMARY": casualties, "INCIDENT_SUMMARY": summary, "SECRET": "x", **extra}


def all_types(_row) -> list[str]:
    return ALL


class Mock:
    """呼び出しを数え、渡された state を記録するモック。"""

    def __init__(self, name="mock", *, choice="injury", confidence=0.9, probability=0.1, fail=None):
        self.name = name
        self.calls: list[dict[str, Any]] = []
        self.choice, self.confidence, self.probability, self.fail = (
            choice,
            confidence,
            probability,
            fail,
        )

    def decide(self, kind, state, question, options=None, rubric=None) -> Decision:
        self.calls.append({"kind": kind, "state": state, "options": options})
        if self.fail == "error":
            raise RuntimeError("boom")
        if self.fail == "slow":
            time.sleep(1)
        if kind == "noul":
            return Decision(self.confidence, self.name, probability=self.probability)
        return Decision(self.confidence, self.name, choice=self.choice, distribution={})


def engine(ds, decider, tmp_path, **kw) -> DecisionEngine:
    return DecisionEngine(ds, decider, cache_path=tmp_path / "decisions.cache.jsonl", **kw)


@pytest.mark.parametrize(
    ("r", "expected"),
    [
        (row(casualties="軽傷1名"), "injury"),
        (row(summary="操縦不能となった"), "loss_of_control"),
        (row(), "other"),
    ],
)
def test_rules_provider_picks_by_fallback_rules(tmp_path: Path, r, expected) -> None:
    ds = make_dataset(tmp_path)
    out = engine(ds, create_decider("rules", ds), tmp_path).run_row(r, all_types)
    rec = out["template"]
    assert rec["choice"] == expected
    assert rec["provider"] == "rules"
    assert rec["used_fallback"] is False  # rules 自体はフォールバックに数えない
    assert rec["confidence"] == 1.0


def test_rules_provider_regex_pii(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    e = engine(ds, create_decider("rules", ds), tmp_path)
    texts = ["連絡先は03-1234-5678です", "a@example.com まで", "港区3丁目", "東京都1番2号", "なし"]
    out = e.run([row(summary=t) for t in texts], all_types)
    assert [o["pii"]["excluded"] for o in out] == [True, True, True, True, False]
    assert all(o["pii"]["used_fallback"] is False for o in out)


def test_options_only_fillable_types(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    m = Mock()
    engine(ds, m, tmp_path).run_row(row(), lambda _r: ["other", "injury"])
    # 定義順で、埋められる型だけ
    assert m.calls[0]["options"] == [
        Option("injury", "人が負傷した"),
        Option("other", "上のどれでもない"),
    ]


def test_rules_never_picks_unfillable_type(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    out = engine(ds, create_decider("rules", ds), tmp_path).run_row(
        row(casualties="重傷"), lambda _r: ["other"]
    )
    assert out["template"]["choice"] == "other"


@pytest.mark.parametrize(
    "kw",
    [{"confidence": 0.3}, {"fail": "error"}, {"fail": "slow", "timeout": 0.05}],
    ids=["low-confidence", "error", "timeout"],
)
def test_fallback(tmp_path: Path, kw) -> None:
    ds = make_dataset(tmp_path)
    timeout = kw.pop("timeout", 30.0)
    out = engine(ds, Mock(**kw), tmp_path, timeout=timeout).run_row(
        row(casualties="重傷"), all_types
    )
    rec = out["template"]
    assert rec["used_fallback"] is True
    assert rec["choice"] == "injury"  # fallback_rules どおり
    assert rec["provider"] == "rules"


def test_invalid_choice_falls_back(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    out = engine(ds, Mock(choice="nonexistent"), tmp_path).run_row(row(), all_types)
    assert out["template"]["used_fallback"] is True
    assert out["template"]["choice"] == "other"


def test_noul_fallback_is_safe_side(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    e = engine(ds, Mock(fail="error"), tmp_path)
    out = e.run([row(summary="03-1234-5678"), row()], all_types)
    assert [o["pii"]["excluded"] for o in out] == [True, False]
    assert all(o["pii"]["used_fallback"] for o in out)


def test_second_run_uses_cache(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    m = Mock()
    engine(ds, m, tmp_path).run([row(), row(summary="別")], all_types)
    n = len(m.calls)
    assert n == 4  # 2行 x 2判断
    again = engine(ds, m, tmp_path).run([row(), row(summary="別")], all_types)
    assert len(m.calls) == n
    assert again[0]["template"]["choice"] == "injury"
    assert (tmp_path / "decisions.cache.jsonl").exists()


def test_same_input_in_one_run_is_called_once(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    m = Mock()
    engine(ds, m, tmp_path).run([row(), row(), row()], all_types)
    assert len(m.calls) == 2  # 判断2つ x 1回


def test_failures_are_not_cached(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    engine(ds, Mock(fail="error"), tmp_path).run_row(row(), all_types)
    m = Mock()
    out = engine(ds, m, tmp_path).run_row(row(), all_types)
    assert len(m.calls) == 2
    assert out["template"]["used_fallback"] is False


def test_cache_key_depends_on_provider(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    a, b = Mock("a"), Mock("b")
    engine(ds, a, tmp_path).run_row(row(), all_types)
    engine(ds, b, tmp_path).run_row(row(), all_types)
    assert len(b.calls) == 2


def test_only_state_columns_reach_provider(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    m = Mock()
    engine(ds, m, tmp_path).run_row(row(), all_types)
    by_kind = {c["kind"]: c["state"] for c in m.calls}
    assert set(by_kind["choice"]) == {"CASUALTIES_SUMMARY", "INCIDENT_SUMMARY"}
    assert set(by_kind["noul"]) == {"INCIDENT_SUMMARY"}


def test_register_new_provider_without_engine_change(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    m = Mock("custom", choice="loss_of_control")
    register("custom", lambda _ds: m)
    decider = create_decider("custom", ds)
    out = engine(ds, decider, tmp_path).run_row(row(), all_types)
    assert out["template"]["choice"] == "loss_of_control"
    assert out["template"]["provider"] == "custom"


def test_batch_is_used_when_provider_has_it(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)

    class Batch(Mock):
        batches = 0

        def decide_batch(self, reqs):
            Batch.batches += 1
            return [self.decide(r.kind, r.state, r.question, r.options) for r in reqs]

    engine(ds, Batch(), tmp_path).run([row(summary=str(i)) for i in range(3)], all_types)
    assert Batch.batches == 2  # 判断ごとに1回


def test_report_and_record_shape(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    e = engine(ds, Mock(fail="error"), tmp_path)
    out = e.run([row(), row()], all_types)
    json.dumps(out)  # jsonb に入れられる
    assert {"id", "kind", "choice", "distribution", "confidence", "provider", "used_fallback"} <= (
        out[0]["template"].keys()
    )
    path = tmp_path / "out" / "ds" / "decisions_report.json"
    e.write_report(path)
    rep = json.loads(path.read_text(encoding="utf-8"))
    assert rep["fallback_rate"] == 1.0
    assert rep["decisions"]["template"] == {"total": 2, "fallback": 2, "fallback_rate": 1.0}


def test_rules_report_has_zero_fallback(tmp_path: Path) -> None:
    ds = make_dataset(tmp_path)
    e = engine(ds, create_decider("rules", ds), tmp_path)
    e.run([row(), row()], all_types)
    assert e.report()["fallback_rate"] == 0.0


def test_fallback_rule_must_use_state_columns(tmp_path: Path) -> None:
    def mutate(d: dict) -> None:
        d["decisions"][0]["state"] = ["INCIDENT_SUMMARY"]

    ds = make_dataset(tmp_path, mutate)
    with pytest.raises(DatasetError, match="CASUALTIES_SUMMARY"):
        engine(ds, Mock(), tmp_path)


def test_provider_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DECIDER_PROVIDER", raising=False)
    assert provider_name_from_env() == "rules"
    monkeypatch.setenv("DECIDER_PROVIDER", "strands_azure")
    assert provider_name_from_env() == "strands_azure"


def test_unknown_provider_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="strands_azure"):
        create_decider("strands_azure", make_dataset(tmp_path))
