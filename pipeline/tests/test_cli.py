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
