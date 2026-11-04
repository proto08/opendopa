"""列定義 YAML の式言語(`when`、`filters`、`fallback_rules` の `if`。docs/data.md §8.3)。

許可リスト方式の再帰下降パーサ。Python の `eval`・`exec`・`ast` は使わない。

    expr     := and_expr ("or" and_expr)*
    and_expr := cmp ("and" cmp)*
    cmp      := primary (("==" | "!=" | ">" | "<") primary)?
    primary  := 列名 | 文字列 | 数値 | null | contains(列名, [リテラル, ...]) | "(" expr ")"

`and` は `or` より強い。比較の結果は真偽値。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class ExprError(ValueError):
    """式の構文エラー。"""


@dataclass(frozen=True)
class Literal:
    value: str | float | int | None


@dataclass(frozen=True)
class Column:
    name: str


@dataclass(frozen=True)
class Compare:
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Contains:
    column: str
    words: tuple[str, ...]


@dataclass(frozen=True)
class BoolOp:
    op: str  # "and" | "or"
    operands: tuple[Expr, ...]


Expr = Literal | Column | Compare | Contains | BoolOp

_TOKEN = re.compile(
    r"""\s*(?:
        (?P<str>'[^']*'|"[^"]*")
      | (?P<num>-?\d+(?:\.\d+)?)
      | (?P<op>==|!=|>|<|\(|\)|\[|\]|,)
      | (?P<ident>\w+)
    )""",
    re.VERBOSE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = _TOKEN.match(text, pos)
        if m is None:
            bad = text[pos:].lstrip()[0]
            raise ExprError(f"式に使えない文字 {bad!r} があります: {text!r}")
        pos = m.end()
        kind = m.lastgroup
        assert kind is not None
        tokens.append((kind, m.group(kind)))
    return tokens


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens = _tokenize(text)
        self.i = 0

    def _fail(self, msg: str) -> ExprError:
        return ExprError(f"{msg}: {self.text!r}")

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _next(self) -> tuple[str, str]:
        tok = self._peek()
        if tok is None:
            raise self._fail("式が途中で終わっています")
        self.i += 1
        return tok

    def _accept_ident(self, word: str) -> bool:
        tok = self._peek()
        if tok == ("ident", word):
            self.i += 1
            return True
        return False

    def _expect_op(self, op: str) -> None:
        tok = self._next()
        if tok != ("op", op):
            raise self._fail(f"{op!r} が必要です(実際は {tok[1]!r})")

    def parse(self) -> Expr:
        if not self.tokens:
            raise self._fail("式が空です")
        expr = self._or()
        if self._peek() is not None:
            raise self._fail(f"式の途中に余分な {self._peek()[1]!r} があります")  # type: ignore[index]
        return expr

    def _or(self) -> Expr:
        operands = [self._and()]
        while self._accept_ident("or"):
            operands.append(self._and())
        return operands[0] if len(operands) == 1 else BoolOp("or", tuple(operands))

    def _and(self) -> Expr:
        operands = [self._cmp()]
        while self._accept_ident("and"):
            operands.append(self._cmp())
        return operands[0] if len(operands) == 1 else BoolOp("and", tuple(operands))

    def _cmp(self) -> Expr:
        left = self._primary()
        tok = self._peek()
        if tok is not None and tok[0] == "op" and tok[1] in ("==", "!=", ">", "<"):
            self.i += 1
            return Compare(tok[1], left, self._primary())
        return left

    def _literal(self, kind: str, value: str) -> Literal:
        if kind == "str":
            return Literal(value[1:-1])
        if kind == "num":
            return Literal(float(value) if "." in value else int(value))
        raise self._fail(f"リテラルが必要です(実際は {value!r})")

    def _primary(self) -> Expr:
        kind, value = self._next()
        if kind == "op" and value == "(":
            expr = self._or()
            self._expect_op(")")
            return expr
        if kind in ("str", "num"):
            return self._literal(kind, value)
        if kind == "ident":
            if value == "null":
                return Literal(None)
            nxt = self._peek()
            if nxt == ("op", "("):
                if value != "contains":
                    raise self._fail(f"未知の関数 {value!r} です(使えるのは contains のみ)")
                return self._contains()
            if value in ("and", "or"):
                raise self._fail(f"{value!r} の前に式が必要です")
            return Column(value)
        raise self._fail(f"式の途中に予期しない {value!r} があります")

    def _contains(self) -> Contains:
        self._expect_op("(")
        kind, name = self._next()
        if kind != "ident" or name == "null":
            raise self._fail("contains の第1引数は列名です")
        self._expect_op(",")
        self._expect_op("[")
        words: list[str] = []
        while True:
            kind, value = self._next()
            if kind != "str":
                raise self._fail("contains の語は文字列です")
            words.append(value[1:-1])
            tok = self._next()
            if tok == ("op", "]"):
                break
            if tok != ("op", ","):
                raise self._fail(f"',' または ']' が必要です(実際は {tok[1]!r})")
        self._expect_op(")")
        return Contains(name, tuple(words))


def parse_expr(text: str) -> Expr:
    """式をパースする。許可していない構文は `ExprError`(何も実行しない)。"""
    return _Parser(text).parse()


def expr_columns(expr: Expr) -> set[str]:
    """式が参照する列名の集合。"""
    match expr:
        case Column(name):
            return {name}
        case Contains(column):
            return {column}
        case Compare(_, left, right):
            return expr_columns(left) | expr_columns(right)
        case BoolOp(_, operands):
            return set().union(*(expr_columns(o) for o in operands))
        case _:
            return set()


def _value(expr: Expr, row: Mapping[str, Any]) -> Any:
    match expr:
        case Literal(v):
            return v
        case Column(name):
            return row.get(name)
        case _:
            return _truth(expr, row)


def _truth(expr: Expr, row: Mapping[str, Any]) -> bool:
    match expr:
        case BoolOp("and", operands):
            return all(_truth(o, row) for o in operands)
        case BoolOp("or", operands):
            return any(_truth(o, row) for o in operands)
        case Contains(column, words):
            v = row.get(column)
            return isinstance(v, str) and any(w in v for w in words)
        case Compare(op, left, right):
            return _compare(op, _value(left, row), _value(right, row))
        case _:
            v = _value(expr, row)
            return v is not None and v is not False and v != 0 and v != ""


def _compare(op: str, a: Any, b: Any) -> bool:
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    # 大小比較は、数値どうし・文字列どうしのときだけ(null や型違いは偽)
    both_num = all(isinstance(x, int | float) and not isinstance(x, bool) for x in (a, b))
    both_str = isinstance(a, str) and isinstance(b, str)
    if not (both_num or both_str):
        return False
    return a > b if op == ">" else a < b


def eval_expr(expr: Expr, row: Mapping[str, Any]) -> bool:
    """行(列名 → 値。欠損は `None`)に対して式を評価し、真偽値を返す。

    列が行になければ `None`(欠損)として扱う。
    """
    return _truth(expr, row)
