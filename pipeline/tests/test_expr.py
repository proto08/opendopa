import pytest

from opendopa_pipeline.expr import ExprError, eval_expr, expr_columns, parse_expr


def ev(text: str, row: dict) -> bool:
    return eval_expr(parse_expr(text), row)


def test_and_with_null_comparison() -> None:
    text = "a == 'x' and b != null"
    assert ev(text, {"a": "x", "b": 1})
    assert not ev(text, {"a": "x", "b": None})
    assert not ev(text, {"a": "y", "b": 1})


def test_contains() -> None:
    text = "contains(S, ['不能','制御'])"
    assert ev(text, {"S": "制御を失った"})
    assert not ev(text, {"S": "衝突した"})
    assert not ev(text, {"S": None})


def test_null_comparison() -> None:
    assert ev("a == null", {"a": None})
    assert ev("a == null", {})  # 行にない列は欠損
    assert not ev("a == null", {"a": 0})
    assert ev("a != null", {"a": 0})


def test_ordering_comparison() -> None:
    assert ev("n > 3", {"n": 4})
    assert ev("n < 3.5", {"n": 3})
    assert not ev("n > 3", {"n": None})  # null との大小は偽
    assert not ev("n > 3", {"n": "9"})  # 型違いは偽


def test_and_binds_tighter_than_or() -> None:
    # a or (b and c)。a が真なら b, c が偽でも真
    assert ev("a == 1 or b == 1 and c == 1", {"a": 1, "b": 0, "c": 0})
    # (a or b) and c なら偽になるはずなので、優先順位が違えば結果が変わる
    assert not ev("a == 0 or b == 1 and c == 1", {"a": 1, "b": 1, "c": 0})
    assert not ev("(a == 1 or b == 1) and c == 1", {"a": 1, "b": 0, "c": 0})


def test_double_quoted_and_japanese_column() -> None:
    assert ev('種別 == "事故"', {"種別": "事故"})


def test_expr_columns() -> None:
    assert expr_columns(parse_expr("a == 'x' and contains(S, ['y']) or b != null")) == {
        "a",
        "S",
        "b",
    }


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os')",
        "__import__('os').system('ls')",
        "1 + 1",
        "a.b",
        "len(a)",
        "contains(a, ['x']",
        "(a == 1",
        "a == 1)",
        "a ==",
        "and a == 1",
        "a == 1 b == 2",
        "contains(a, [b])",
        "contains(a, [])",
        "a == 'x",
        "",
        "a >= 1",
    ],
)
def test_rejects_unsupported_syntax(text: str) -> None:
    with pytest.raises(ExprError):
        parse_expr(text)
