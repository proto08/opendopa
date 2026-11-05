"""判断モデルの評価(`opendopa decide --eval` / `--draft`、設計書 §14.2b)。

人が付けた正解(`datasets/<id>.labels.csv`: 列 `No.`, `template`)との一致率、
フォールバックの割合、1問あたりの時間をプロバイダーごとに出す。
`--draft` は、`rules` の判断を下書きとして50行ぶん出す(人が `template` を直す)。
"""

from __future__ import annotations

import csv
import random
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opendopa_pipeline.decider.engine import DecisionEngine
from opendopa_pipeline.decider.registry import create_decider
from opendopa_pipeline.script import fillable_types
from opendopa_pipeline.spec import DatasetDef

ID_COLUMN = "No."
LABEL_COLUMN = "template"
DRAFT_SIZE = 50
DRAFT_SEED = 42
# 合格の目安(§14.2b): 一致率がこれ以上、かつフォールバックがこれ以下
PASS_AGREEMENT = 0.80
PASS_FALLBACK = 0.30


class EvalError(ValueError):
    """ラベルや設定の誤り。"""


@dataclass
class ProviderResult:
    provider: str
    total: int
    agree: int
    fallback: int
    seconds: float

    @property
    def agreement(self) -> float:
        return self.agree / self.total if self.total else 0.0

    @property
    def fallback_rate(self) -> float:
        return self.fallback / self.total if self.total else 0.0

    @property
    def sec_per_question(self) -> float:
        return self.seconds / self.total if self.total else 0.0


def _template_decision(dataset: DatasetDef):
    if dataset.template_select is None:
        raise EvalError(f"{dataset.id}: template_select がないので、評価できません")
    for d in dataset.decisions:
        if d.id == dataset.template_select.decision:
            return d
    raise EvalError(f"{dataset.id}: decisions に {dataset.template_select.decision!r} がありません")


def row_key(row: Mapping[str, Any]) -> str:
    """行の `No.`(ラベルの `No.` と同じ書き方の文字列)。"""
    v = row.get(ID_COLUMN)
    if v is None:
        raise EvalError(f"行に列 {ID_COLUMN!r} がありません")
    return str(v)


def load_labels(
    path: Path, dataset: DatasetDef, rows: Sequence[Mapping[str, Any]]
) -> dict[str, str]:
    """ラベルを読んで検証する。`No.` がデータにあること、`template` が型の id であること。"""
    if not path.exists():
        raise EvalError(
            f"ラベルのファイル {path} がありません(`decide --draft` で下書きを作れます)"
        )
    known = {row_key(r) for r in rows}
    valid = {g.id for g in dataset.template_groups}
    labels: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {ID_COLUMN, LABEL_COLUMN} - set(reader.fieldnames or [])
        if missing:
            raise EvalError(f"{path}: 列 {sorted(missing)} がありません")
        for line, rec in enumerate(reader, start=2):
            no = (rec[ID_COLUMN] or "").strip()
            tpl = (rec[LABEL_COLUMN] or "").strip()
            if no not in known:
                raise EvalError(f"{path}:{line}: {ID_COLUMN} {no!r} がデータにありません")
            if tpl not in valid:
                raise EvalError(
                    f"{path}:{line}: template {tpl!r} は不正です(使える値: {sorted(valid)})"
                )
            if no in labels:
                raise EvalError(f"{path}:{line}: {ID_COLUMN} {no!r} が重複しています")
            labels[no] = tpl
    if not labels:
        raise EvalError(f"{path}: ラベルが1行もありません")
    return labels


def evaluate(
    dataset: DatasetDef,
    rows: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str],
    providers: Sequence[str],
) -> list[ProviderResult]:
    """プロバイダーごとに、ラベルのある行の `template` 判断を走らせて比べる。

    キャッシュは使わない(時間を測るため)。時間は判断全体の実時間を問数で割る。
    """
    td = _template_decision(dataset)
    sub = dataset.model_copy(update={"decisions": [td]})  # 評価に関係ない判断(pii)は呼ばない
    target = [dict(r) for r in rows if row_key(r) in labels]

    def fillable(row: Mapping[str, Any]) -> list[str]:
        return fillable_types(dataset, row)

    results = []
    for name in providers:
        try:
            decider = create_decider(name, sub)
        except ValueError as e:
            raise EvalError(str(e)) from e
        engine = DecisionEngine(sub, decider)
        t0 = time.perf_counter()
        recs = engine.run(target, fillable)
        elapsed = time.perf_counter() - t0
        got = [r[td.id] for r in recs]
        agree = sum(g.get("choice") == labels[row_key(r)] for g, r in zip(got, target, strict=True))
        fb = sum(bool(g.get("used_fallback")) for g in got)
        results.append(ProviderResult(name, len(target), agree, fb, elapsed))
    return results


def format_results(results: Sequence[ProviderResult]) -> str:
    lines = []
    for r in results:
        ok = r.agreement >= PASS_AGREEMENT and r.fallback_rate <= PASS_FALLBACK
        lines += [
            f"プロバイダー: {r.provider}({r.total} 問)",
            f"  一致率: {r.agreement:.1%}({r.agree}/{r.total})",
            f"  フォールバック: {r.fallback_rate:.1%}({r.fallback}/{r.total})",
            f"  1問あたりの時間: {r.sec_per_question:.3f} 秒",
            f"  合格の目安(一致率 {PASS_AGREEMENT:.0%} 以上、"
            f"フォールバック {PASS_FALLBACK:.0%} 以下): " + ("満たす" if ok else "満たさない"),
        ]
    return "\n".join(lines)


def draft_labels(
    dataset: DatasetDef,
    rows: Sequence[Mapping[str, Any]],
    *,
    size: int = DRAFT_SIZE,
    seed: int = DRAFT_SEED,
) -> list[tuple[str, str]]:
    """`rules` の判断で型ごとに層化して `size` 行を選び、(No., template) を `No.` 順で返す。

    型ごとに `No.` 順に並べて `seed` でシャッフルし、型を順に1行ずつ取る
    (少ない型も入る)。同じ入力なら、結果は毎回同じ。
    """
    td = _template_decision(dataset)
    sub = dataset.model_copy(update={"decisions": [td]})
    engine = DecisionEngine(sub, create_decider("rules", sub))
    ordered = sorted((dict(r) for r in rows), key=lambda r: _no_order(row_key(r)))
    recs = engine.run(ordered, lambda row: fillable_types(dataset, row))
    by_type: dict[str, list[str]] = defaultdict(list)
    for r, rec in zip(ordered, recs, strict=True):
        by_type[rec[td.id].get("choice") or "other"].append(row_key(r))
    rng = random.Random(seed)
    queues = {t: rng.sample(v, len(v)) for t, v in sorted(by_type.items())}
    picked: list[tuple[str, str]] = []
    while len(picked) < size and any(queues.values()):
        for t, q in queues.items():
            if q and len(picked) < size:
                picked.append((q.pop(), t))
    return sorted(picked, key=lambda p: _no_order(p[0]))


def _no_order(no: str) -> tuple[int, int | str]:
    return (0, int(no)) if no.isdigit() else (1, no)


def write_labels(path: Path, labels: Sequence[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([ID_COLUMN, LABEL_COLUMN])
        w.writerows(labels)
