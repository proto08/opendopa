"""`rules` プロバイダー: `fallback_rules`(式言語は #29)と `regex_pii`。

`rules` は判断モデルの代わりに「これを使う」と選んだ既定の実装なので、
結果の `used_fallback` は `False`、`confidence` は `1.0` とする
(フォールバックの割合に数えるのは、判断モデルが失敗したときだけ)。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from opendopa_pipeline.decider.base import Decision, Kind, Option
from opendopa_pipeline.expr import eval_expr, parse_expr
from opendopa_pipeline.spec import DatasetDef, FallbackRule

PII_PATTERNS = {
    # 電話番号: 0 から始まる、ハイフン区切りまたは 10〜11 桁の数字
    "phone": re.compile(r"0\d{1,4}[-ー－]\d{1,4}[-ー－]\d{3,4}|(?<!\d)0\d{9,10}(?!\d)"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    # 番地らしい文字列: 「3丁目」「12番地」「4番5号」
    "address": re.compile(r"[0-9０-９]+\s*(?:丁目|番地)|[0-9０-９]+\s*番\s*[0-9０-９]+\s*号"),
}


def contains_pii(state: Mapping[str, Any]) -> bool:
    return any(
        p.search(v) for v in state.values() if isinstance(v, str) for p in PII_PATTERNS.values()
    )


def apply_rules(rules: list[FallbackRule], state: Mapping[str, Any]) -> str | None:
    """規則を上から順に試し、最初に当たった `then`(または `else`)を返す。"""
    for r in rules:
        if r.else_ is not None:
            return r.else_
        if r.if_ is not None and eval_expr(parse_expr(r.if_), state):
            return r.then
    return None


def choose(
    fallback: Mapping[str, Any] | None,
    rules: Mapping[str, list[FallbackRule]],
    state: Mapping[str, Any],
    options: list[Option],
) -> str | None:
    """`fallback` の指定(`{rule, default}`)で選択肢から1つ選ぶ。

    規則の結果が選択肢にない(その行で埋められない型)ときは `default`、
    それも選択肢にないときは先頭の選択肢にする。選択肢が空なら `None`。
    """
    ids = [o.id for o in options]
    fb = fallback or {}
    picked = apply_rules(rules.get(fb.get("rule", ""), []), state)
    for cand in (picked, fb.get("default")):
        if cand in ids:
            return cand
    return ids[0] if ids else None


class RulesDecider:
    name = "rules"

    def __init__(self, dataset: DatasetDef) -> None:
        self._rules = dataset.fallback_rules
        # `decide` は質問文で、どの判断かを引く(質問文は判断ごとに別にする)
        self._by_question: dict[str, dict[str, Any] | None] = {}
        for d in dataset.decisions:
            if d.question in self._by_question and self._by_question[d.question] != d.fallback:
                raise ValueError(f"decisions: 質問文 {d.question!r} が別の判断と重なっています")
            self._by_question[d.question] = d.fallback

    @classmethod
    def from_dataset(cls, dataset: DatasetDef) -> RulesDecider:
        return cls(dataset)

    def decide(
        self,
        kind: Kind,
        state: dict[str, Any],
        question: str,
        options: list[Option] | None = None,
        rubric: list[str] | None = None,
    ) -> Decision:
        fallback = self._by_question.get(question)
        if kind == "noul":
            p = 1.0 if contains_pii(state) else 0.0
            return Decision(confidence=1.0, provider=self.name, probability=p)
        if kind == "choice":
            opts = options or []
            choice = choose(fallback, self._rules, state, opts)
            dist = {o.id: 1.0 if o.id == choice else 0.0 for o in opts}
            return Decision(confidence=1.0, provider=self.name, choice=choice, distribution=dist)
        raise ValueError(f"rules は kind={kind!r} に対応していません")
