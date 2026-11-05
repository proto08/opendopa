"""`opendopa` コマンドの入口(設計書 §8.1、ADR-0012 A7)。

各サブコマンドの中身は、M1 以降で実装する。
"""

import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from opendopa_pipeline.ingest import IngestError, load_frame, load_path
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
def generate(dataset: DatasetOpt) -> None:
    """選定 → 原稿 → シーン → 検証 → out/<id>/scenes.jsonl。"""
    _not_implemented("generate", "M1")


@app.command()
def decide(
    dataset: DatasetOpt,
    eval_labels: Annotated[Path | None, typer.Option("--eval", help="人が付けた正解のCSV")] = None,
) -> None:
    """判断モデルの評価(人が付けた正解との一致率)。"""
    _not_implemented("decide", "M1b")


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
