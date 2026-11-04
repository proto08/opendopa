"""`opendopa` コマンドの入口(設計書 §8.1、ADR-0012 A7)。

各サブコマンドの中身は、M1 以降で実装する。
"""

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="OpenDopa のコンテンツ生成パイプライン", no_args_is_help=True)

DatasetOpt = Annotated[str, typer.Option("--dataset", help="データセットID(例: accident)")]


def _not_implemented(name: str, milestone: str) -> None:
    typer.echo(f"`{name}` はまだ実装されていません({milestone})", err=True)
    raise typer.Exit(code=1)


@app.command()
def profile(dataset: DatasetOpt) -> None:
    """列のプロファイルを出す。"""
    _not_implemented("profile", "M1")


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
