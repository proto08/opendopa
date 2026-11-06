from typer.testing import CliRunner

from opendopa_pipeline.cli import app

runner = CliRunner()


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ["profile", "generate", "decide", "embed", "tts", "publish", "all"]:
        assert name in result.output


def test_unimplemented_command_fails() -> None:
    result = runner.invoke(app, ["embed"])
    assert result.exit_code == 1


def test_generate_without_data_fails_cleanly(tmp_path) -> None:
    # data/raw がない環境では、トレースバックでなくエラーメッセージで終わる
    result = runner.invoke(app, ["generate", "--dataset", "nope", "--out-dir", str(tmp_path)])
    assert result.exit_code == 2


def test_decide_requires_exactly_one_mode() -> None:
    assert runner.invoke(app, ["decide", "--dataset", "accident"]).exit_code == 2
    both = ["decide", "--dataset", "accident", "--draft", "--eval", "x.csv"]
    assert runner.invoke(app, both).exit_code == 2
