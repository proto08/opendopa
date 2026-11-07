"""`strands_local` プロバイダー: 手元の PC で Strands Decider 2B をプロセス内で動かす。

依存(PyTorch など)は extra に分けてある: `uv sync --extra decider`
(`strands_azure` と違い、API サーバーは使わない。`strands-decider serve` も使わない)。

環境変数:
- `STRANDS_LOCAL_MODEL`: モデルの Hub ID またはローカルのディレクトリ
  (既定 `StrandsAgents/strands-decider-2B-hobson-v19`。初回は Hugging Face Hub から重みを落とす)
- `STRANDS_LOCAL_DEVICE`: `cuda` / `mps` / `cpu`(既定は cuda > mps > cpu の順で使えるもの)

呼び方(strands-decider 0.3.0 の `SystemOneEngine.evaluate`): 1つの `state` に対して
`questions` を渡し、`answers[name]` に型ごとの答えが返る。
- noul   : `NoulAnswer.noul`(はいの確率)
- choice : `ChoiceAnswer.choice` / `.probabilities`(選択肢名 → 確率)
- score  : `ScoreAnswer.score`(期待値)/ `.confidence`

選択・確信度は `strands_azure` と同じ作り方にそろえる(choice は最大確率、noul は max(p, 1-p))。
モデルが読めない・推論が失敗したときは例外を投げ、エンジンが `rules` にフォールバックする
(確信度のしきい値もエンジン側)。モデルの読み込みは、エンジンの1問あたりの時間制限に
入れないため、プロバイダーを作るときに行う。読み込みに失敗しても止めず、問いごとに失敗させる。
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from opendopa_pipeline.decider.base import Decision, DecisionRequest, Kind, Option
from opendopa_pipeline.spec import DatasetDef

logger = logging.getLogger(__name__)

NAME = "strands_local"
DEFAULT_MODEL = "StrandsAgents/strands-decider-2B-hobson-v19"
_QUESTION = "q"


class StrandsLocalDecider:
    name = NAME

    def __init__(self, engine: Any | None = None, load_error: Exception | None = None) -> None:
        self._engine = engine
        self._load_error = load_error
        self._lock = threading.Lock()  # 時間切れで放置された推論と重ならないように
        self.failed = 0  # rules にフォールバックさせた件数の累計(黙ってフォールバックしないため)

    @classmethod
    def from_dataset(cls, _dataset: DatasetDef) -> StrandsLocalDecider:
        model = os.environ.get("STRANDS_LOCAL_MODEL") or DEFAULT_MODEL
        device = os.environ.get("STRANDS_LOCAL_DEVICE") or None
        try:
            return cls(engine=_load_engine(model, device))
        except Exception as e:  # noqa: BLE001  # 読めなくても止めず、rules に戻す
            logger.warning("strands_local: %s を読めません(rules にフォールバック): %s", model, e)
            return cls(load_error=e)

    def decide(
        self,
        kind: Kind,
        state: dict[str, Any],
        question: str,
        options: list[Option] | None = None,
        rubric: list[str] | None = None,
    ) -> Decision:
        try:
            return self._decide(DecisionRequest(kind, state, question, options, rubric))
        except Exception:
            self.failed += 1
            logger.warning(
                "strands_local が失敗し rules にフォールバックした(累計 %d 件)", self.failed
            )
            raise

    def _decide(self, r: DecisionRequest) -> Decision:
        if self._engine is None:
            raise RuntimeError(f"strands_local: モデルを読めていません: {self._load_error}")
        payload, names = _payload(r)
        with self._lock:
            response = self._engine.evaluate(_make_request(payload))
        answer = response.answers[_QUESTION]
        return _to_decision(r, answer, names)


def _load_engine(model: str, device: str | None) -> Any:
    try:
        from strands_decider.infer import load_engine
    except ImportError as e:
        raise ImportError(
            "strands_local には extra が必要です: uv sync --extra decider(PyTorch などが入ります)"
        ) from e
    if device is None:
        import torch

        if torch.cuda.is_available():
            device = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    return load_engine(model, device=device)


def _make_request(payload: dict[str, Any]) -> Any:
    from strands_decider.schema import SystemOneRequest

    return SystemOneRequest.model_validate(payload)


def _payload(r: DecisionRequest) -> tuple[dict[str, Any], dict[str, str]]:
    """`SystemOneRequest` の中身と、選択肢名 → id の対応(choice のとき)を作る。"""
    names: dict[str, str] = {}
    if r.kind == "noul":
        q: dict[str, Any] = {"type": "noul", "instructions": r.question}
    elif r.kind == "choice":
        if not r.options or len(r.options) < 2:
            raise ValueError("strands_local: choice には選択肢が2つ以上必要です")
        # モデルには日本語のラベルを見せる。ラベルが重なるときだけ id を使う
        use_label = len({o.label for o in r.options}) == len(r.options)
        names = {(o.label if use_label else o.id): o.id for o in r.options}
        q = {"type": "choice", "instructions": r.question, "criteria": dict.fromkeys(names)}
    else:
        if not r.rubric:
            raise ValueError("strands_local: score には rubric が必要です")
        q = {"type": "score", "instructions": r.question, "criteria": list(r.rubric)}
    return {"state": r.state, "questions": {_QUESTION: q}}, names


def _to_decision(r: DecisionRequest, answer: Any, names: dict[str, str]) -> Decision:
    """モデルの答えを `Decision` にする。形が壊れていれば確信度0(→ エンジンがフォールバック)。"""
    if r.kind == "choice":
        dist: dict[str, float] = {}
        for k, v in (answer.probabilities or {}).items():
            if k in names and isinstance(v, int | float):
                dist[names[k]] = dist.get(names[k], 0.0) + float(v)
        total = sum(dist.values())
        if total <= 0:
            return Decision(0.0, NAME)
        dist = {k: v / total for k, v in dist.items()}
        choice = max(dist, key=lambda k: dist[k])
        return Decision(dist[choice], NAME, choice=choice, distribution=dist)
    if r.kind == "noul":
        p = answer.noul
        if not isinstance(p, int | float) or not 0.0 <= p <= 1.0:
            return Decision(0.0, NAME)
        return Decision(max(p, 1 - p), NAME, probability=float(p))
    s = answer.score
    if not isinstance(s, int | float):
        return Decision(0.0, NAME)
    return Decision(float(answer.confidence), NAME, score=float(s))
