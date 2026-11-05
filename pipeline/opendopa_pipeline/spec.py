"""列定義 YAML(`datasets/<id>.yaml`)のモデルとローダ(docs/data.md §8.3)。

`derived` / `stats` の `op` の実装、穴埋め、判断はここに含めない(#30、#33、#32)。
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from opendopa_pipeline.expr import ExprError, expr_columns, parse_expr

_HOLE = re.compile(r"\{([^{}]+)\}")
_TYPE_COUNT_RANGE = range(4, 7)


def parse_comment_rule(rule: str) -> list[tuple[str | None, str]]:
    """`comments.rule` を、(式 or None, プール名)の一覧にする。

    書き方: `式 -> プール名; 式 -> プール名; else プール名`。プール名 `none` はコメントなし。
    `;` と `->` は区切りなので、式の中の文字列には使えない。
    """
    if not isinstance(rule, str) or not rule.strip():
        raise ValueError("空です")
    out: list[tuple[str | None, str]] = []
    for clause in (c.strip() for c in rule.split(";")):
        if not clause:
            continue
        if clause.startswith("else "):
            out.append((None, clause.removeprefix("else ").strip()))
        elif "->" in clause:
            expr, pool = clause.rsplit("->", 1)
            out.append((expr.strip(), pool.strip()))
        else:
            raise ValueError(f"{clause!r} は `式 -> プール名` か `else プール名` の形です")
    if not out or any(not pool for _, pool in out):
        raise ValueError("プール名がありません")
    return out


class DatasetError(ValueError):
    """列定義 YAML の誤り。どのファイルのどこが悪いかをメッセージに含める。"""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FileFilter(_Model):
    col: str
    not_null: bool = True


class Derived(BaseModel):
    """`derived` の1項目。`op` ごとの引数は #30 で解釈するので、余分なキーを残す。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_: str | None = Field(default=None, alias="from")
    op: str


class Stat(BaseModel):
    """`stats` の1項目。`op` ごとの引数は #30 で解釈する。"""

    model_config = ConfigDict(extra="allow")

    name: str
    op: str
    # 指定すると、`<name>_text` の列に、この表示形(fmt.py の FORMATTERS)の文字列も作る
    fmt: str | None = None


class Select(_Model):
    cap: int | None = None
    order_by: str | None = None
    filters: list[FileFilter | str] = []
    score: list[dict[str, Any]] = []
    diversify_by: list[str] | str | None = None
    seed: int | None = None


class BigNumber(_Model):
    text: str
    unit: str = ""
    label: str
    when: str | None = None


class BigNumberSet(_Model):
    primary: BigNumber
    fallback: BigNumber | None = None


class MapPlace(_Model):
    """地図の1地点。名前は穴を含む文、緯度経度は列名。"""

    name: str
    lat: str
    lon: str


class MapSpec(_Model):
    """シーンの `map` の作り方。`route` は from / to、`points` は points を使う(polygon は #56)。"""

    type: Literal["route", "points"]
    from_: MapPlace | None = Field(default=None, alias="from")
    to: MapPlace | None = None
    points: list[MapPlace] = []

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _check_shape(self) -> MapSpec:
        if self.type == "route" and (self.from_ is None or self.to is None):
            raise ValueError("map: route には from と to が必要です")
        if self.type == "points" and not self.points:
            raise ValueError("map: points には points が必要です")
        return self

    def places(self) -> list[MapPlace]:
        return [p for p in (self.from_, self.to, *self.points) if p is not None]


class Line(_Model):
    text: str
    optional: bool = False


class Template(_Model):
    id: str
    short: bool = False
    lines: list[Line]

    @model_validator(mode="before")
    @classmethod
    def _normalize_lines(cls, data: Any) -> Any:
        # 文字列の行は、必須の行 `{text: ..., optional: false}` に直す
        if isinstance(data, dict) and isinstance(data.get("lines"), list):
            data = {
                **data,
                "lines": [{"text": x} if isinstance(x, str) else x for x in data["lines"]],
            }
        return data


