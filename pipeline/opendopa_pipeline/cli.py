"""`opendopa` コマンドの入口(設計書 §8.1、ADR-0012 A7)。

各サブコマンドの中身は、M1 以降で実装する。
"""

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from opendopa_pipeline.decider.evaluate import (
    draft_labels,
    evaluate,
    format_results,
    load_labels,
    write_labels,
)
from opendopa_pipeline.generate import format_summary, run_generate
from opendopa_pipeline.ingest import IngestError, load_frame, load_path, row_dict
from opendopa_pipeline.prepare import prepare
from opendopa_pipeline.profile import build_profile, format_table, prepare_raw
from opendopa_pipeline.spec import load_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]

app = typer.Typer(help="OpenDopa のコンテンツ生成パイプライン", no_args_is_help=True)

DatasetOpt = Annotated[str, typer.Option("--dataset", help="データセットID(例: accident)")]


def _not_implemented(name: str, milestone: str) -> None:
    typer.echo(f"`{name}` はまだ実装されていません({milestone})", err=True)
    raise typer.Exit(code=1)


def _fail(message: str) -> typer.Exit:
    typer.echo(f"エラー: {message}", err=True)
    return typer.Exit(code=2)


@app.command()
def profile(
    dataset: Annotated[
        str | None, typer.Option("--dataset", help="データセットID(例: accident)")
    ] = None,
    file: Annotated[
        list[Path] | None,
        typer.Option("--file", help="CSV を直接指定する(YAML がない新規データセット用。複数可)"),
    ] = None,
    out_dir: Annotated[Path, typer.Option("--out-dir", help="出力先の親")] = REPO_ROOT / "out",
) -> None:
    """列のプロファイル(型・欠損率・種類数・最長の文字数・役割・上位の値)を出す。"""
    if dataset is None and not file:
        raise _fail("--dataset か --file のどちらかを指定してください")
    dataset_id = dataset or file[0].stem  # type: ignore[index]
    try:
        if file:
            df = prepare_raw(pd.concat([load_path(p) for p in file], ignore_index=True))
            source = [str(p) for p in file]
        else:
            yaml_path = REPO_ROOT / "datasets" / f"{dataset_id}.yaml"
            if yaml_path.exists():
                definition = load_dataset(yaml_path)
                df = load_frame(definition, REPO_ROOT)
                source = definition.files
            else:
                # 新規データセットは YAML がまだない。data/raw/<id>/ の CSV を読む
                paths = sorted((REPO_ROOT / "data" / "raw" / dataset_id).glob("*.csv"))
                if not paths:
                    raise IngestError(
                        f"datasets/{dataset_id}.yaml も data/raw/{dataset_id}/*.csv もありません"
                    )
                df = prepare_raw(pd.concat([load_path(p) for p in paths], ignore_index=True))
                source = [str(p.relative_to(REPO_ROOT)) for p in paths]
    except (IngestError, ValueError) as e:
        raise _fail(str(e)) from e

    result = build_profile(dataset_id, df, source)
    typer.echo(format_table(result))
    out_path = out_dir / dataset_id / "profile.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"\n書き出しました: {out_path}")


@app.command()
def generate(
    dataset: DatasetOpt,
    out_dir: Annotated[Path, typer.Option("--out-dir", help="出力先の親")] = REPO_ROOT / "out",
    provider: Annotated[
        str | None, typer.Option("--provider", help="判断のプロバイダー(既定は DECIDER_PROVIDER)")
    ] = None,
) -> None:
    """選定 → 判断 → 原稿 → シーン → 品質ゲート → out/<id>/ に出力。"""
    yaml_path = REPO_ROOT / "datasets" / f"{dataset}.yaml"
    try:
        definition = load_dataset(yaml_path)
        result = run_generate(definition, REPO_ROOT, out_dir / dataset, provider)
    except (IngestError, ValueError, OSError) as e:  # DatasetError は ValueError
        raise _fail(str(e)) from e
    typer.echo(format_summary(result.report))
    typer.echo(f"\n書き出しました: {out_dir / dataset}")


@app.command()
def decide(
    dataset: DatasetOpt,
    eval_labels: Annotated[Path | None, typer.Option("--eval", help="人が付けた正解のCSV")] = None,
    draft: Annotated[
        bool, typer.Option("--draft", help="rules の判断で、評価用ラベルの下書き(50行)を出す")
    ] = False,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="評価するプロバイダー(カンマ区切りで複数。既定は rules)"),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="--draft で既存のファイルを上書きする")
    ] = False,
) -> None:
    """判断モデルの評価(人が付けた正解との一致率)と、正解の下書き。"""
    if draft == (eval_labels is not None):
        raise _fail("`--eval <CSV>` と `--draft` のどちらか1つを指定してください")
    yaml_path = REPO_ROOT / "datasets" / f"{dataset}.yaml"
    try:
        definition = load_dataset(yaml_path)
        rows = [row_dict(r) for _, r in prepare(definition, REPO_ROOT).frame.iterrows()]
        if draft:
            out = REPO_ROOT / "datasets" / f"{dataset}.labels.csv"
            if out.exists() and not force:
                raise _fail(f"{out} が既にあります(人が直した内容を守るため。上書きは --force)")
            write_labels(out, draft_labels(definition, rows))
            typer.echo(f"下書きを書き出しました: {out}\n`template` を人が確認して直してください")
            return
        assert eval_labels is not None
        names = [p.strip() for p in (provider or "rules").split(",") if p.strip()]
        labels = load_labels(eval_labels, definition, rows)
        typer.echo(format_results(evaluate(definition, rows, labels, names)))
    except (IngestError, ValueError, OSError) as e:  # EvalError・DatasetError は ValueError
        raise _fail(str(e)) from e


@app.command()
def embed() -> None:
    """全動画の埋め込み・2D座標・クラスタ。"""
    _not_implemented("embed", "M2")


@app.command()
def tts(dataset: DatasetOpt) -> None:
    """音声(TTS_PROVIDER が none ならスキップ)。"""
    _not_implemented("tts", "M8")


@app.command()
def publish() -> None:
    """Blob と DB へ書き込む。"""
    _not_implemented("publish", "M2")


@app.command(name="all")
def run_all() -> None:
    """上のコマンドを順に実行する。"""
    _not_implemented("all", "M2")
