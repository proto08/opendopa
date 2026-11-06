"""`strands_azure` プロバイダー: Azure 上の内部 API(Strands Decider 2B)を呼ぶ。

環境変数:
- `STRANDS_DECIDER_URL`: 内部 API のベース URL(必須。外部には公開しない)
- `STRANDS_DECIDER_TOKEN`: 内部 API の認証トークン(`Authorization: Bearer` で送る)
- `STRANDS_DECIDER_TIMEOUT`: 1問あたりの秒数(既定 30)

API の形(`POST {URL}/v1/decide`。問いは配列で、同じ順に結果が返る):

    {"requests": [{"kind": "choice", "state": {...}, "question": "...",
                   "options": [{"id": "...", "label": "..."}], "rubric": null}]}
    -> {"results": [{"distribution": {"<id>": 0.7, ...},   # choice
                     "probability": 0.1,                    # noul(はいの確率)
                     "score": 3.2}]}                        # score(期待値)

選択・確信度はここで分布から作る。API が失敗・タイムアウトしたときは例外を投げ、
エンジンが `rules` にフォールバックする(確信度のしきい値もエンジン側)。
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from opendopa_pipeline.decider.base import Decision, DecisionRequest, Kind, Option
from opendopa_pipeline.spec import DatasetDef

NAME = "strands_azure"
DEFAULT_TIMEOUT = 30.0
PATH = "/v1/decide"


class StrandsAzureDecider:
    name = NAME

    def __init__(self, url: str, token: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._endpoint = url.rstrip("/") + PATH
        self._token = token
        self._timeout = timeout

    @classmethod
    def from_dataset(cls, _dataset: DatasetDef) -> StrandsAzureDecider:
        url = os.environ.get("STRANDS_DECIDER_URL", "")
        if not url:
            raise ValueError("DECIDER_PROVIDER=strands_azure には STRANDS_DECIDER_URL が必要です")
        timeout = float(os.environ.get("STRANDS_DECIDER_TIMEOUT") or DEFAULT_TIMEOUT)
        return cls(url, os.environ.get("STRANDS_DECIDER_TOKEN", ""), timeout)

    def decide(
        self,
        kind: Kind,
        state: dict[str, Any],
        question: str,
        options: list[Option] | None = None,
        rubric: list[str] | None = None,
    ) -> Decision:
        return self.decide_batch([DecisionRequest(kind, state, question, options, rubric)])[0]

    def decide_batch(self, requests: list[DecisionRequest]) -> list[Decision]:
        body = {"requests": [_wire(r) for r in requests]}
        results = self._post(body, self._timeout * max(len(requests), 1)).get("results")
        if not isinstance(results, list) or len(results) != len(requests):
            raise ValueError("strands_azure: results の件数が問いと合いません")
        return [_to_decision(r, raw) for r, raw in zip(requests, results, strict=True)]

    def _post(self, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(  # noqa: S310  # URL は環境変数(内部 API)
            self._endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        # 4xx・5xx は HTTPError(例外)になる。呼び出し側(エンジン)がフォールバックにする
        with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310
            return json.loads(res.read().decode("utf-8"))


def _wire(r: DecisionRequest) -> dict[str, Any]:
    return {
        "kind": r.kind,
        "state": r.state,
        "question": r.question,
        "options": [{"id": o.id, "label": o.label} for o in r.options] if r.options else None,
        "rubric": r.rubric,
    }


def _to_decision(r: DecisionRequest, raw: Any) -> Decision:
    """API の結果を `Decision` にする。形が壊れた1件は、確信度0(→ エンジンがフォールバック)。"""
    raw = raw if isinstance(raw, dict) else {}
    if r.kind == "choice":
        ids = {o.id for o in r.options or []}
        dist = {
            k: float(v)
            for k, v in (raw.get("distribution") or {}).items()
            if k in ids and isinstance(v, int | float)
        }
        total = sum(dist.values())
        if total <= 0:
            return Decision(0.0, NAME)
        dist = {k: v / total for k, v in dist.items()}
        choice = max(dist, key=lambda k: dist[k])
        return Decision(dist[choice], NAME, choice=choice, distribution=dist)
    if r.kind == "noul":
        p = raw.get("probability")
        if not isinstance(p, int | float) or not 0.0 <= p <= 1.0:
            return Decision(0.0, NAME)
        return Decision(max(p, 1 - p), NAME, probability=float(p))
    s = raw.get("score")
    if not isinstance(s, int | float):
        return Decision(0.0, NAME)
    return Decision(1.0, NAME, score=float(s))
