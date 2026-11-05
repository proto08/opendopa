"""Decider のインターフェースと、やり取りする値。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

Kind = Literal["choice", "noul", "score"]


@dataclass(frozen=True)
class Option:
    """選択肢。`id` はコード用、`label` は判断モデルへの質問に出す日本語。"""

    id: str
    label: str


@dataclass
class Decision:
    """判断の結果。種類によって使う項目が違う(使わない項目は `None` / 空)。"""

    confidence: float  # 分布の集中の度合い(0〜1)
    provider: str
    used_fallback: bool = False
    choice: str | None = None  # choice のとき
    distribution: dict[str, float] = field(default_factory=dict)  # 各選択肢の確率
    score: float | None = None  # score のとき(期待値)
    probability: float | None = None  # noul のとき(はいの確率)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Decision:
        return cls(**d)


@dataclass(frozen=True)
class DecisionRequest:
    """`decide` の引数をまとめたもの(バッチ処理用)。"""

    kind: Kind
    state: dict[str, Any]
    question: str
    options: list[Option] | None = None
    rubric: list[str] | None = None


class Decider(Protocol):
    """判断モデル。新しいプロバイダーは、これを満たして `registry.register` するだけでよい。

    同じ質問をまとめて推論できるプロバイダーは、任意で
    `decide_batch(requests: list[DecisionRequest]) -> list[Decision]` も実装する
    (エンジンがあれば使う。なければ `decide` を1件ずつ呼ぶ)。
    """

    name: str

    def decide(
        self,
        kind: Kind,
        state: dict[str, Any],
        question: str,
        options: list[Option] | None = None,
        rubric: list[str] | None = None,
    ) -> Decision: ...
