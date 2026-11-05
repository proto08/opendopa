"""`generate`: 読み込みから出力まで(設計書 §8.2)。"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opendopa_pipeline import gate
from opendopa_pipeline.build import Video, build_dataset, write_outputs
from opendopa_pipeline.decider import DecisionEngine, create_decider, provider_name_from_env
from opendopa_pipeline.prepare import prepare
from opendopa_pipeline.spec import DatasetDef


@dataclass
class GenerateResult:
    videos: list[Video]
    report: dict[str, Any]


def run_generate(
    dataset: DatasetDef,
    root: Path | str,
    out_dir: Path | str,
    provider: str | None = None,
) -> GenerateResult:
    """データセットを生成して `out_dir`(`out/<id>`)に書く。

    書くもの: `scenes.jsonl` / `videos.jsonl` / `excluded.csv` / `decisions_report.json`
    (+ 判断のキャッシュ `decisions.cache.jsonl`)。
    """
    out = Path(out_dir)
    prepared = prepare(dataset, root)  # excluded.csv は、後で選定以降の除外とまとめて書く
    engine = None
    if dataset.decisions:
        name = provider or provider_name_from_env()
        engine = DecisionEngine(
            dataset, create_decider(name, dataset), cache_path=out / "decisions.cache.jsonl"
        )
    videos = build_dataset(dataset, prepared, engine)

    write_outputs(videos, out)
    _write_excluded(out / "excluded.csv", prepared, videos)
    report = make_report(dataset, prepared, videos, engine)
    (out / "decisions_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return GenerateResult(videos, report)


def _write_excluded(path: Path, prepared: Any, videos: list[Video]) -> None:
    """除外した行を理由つきで書く。列: row_id, video_id, stage, reason, detail。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "video_id", "stage", "reason", "detail"])
        for e in prepared.excluded:
            w.writerow([e.row_id, "", "clean", "filter", e.reason])
        for v in videos:
            if v.status == "excluded":
                w.writerow([v.row_id, v.video_id, "build", v.excluded_why, v.excluded_detail])


def make_report(
    dataset: DatasetDef, prepared: Any, videos: list[Video], engine: DecisionEngine | None
) -> dict[str, Any]:
    """生成件数・除外件数と理由の内訳・推定秒数の最小/中央/最大・型の内訳・警告。"""
    ok = [v for v in videos if v.scene is not None]
    reasons = [v.excluded_why or "unknown" for v in videos if v.status == "excluded"]
    reasons += ["filter"] * len(prepared.excluded)
    types = Counter(
        (v.decisions.get(dataset.template_select.decision) or {}).get("choice") or "?"
        for v in ok
        if dataset.template_select is not None
    )
    report: dict[str, Any] = engine.report() if engine else {"dataset": dataset.id}
    warnings: list[str] = []
    rate = report.get("fallback_rate")
    if isinstance(rate, float) and rate > gate.FALLBACK_WARN_RATE:
        warnings.append(
            f"判断のフォールバックが {rate:.0%} です(上限 {gate.FALLBACK_WARN_RATE:.0%})"
        )
    report["warnings"] = warnings
    report["summary"] = {
        "generated": len(ok),
        "excluded": len(reasons),
        "excluded_by_reason": gate.count_reasons(reasons),
        "estimated_sec": gate.summarize([v.scene["durationSec"] for v in ok if v.scene]),
        "by_type": dict(sorted(types.items())),
    }
    return report


def format_summary(report: dict[str, Any]) -> str:
    s = report["summary"]
    sec = s["estimated_sec"]
    lines = [
        f"データセット: {report['dataset']}",
        f"生成: {s['generated']} 本 / 除外: {s['excluded']} 行",
    ]
    for reason, n in s["excluded_by_reason"].items():
        lines.append(f"  除外 {reason}: {n}")
    if sec["min"] is not None:
        lines.append(f"推定秒数: 最小 {sec['min']} / 中央 {sec['median']} / 最大 {sec['max']}")
    if s["by_type"]:
        lines.append("型の内訳: " + ", ".join(f"{k} {v}" for k, v in s["by_type"].items()))
    if "fallback_rate" in report:
        lines.append(f"判断のフォールバック: {report['fallback']}/{report['total']}")
    lines += [f"警告: {w}" for w in report["warnings"]]
    return "\n".join(lines)
