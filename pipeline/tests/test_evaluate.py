import csv
from pathlib import Path

import pytest

from opendopa_pipeline.decider import Decision, register
from opendopa_pipeline.decider.evaluate import (
    EvalError,
    draft_labels,
    evaluate,
    load_labels,
    write_labels,
)
from opendopa_pipeline.spec import load_dataset

YAML = Path(__file__).parents[2] / "datasets" / "accident.yaml"
DS = load_dataset(YAML)

TEXTS = {
    "injury": "操縦者が負傷した。",
    "loss_of_control": "制御不能となり墜落した。",
    "object_damage": "建物の壁に接触した。",
    "other": "機体が落下した。",
}


def make_rows(n_per: dict[str, int]) -> list[dict]:
    rows, no = [], 0
    for t, n in n_per.items():
        for _ in range(n):
            no += 1
            rows.append(
                {
                    "No.": no,
                    "INCIDENT_SUMMARY": TEXTS[t],
                    "casualty_sentence": "負傷者の報告はありません。",
                    "date": "2022年12月6日",
                    "place": "東京都",
                    "summary_1": TEXTS[t],
                }
            )
    return rows


def write_csv(path: Path, recs: list[tuple[str, str]]) -> Path:
    write_labels(path, recs)
    return path


def test_agreement_three_of_four(tmp_path):
    rows = make_rows({"injury": 1, "loss_of_control": 1, "object_damage": 1, "other": 1})
    # rules の答えは 1:injury 2:loss_of_control 3:object_damage 4:other。4 を間違いにする
    labels = {"1": "injury", "2": "loss_of_control", "3": "object_damage", "4": "injury"}
    [r] = evaluate(DS, rows, labels, ["rules"])
    assert (r.total, r.agree, r.fallback) == (4, 3, 0)
    assert r.agreement == 0.75
    assert r.sec_per_question >= 0


def test_fallback_counted(tmp_path):
    class Bad:
        name = "bad_eval"

        def decide(self, kind, state, question, options=None, rubric=None):
            return Decision(confidence=0.1, provider=self.name, choice="injury")

    register("bad_eval", lambda ds: Bad())
    rows = make_rows({"object_damage": 2})
    labels = {"1": "object_damage", "2": "object_damage"}
    [r] = evaluate(DS, rows, labels, ["bad_eval"])
    assert r.fallback == 2  # 確信度が低いので rules に落ちる
    assert r.agree == 2


def test_unknown_provider_is_error():
    with pytest.raises(EvalError):
        evaluate(DS, make_rows({"other": 1}), {"1": "other"}, ["nope"])


def test_load_labels_errors(tmp_path):
    rows = make_rows({"other": 2})
    ok = write_csv(tmp_path / "ok.csv", [("1", "other"), ("2", "injury")])
    assert load_labels(ok, DS, rows) == {"1": "other", "2": "injury"}
    with pytest.raises(EvalError, match="データにありません"):
        load_labels(write_csv(tmp_path / "a.csv", [("99", "other")]), DS, rows)
    with pytest.raises(EvalError, match="不正"):
        load_labels(write_csv(tmp_path / "b.csv", [("1", "bogus")]), DS, rows)
    with pytest.raises(EvalError, match="重複"):
        load_labels(write_csv(tmp_path / "c.csv", [("1", "other"), ("1", "other")]), DS, rows)
    with pytest.raises(EvalError, match="ありません"):
        load_labels(tmp_path / "missing.csv", DS, rows)
    bad = tmp_path / "d.csv"
    bad.write_text("x,y\n1,2\n", encoding="utf-8")
    with pytest.raises(EvalError, match="列"):
        load_labels(bad, DS, rows)


def test_draft_is_deterministic_and_stratified(tmp_path):
    rows = make_rows({"injury": 5, "loss_of_control": 5, "object_damage": 60, "other": 30})
    a = draft_labels(DS, rows)
    assert a == draft_labels(DS, list(reversed(rows)))
    assert len(a) == 50
    types = [t for _, t in a]
    # 少ない型も入る(各型 5 行は全部入り、残りを多い型で埋める)
    assert types.count("injury") == 5 and types.count("loss_of_control") == 5
    assert [int(n) for n, _ in a] == sorted(int(n) for n, _ in a)
    out = tmp_path / "labels.csv"
    write_labels(out, a)
    assert next(csv.reader(out.open(encoding="utf-8"))) == ["No.", "template"]


def test_draft_with_fewer_rows_than_size():
    assert len(draft_labels(DS, make_rows({"other": 3}))) == 3
