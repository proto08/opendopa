"""YAML の `decisions` を行ごとに実行する(キャッシュ・フォールバック・記録つき)。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from opendopa_pipeline.decider import rules
from opendopa_pipeline.decider.base import Decider, Decision, DecisionRequest, Option
from opendopa_pipeline.expr import expr_columns, parse_expr
from opendopa_pipeline.spec import DatasetDef, DatasetError
from opendopa_pipeline.spec import Decision as DecisionDef

TIMEOUT_SEC = 30.0  # 1問あたり

# 行 → その行で少なくとも1つのテンプレートが埋められる型の id(#33 が渡す)
FillableTypes = Callable[[Mapping[str, Any]], Iterable[str]]


class DecisionEngine:
    def __init__(
        self,
        dataset: DatasetDef,
        decider: Decider,
        *,
        cache_path: Path | None = None,
        timeout: float = TIMEOUT_SEC,
    ) -> None:
        self.dataset = dataset
        self.decider = decider
        self.timeout = timeout
        self._cache_path = cache_path
        self._cache: dict[str, Decision] = {}
        self._stats: dict[str, Counter[str]] = {d.id: Counter() for d in dataset.decisions}
        self._check_fallback_columns()
        if cache_path and cache_path.exists():
            self._load_cache(cache_path)

    # ---- 公開 ----

    def run(
        self, rows: Sequence[Mapping[str, Any]], fillable: FillableTypes
    ) -> list[dict[str, dict[str, Any]]]:
        """全行の判断を実行し、行ごとの記録(判断の id → 記録)を返す。

        同じ判断の問いは、まとめて(`decide_batch` があればそれで)推論する。
        記録は `videos.decisions`(jsonb)にそのまま入れられる形。
        """
        out: list[dict[str, dict[str, Any]]] = [{} for _ in rows]
        for d in self.dataset.decisions:
            reqs = [self._request(d, row, fillable) for row in rows]
            for i, dec in enumerate(self._decide_all(d, reqs)):
                out[i][d.id] = self._record(d, dec)
        return out

    def run_row(self, row: Mapping[str, Any], fillable: FillableTypes) -> dict[str, dict[str, Any]]:
        return self.run([row], fillable)[0]

    def report(self) -> dict[str, Any]:
        """フォールバックの割合(判断ごと・全体)。"""
        by = {
            did: {
                "total": c["total"],
                "fallback": c["fallback"],
                "fallback_rate": _rate(c["fallback"], c["total"]),
            }
            for did, c in self._stats.items()
        }
        total = sum(c["total"] for c in self._stats.values())
        fb = sum(c["fallback"] for c in self._stats.values())
        return {
            "dataset": self.dataset.id,
            "provider": self.decider.name,
            "total": total,
            "fallback": fb,
            "fallback_rate": _rate(fb, total),
            "decisions": by,
        }

    def write_report(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # ---- 内部 ----

    def _check_fallback_columns(self) -> None:
        # フォールバックの規則は state の列だけで評価する(渡していない列は見えない)
        for d in self.dataset.decisions:
            rule_name = (d.fallback or {}).get("rule")
            for i, r in enumerate(self.dataset.fallback_rules.get(rule_name, [])):
                missing = (expr_columns(parse_expr(r.if_)) if r.if_ else set()) - set(d.state)
                if missing:
                    raise DatasetError(
                        f"decisions[{d.id}]: fallback_rules.{rule_name}[{i}] が state にない列"
                        f" {sorted(missing)} を参照しています"
                    )

    def _request(
        self, d: DecisionDef, row: Mapping[str, Any], fillable: FillableTypes
    ) -> DecisionRequest:
        # 判断モデルに渡すのは state の列だけ
        state = {c: row.get(c) for c in d.state}
        options = None
        if d.options_from == "template_groups":
            ok = set(fillable(row))
            options = [Option(g.id, g.label) for g in self.dataset.template_groups if g.id in ok]
        return DecisionRequest(d.kind, state, d.question, options)

    def _decide_all(self, d: DecisionDef, reqs: list[DecisionRequest]) -> list[Decision]:
        results: dict[int, Decision | Exception] = {}
        todo: dict[str, list[int]] = {}  # キャッシュキー → 未計算の行(同じ入力は1回だけ)
        for i, req in enumerate(reqs):
            key = self._key(req)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                todo.setdefault(key, []).append(i)
        for key, raw in zip(todo, self._infer([reqs[ix[0]] for ix in todo.values()]), strict=True):
            if isinstance(raw, Decision):
                self._store(key, raw)
            for i in todo[key]:
                results[i] = raw  # 失敗は例外のまま、_finish でフォールバックにする
        return [self._finish(d, reqs[i], results[i]) for i in range(len(reqs))]

    def _infer(self, reqs: list[DecisionRequest]) -> list[Decision | Exception]:
        """プロバイダーを呼ぶ。失敗は例外オブジェクトのまま返す(止めない)。"""
        batch = getattr(self.decider, "decide_batch", None)
        if batch and len(reqs) > 1:
            try:
                got = self._with_timeout(lambda: batch(reqs), self.timeout * len(reqs))
                if len(got) == len(reqs):
                    return list(got)
            except Exception:  # noqa: BLE001  # バッチが失敗したら1件ずつに戻す
                pass
        out: list[Decision | Exception] = []
        for r in reqs:
            try:
                out.append(self._with_timeout(lambda r=r: self._call(r), self.timeout))
            except Exception as e:  # noqa: BLE001  # エラー・タイムアウトはフォールバックへ
                out.append(e)
        return out

    def _call(self, r: DecisionRequest) -> Decision:
        return self.decider.decide(r.kind, r.state, r.question, r.options, r.rubric)

    @staticmethod
    def _with_timeout(fn: Callable[[], Any], timeout: float) -> Any:
        ex = ThreadPoolExecutor(max_workers=1)
        try:
            return ex.submit(fn).result(timeout=timeout)
        except FutureTimeout:
            raise TimeoutError(f"{timeout}秒で終わりませんでした") from None
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    def _finish(self, d: DecisionDef, req: DecisionRequest, raw: Decision | Exception) -> Decision:
        if isinstance(raw, Decision) and self._usable(d, req, raw):
            return raw
        return self._fallback(d, req)

    def _usable(self, d: DecisionDef, req: DecisionRequest, dec: Decision) -> bool:
        if d.min_confidence is not None and dec.confidence < d.min_confidence:
            return False
        if d.kind == "choice":
            return dec.choice in {o.id for o in req.options or []}
        return dec.probability is not None

    def _fallback(self, d: DecisionDef, req: DecisionRequest) -> Decision:
        if d.kind == "choice":
            opts = req.options or []
            choice = rules.choose(d.fallback, self.dataset.fallback_rules, req.state, opts)
            dist = {o.id: 1.0 if o.id == choice else 0.0 for o in opts}
            return Decision(1.0, "rules", True, choice=choice, distribution=dist)
        # noul: regex_pii 以外(または指定なし)は、安全側に倒して「ある」とする
        is_pii = (d.fallback or {}).get("rule") != "regex_pii" or rules.contains_pii(req.state)
        return Decision(1.0, "rules", True, probability=1.0 if is_pii else 0.0)

    def _record(self, d: DecisionDef, dec: Decision) -> dict[str, Any]:
        c = self._stats[d.id]
        c["total"] += 1
        c["fallback"] += dec.used_fallback
        rec = {"id": d.id, "kind": d.kind, **dec.to_dict()}
        if d.exclude_if_probability_above is not None and dec.probability is not None:
            rec["excluded"] = dec.probability > d.exclude_if_probability_above
        return rec

    # ---- キャッシュ ----

    @staticmethod
    def _key_of(provider: str, r: DecisionRequest) -> str:
        payload = {
            "provider": provider,
            "kind": r.kind,
            "question": r.question,
            "state": r.state,
            "options": [[o.id, o.label] for o in r.options] if r.options is not None else None,
            "rubric": r.rubric,
        }
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _key(self, r: DecisionRequest) -> str:
        return self._key_of(self.decider.name, r)

    def _load_cache(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                e = json.loads(line)
                self._cache[e["key"]] = Decision.from_dict(e["decision"])

    def _store(self, key: str, dec: Decision) -> None:
        # 成功した結果だけを入れる(フォールバックの判定は毎回かけ直すので、しきい値を変えられる)
        self._cache[key] = dec
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "decision": dec.to_dict()}, ensure_ascii=False))
                f.write("\n")


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0