class TemplateGroup(_Model):
    id: str
    label: str
    templates: list[Template]


class TemplateSelect(_Model):
    decision: str


class Decision(_Model):
    id: str
    kind: Literal["choice", "noul"]
    question: str
    state: list[str] = []
    options_from: str | None = None
    min_confidence: float | None = None
    exclude_if_probability_above: float | None = None
    fallback: dict[str, Any] | None = None


class FallbackRule(_Model):
    if_: str | None = Field(default=None, alias="if")
    then: str | None = None
    else_: str | None = Field(default=None, alias="else")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _check_shape(self) -> FallbackRule:
        if self.else_ is not None:
            if self.if_ is not None or self.then is not None:
                raise ValueError("else の規則に if / then は書けません")
        elif self.if_ is None or self.then is None:
            raise ValueError("規則は {if, then} または {else} のどちらかです")
        return self


class DatasetDef(_Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    label: str
    source_name: str
    wm_char: str = Field(min_length=1, max_length=1)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    files: list[str]
    grain: Literal["row", "group"]
    # grain: group のとき、group_by の列で集計して 1 グループ = 1 行にする。
    # aggregate は 列名 → sum / mean / min / max / first / count
    group_by: list[str] = []
    aggregate: dict[str, Literal["sum", "mean", "min", "max", "first", "count"]] = {}
    rename: dict[str, str] = {}
    null_values: list[str] = []
    zero_is_null: list[str] = []
    filters: list[FileFilter | str] = []
    derived: dict[str, Derived] = {}
    stats: list[Stat] = []
    select: Select = Select()
    big_number: BigNumberSet
    template_groups: list[TemplateGroup]
    template_select: TemplateSelect | None = None
    decisions: list[Decision] = []
    fallback_rules: dict[str, list[FallbackRule]] = {}
    comments: dict[str, Any] = {}
    embed_text: str
    required: list[str] = []
    # シーンの組み立て(#33)。いずれも省略可
    kind: Literal["event", "stat", "geo"] | None = None  # 省略は grain: row → event、group → stat
    headline: str | None = None  # 穴を含む文。省略は先頭の字幕の最初の文(40字以内)
    chips: list[str] = []  # 特徴の小さなラベル(穴を含む文。穴が空のものは省く)
    sparkline: str | None = None  # `series` の stat の名前
    map: MapSpec | None = None
    # 元の行を `csv_row` に出すとき、除く列(個人に関わる列など。設計書 §15.2)
    hide: list[str] = []

    # 読み込み元(エラーメッセージ用。YAML のキーではない)
    source_path: Path | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _check_structure(self) -> DatasetDef:
        errors: list[str] = []

        seen: set[str] = set()
        for g in self.template_groups:
            if g.id in seen:
                errors.append(f"template_groups: 型の id {g.id!r} が重複しています")
            seen.add(g.id)
            tids = [t.id for t in g.templates]
            if len(set(tids)) != len(tids):
                errors.append(f"型 {g.id!r}: テンプレートの id が重複しています")
            if not any(t.short for t in g.templates):
                errors.append(f"型 {g.id!r}: short: true のテンプレートが1つ必要です")

        if not self.template_groups:
            errors.append("template_groups が空です")
        elif len(self.template_groups) not in _TYPE_COUNT_RANGE:
            warnings.warn(
                f"{self._where()}: 型の数が {len(self.template_groups)} です"
                "(目安は4〜6。docs/data.md §8.3.1)",
                stacklevel=2,
            )

        if self.grain == "group" and not self.group_by:
            errors.append("grain: group には group_by が必要です")
        if self.grain == "row" and (self.group_by or self.aggregate):
            errors.append("group_by / aggregate は grain: group のときだけ使えます")

        for name in self.derived:
            if not name.isidentifier():
                errors.append(f"derived: 名前 {name!r} は英数字と _ だけにしてください")

        errors += self._check_exprs()
        errors += self._check_references()

        if errors:
            raise ValueError("\n".join(errors))
        return self

    def _where(self) -> str:
        return str(self.source_path) if self.source_path else f"データセット {self.id}"

    def defined_names(self) -> set[str]:
        """`derived` と `stats` で作る名前(列名以外に、穴・式で使える名前)。"""
        names = set(self.derived) | {s.name for s in self.stats}
        return names | {f"{s.name}_text" for s in self.stats if s.fmt}

    def exprs(self) -> list[tuple[str, str]]:
        """YAML 中の式を、(場所, 式) の一覧で返す。"""
        out: list[tuple[str, str]] = []
        for i, f in enumerate(self.filters):
            if isinstance(f, str):
                out.append((f"filters[{i}]", f))
        for i, f in enumerate(self.select.filters):
            if isinstance(f, str):
                out.append((f"select.filters[{i}]", f))
        for label, bn in (
            ("primary", self.big_number.primary),
            ("fallback", self.big_number.fallback),
        ):
            if bn is not None and bn.when is not None:
                out.append((f"big_number.{label}.when", bn.when))
        for name, rules in self.fallback_rules.items():
            for i, r in enumerate(rules):
                if r.if_ is not None:
                    out.append((f"fallback_rules.{name}[{i}].if", r.if_))
        rule = self.comments.get("rule")
        if rule is not None:
            try:
                clauses = parse_comment_rule(rule)
            except ValueError:
                clauses = []  # 形の誤りは _check_exprs が報告する
            out += [(f"comments.rule[{i}]", c) for i, (c, _) in enumerate(clauses) if c]
        return out

    def texts(self) -> list[tuple[str, str]]:
        """穴を含みうる文を、(場所, 文) の一覧で返す。テンプレートの行は除く。"""
        out = [("embed_text", self.embed_text)]
        if self.headline is not None:
            out.append(("headline", self.headline))
        out += [(f"chips[{i}]", c) for i, c in enumerate(self.chips)]
        if self.map is not None:
            out += [(f"map {p.name}", p.name) for p in self.map.places()]
        for label, bn in (
            ("primary", self.big_number.primary),
            ("fallback", self.big_number.fallback),
        ):
            if bn is not None:
                out += [
                    (f"big_number.{label}.text", bn.text),
                    (f"big_number.{label}.label", bn.label),
                ]
        return out

    def _check_exprs(self) -> list[str]:
        errors = []
        rule = self.comments.get("rule")
        if rule is not None:
            try:
                parse_comment_rule(rule)
            except ValueError as e:
                errors.append(f"comments.rule: {e}")
        for where, text in self.exprs():
            try:
                parse_expr(text)
            except ExprError as e:
                errors.append(f"{where}: {e}")
        return errors

    def _check_references(self) -> list[str]:
        errors = []
        type_ids = {g.id for g in self.template_groups}
        decision_ids = {d.id for d in self.decisions}
        if self.template_select and self.template_select.decision not in decision_ids:
            errors.append(
                f"template_select.decision: 判断 {self.template_select.decision!r} が"
                " decisions にありません"
            )
        for name, rules in self.fallback_rules.items():
            for i, r in enumerate(rules):
                target = r.then if r.then is not None else r.else_
                if target not in type_ids:
                    errors.append(
                        f"fallback_rules.{name}[{i}]: 型 {target!r} が template_groups にありません"
                    )
        if self.sparkline is not None and self.sparkline not in {s.name for s in self.stats}:
            errors.append(f"sparkline: stat {self.sparkline!r} が stats にありません")
        for d in self.decisions:
            if d.options_from not in (None, "template_groups"):
                errors.append(f"decisions[{d.id}].options_from: template_groups のみ使えます")
        return errors

    def holes(self) -> list[tuple[str, str]]:
        """穴の使用箇所を、(場所, 穴の名前) の一覧で返す。場所はエラーメッセージ用。"""
        out = [(w, h) for w, text in self.texts() for h in _HOLE.findall(text)]
        for g in self.template_groups:
            for t in g.templates:
                for n, line in enumerate(t.lines, start=1):
                    out += [
                        (f"型 {g.id!r} のテンプレート {t.id!r} の{n}行目", h)
                        for h in _HOLE.findall(line.text)
                    ]
        return out


def validate_against_columns(dataset: DatasetDef, columns: list[str] | set[str]) -> None:
    """穴・式・`required` などが使う列名が、データにあるかを検査する。

    `columns` は `rename` 適用後の列名。`derived` / `stats` の名前も、列名と同じように使える。
    未定義の名前があれば、ファイルパス・場所つきの `DatasetError`。
    """
    known = set(columns) | dataset.defined_names()
    if dataset.grain == "group":
        known.add("n_rows")  # グループ集計で足す、元の行数の列
    errors = []

    for where, hole in dataset.holes():
        if hole not in known:
            errors.append(f"{where}: 穴 {{{hole}}} は、列にも derived / stats にもありません")

    for where, text in dataset.exprs():
        for col in sorted(expr_columns(parse_expr(text)) - known):
            errors.append(f"{where}: 式が使う {col!r} は、列にも derived / stats にもありません")

    cols = set(columns)
    if dataset.map is not None:
        for p in dataset.map.places():
            for col in (p.lat, p.lon):
                if col not in known:
                    errors.append(f"map: 列 {col!r} は、列にも derived / stats にもありません")
    for name, d in dataset.derived.items():
        if d.from_ is not None and d.from_ not in cols:
            errors.append(f"derived.{name}.from: 列 {d.from_!r} がありません")
    # grain: group の集計は、derived を作った後・stats の前に行う
    after_derive = cols | set(dataset.derived)
    for col in [*dataset.group_by, *dataset.aggregate]:
        if col not in after_derive:
            errors.append(f"group_by / aggregate: 列 {col!r} がありません")
    for col in dataset.required:
        if col not in known:
            errors.append(f"required: {col!r} は、列にも derived / stats にもありません")
    for i, f in enumerate(dataset.filters):
        if isinstance(f, FileFilter) and f.col not in cols:
            errors.append(f"filters[{i}]: 列 {f.col!r} がありません")

    if errors:
        raise DatasetError(f"{dataset._where()}:\n" + "\n".join(f"  {e}" for e in errors))


def _format_validation_error(path: Path, e: ValidationError) -> str:
    lines = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(トップレベル)"
        msg = err["msg"].removeprefix("Value error, ")
        lines.append(f"  {loc}: {msg}")
    return f"{path}:\n" + "\n".join(lines)


def load_dataset(path: str | Path, columns: list[str] | set[str] | None = None) -> DatasetDef:
    """`datasets/<id>.yaml` を読み、検証して返す。

    読み込み時に、スキーマ・式の構文・型の構成(`short: true`)を検査する。
    `columns`(`rename` 後の列名)を渡すと、穴や式の列名も続けて検査する
    (渡さないときは、データ読み込み後に `validate_against_columns` を呼ぶ)。
    """
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as e:
        raise DatasetError(f"{path}: 読み込めません: {e}") from e
    except yaml.YAMLError as e:
        raise DatasetError(f"{path}: YAML として読めません: {e}") from e
    if not isinstance(raw, dict):
        raise DatasetError(f"{path}: トップレベルはマッピングにしてください")

    raw["source_path"] = path
    try:
        dataset = DatasetDef.model_validate(raw)
    except ValidationError as e:
        raise DatasetError(_format_validation_error(path, e)) from e

    if columns is not None:
        validate_against_columns(dataset, columns)
    return dataset
