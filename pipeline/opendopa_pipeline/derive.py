"""`derived`: 穴に入れる値を、元の列から機械的に作る(docs/data.md §8.3)。

op はレジストリ方式。データセットを足すときに op が足りなければ、`@derive_op("名前")` で
関数を足すだけでよい。LLM は使わない。元の文は書き換えず、そのまま使う。
未知の op はエラー。元の値が欠損なら、結果も欠損(`classify` だけは `else` に入る)。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pandas as pd

from opendopa_pipeline.decider.rules import PII_PATTERNS
from opendopa_pipeline.fmt import FORMATTERS, format_datetime, format_value, parse_datetime
from opendopa_pipeline.ingest import is_missing
from opendopa_pipeline.spec import DatasetDef, Derived


class DeriveError(ValueError):
    """derived の定義の誤り(未知の op、引数の不足など)。"""


# op の関数: (元の列の Series, derived の定義) → 結果の Series(同じ index)。
# `frame=True` で登録した op は、第3引数に DataFrame 全体も受け取る(別の列を見る op 用)
DeriveOp = Callable[..., pd.Series]
_OPS: dict[str, DeriveOp] = {}
_FRAME_OPS: set[str] = set()


def derive_op(name: str, *, frame: bool = False) -> Callable[[DeriveOp], DeriveOp]:
    def deco(fn: DeriveOp) -> DeriveOp:
        _OPS[name] = fn
        if frame:
            _FRAME_OPS.add(name)
        return fn

    return deco


def known_derive_ops() -> list[str]:
    return sorted(_OPS)


def _arg(d: Derived, key: str, default: Any = ...) -> Any:
    extra = d.model_extra or {}
    if key in extra:
        return extra[key]
    if default is ...:
        raise DeriveError(f"op {d.op!r} には {key!r} が必要です")
    return default


def _map_non_null(col: pd.Series, f: Callable[[Any], Any]) -> pd.Series:
    return pd.Series([None if is_missing(v) else f(v) for v in col], index=col.index, dtype=object)


@derive_op("format_datetime")
def _format_datetime(col: pd.Series, d: Derived) -> pd.Series:
    fmt = _arg(d, "fmt", "ymdhm")
    format_datetime("2000/1/1", fmt)  # fmt の誤りを、行を処理する前に見つける
    return _map_non_null(col, lambda v: format_datetime(v, fmt))


_PAREN = re.compile(r"[（(][^（）()]*[）)]")


def strip_parenthesis(text: str) -> str:
    """括弧(全角・半角。入れ子も)とその中身を取り除く。"""
    prev = None
    while prev != text:
        prev, text = text, _PAREN.sub("", text)
    return text.strip()


@derive_op("strip_parenthesis")
def _strip_parenthesis(col: pd.Series, d: Derived) -> pd.Series:
    return _map_non_null(col, lambda v: strip_parenthesis(str(v)) or None)


PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 "
    "神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 "
    "大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 "
    "福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()
_PREF = re.compile("^(" + "|".join(PREFECTURES) + ")")


def extract_pref(text: str) -> str | None:
    """先頭の都道府県名。先頭にないとき(海外の長い文など)は `None`。"""
    m = _PREF.match(text.strip())
    return m.group(1) if m else None


@derive_op("extract_pref")
def _extract_pref(col: pd.Series, d: Derived) -> pd.Series:
    return _map_non_null(col, lambda v: extract_pref(str(v)))


@derive_op("classify")
def _classify(col: pd.Series, d: Derived) -> pd.Series:
    rules = _arg(d, "rules")
    contains = [(r["contains"], r["value"]) for r in rules if "contains" in r]
    others = [r["else"] for r in rules if "else" in r]
    if len(others) != 1:
        raise DeriveError("classify の rules には、else を1つだけ書いてください")
    else_value = others[0]

    def classify(v: Any) -> Any:
        text = "" if is_missing(v) else str(v)
        return next((value for word, value in contains if word in text), else_value)

    return pd.Series([classify(v) for v in col], index=col.index, dtype=object)


_SENTENCE = re.compile(r"[^。！？]*[。！？]+[」』）)]*|[^。！？]+$")


def sentences(text: str) -> list[str]:
    """文に分ける(`。` `！` `？` の後ろで切る)。元の文字は変えない(前後の空白だけ除く)。"""
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


@derive_op("sentence")
def _sentence(col: pd.Series, d: Derived) -> pd.Series:
    n = _arg(d, "n")
    if not isinstance(n, int) or n < 1:
        raise DeriveError("sentence の n は 1 以上の整数です")

    def nth(v: Any) -> str | None:
        parts = sentences(str(v))
        return parts[n - 1] if len(parts) >= n else None

    return _map_non_null(col, nth)


@derive_op("map")
def _map(col: pd.Series, d: Derived) -> pd.Series:
    mapping = {str(k): v for k, v in _arg(d, "map").items()}
    else_value = _arg(d, "else", None)
    return _map_non_null(col, lambda v: mapping.get(str(v), else_value))


def _frame_col(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        raise DeriveError(f"列 {name!r} がありません")
    return df[name]


@derive_op("format", frame=True)
def _format(col: pd.Series, d: Derived, df: pd.DataFrame) -> pd.Series:
    """数値を日本語の表記(fmt.py の FORMATTERS)にする。`fmt: yen | sen_yen | percent | ...`

    `prefix_if: {col: 列, contains: 語, prefix: 文字}` を付けると、その列に語が含まれる行だけ、
    表記の前に文字を足す(賃貸の金額に「月」を付ける、など)。
    """
    fmt = _arg(d, "fmt")
    if fmt not in FORMATTERS:
        raise DeriveError(f"format の fmt {fmt!r} は未知です(使えるのは {', '.join(FORMATTERS)})")
    out = _map_non_null(col, lambda v: format_value(fmt, v))
    cond = _arg(d, "prefix_if", None)
    if cond is None:
        return out
    flag = _frame_col(df, cond["col"])
    prefix = [
        cond["prefix"] if (not is_missing(f) and cond["contains"] in str(f)) else "" for f in flag
    ]
    return pd.Series(
        [None if is_missing(v) else p + v for p, v in zip(prefix, out, strict=True)],
        index=col.index,
        dtype=object,
    )


@derive_op("pct_diff", frame=True)
def _pct_diff(col: pd.Series, d: Derived, df: pd.DataFrame) -> pd.Series:
    """`(元の列 - against) ÷ 元の列 × 100`(%)。両方が正のときだけ。

    `fmt: percent` を付けると表記の文字列(「12.3%」)にする。`only_positive: true` なら、
    結果が 0 以下の行は欠損にする(「◯%下がった」と言えるときだけ使うため)。
    """
    other = _frame_col(df, _arg(d, "against"))
    fmt = _arg(d, "fmt", None)
    if fmt is not None and fmt not in FORMATTERS:
        raise DeriveError(f"pct_diff の fmt {fmt!r} は未知です(使えるのは {', '.join(FORMATTERS)})")
    only_positive = bool(_arg(d, "only_positive", False))

    def one(a: Any, b: Any) -> Any:
        if is_missing(a) or is_missing(b):
            return None
        try:
            x, y = float(a), float(b)
        except (TypeError, ValueError):
            return None
        if x <= 0 or y <= 0:
            return None
        pct = (x - y) / x * 100
        if only_positive and pct <= 0:
            return None
        return format_value(fmt, pct) if fmt else pct

    return pd.Series(
        [one(a, b) for a, b in zip(col, other, strict=True)], index=col.index, dtype=object
    )


@derive_op("ensure_suffix")
def _ensure_suffix(col: pd.Series, d: Derived) -> pd.Series:
    """文字列の末尾が `suffix` でなければ足す(「石動」→「石動駅」。「佐伯駅」はそのまま)。"""
    suffix = _arg(d, "suffix")
    return _map_non_null(
        col,
        lambda v: (
            (str(v).strip() if str(v).strip().endswith(suffix) else str(v).strip() + suffix)
            if str(v).strip()
            else None
        ),
    )


@derive_op("year_of")
def _year_of(col: pd.Series, d: Derived) -> pd.Series:
    """日付の年を文字列にする(`suffix: 年築` なら「1976年築」)。読めない日付は欠損。"""
    suffix = _arg(d, "suffix", "年")

    def year(v: Any) -> str | None:
        dt = parse_datetime(v)
        return None if dt is None else f"{dt.year}{suffix}"

    return _map_non_null(col, year)


@derive_op("years_since")
def _years_since(col: pd.Series, d: Derived) -> pd.Series:
    """日付の年から `as_of_year` までの年数(築年数)。1 未満・`max` を超える値は欠損。

    今の年を使うと実行のたびに値が変わるので、基準の年は YAML に書く。
    """
    as_of = _arg(d, "as_of_year")
    if not isinstance(as_of, int):
        raise DeriveError("years_since の as_of_year は整数です")
    upper = _arg(d, "max", 150)

    def years(v: Any) -> int | None:
        dt = parse_datetime(v)
        if dt is None:
            return None
        n = as_of - dt.year
        return n if 1 <= n <= upper else None

    return _map_non_null(col, years)


@derive_op("flag_present")
def _flag_present(col: pd.Series, d: Derived) -> pd.Series:
    """値があれば 1、なければ 0(選定の点数に加点するための数値)。"""
    return pd.Series([0 if is_missing(v) else 1 for v in col], index=col.index, dtype=object)


# 自由記述の文を、読み上げに使えるか判定するための語(広告・屋号・問い合わせの定型)
AD_KEYWORDS = tuple(
    """
    株式会社 有限会社 合同会社 (株) （株） ㈱ (有) （有） ㈲ 不動産
    ハウス ホーム 建設 工務店 商事 住宅販売 宅建 協会 お問い合わせ
    お問合せ 問合せ 問い合せ お電話 電話 ＴＥＬ TEL ＦＡＸ FAX
    メール お気軽 ご連絡 連絡 内覧 内見 見学 ご相談 御相談 ご案内 詳細
    空き家バンク 空家バンク 空き家情報 ホームページ ＨＰ ＵＲＬ URL
    http www. 仲介 担当 取扱 登録 物件番号 ご紹介 おすすめ お勧め
    〒
    """.split()
)
_AD_PUNCT = re.compile(r"[！!]{2,}")  # 「！」の連続は広告の言い回しとして使わない
_STRIP_SYMBOLS = re.compile(r"[♪♬♡♥☆★◎]")
_LEADING_MARK = re.compile(r"^[\s・•●■◆◇□○▲△▼▽◎※①-⑩\-ー―]+")
_DIGIT = re.compile(r"[0-9０-９]")
_BRACKETS = re.compile(r"[【】「」『』〈〉《》※]")


def clean_free_sentence(text: str, max_chars: int = 40) -> str | None:
    """自由記述から、読み上げに使える最初の1文を取り出す。使えなければ `None`。

    ①広告・屋号・問い合わせの定型、個人情報らしい文字列(電話・メール・番地)、URL、括弧書きの
    固有名詞を含む文は使わない ②記号(♪♡★など)は取り除く ③最初の1文だけ、`max_chars` 字以内
    ④数字を含む文は使わない(自由記述の数字は、単位や時点を確かめられず、元データの列とも
    ずれうるため)。最初の1文が使えないとき、2文目以降には進まない。
    """
    text = str(text)
    if any(p.search(text) for p in PII_PATTERNS.values()):
        return None  # 記述のどこかに個人情報らしい文字列があれば、その記述は使わない
    # 改行は文の切れ目として扱い、最初の行の記号(箇条書きの印)を除いてから、1文目を取る
    lines = [ln.replace("\u3000", " ").strip() for ln in re.split(r"[\r\n]+", text)]
    line = next((_LEADING_MARK.sub("", ln) for ln in lines if _LEADING_MARK.sub("", ln)), "")
    first = sentences(line)
    if not first:
        return None
    s = first[0]
    if _AD_PUNCT.search(s):
        return None
    s = _STRIP_SYMBOLS.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = _LEADING_MARK.sub("", s)
    if not s or len(s) > max_chars:
        return None
    if _DIGIT.search(s) or _BRACKETS.search(s) or any(w in s for w in AD_KEYWORDS):
        return None
    return s


@derive_op("free_sentence")
def _free_sentence(col: pd.Series, d: Derived) -> pd.Series:
    """自由記述の最初の1文(`clean_free_sentence`)。`max_chars`(既定 40)。"""
    n = _arg(d, "max_chars", 40)
    return _map_non_null(col, lambda v: clean_free_sentence(str(v), n))


def derive(df: pd.DataFrame, dataset: DatasetDef) -> pd.DataFrame:
    """`derived` の列を足した新しい DataFrame を返す(元の DataFrame は変えない)。"""
    out = df.copy()
    for name, d in dataset.derived.items():
        op = _OPS.get(d.op)
        if op is None:
            raise DeriveError(
                f"derived.{name}: 未知の op {d.op!r}(使えるのは {', '.join(known_derive_ops())})"
            )
        if name in df.columns:
            raise DeriveError(f"derived.{name}: 同じ名前の列が元データにあります")
        if d.from_ is None:
            raise DeriveError(f"derived.{name}: from が必要です")
        if d.from_ not in df.columns:
            raise DeriveError(f"derived.{name}: 列 {d.from_!r} がありません")
        try:
            out[name] = op(df[d.from_], d, df) if d.op in _FRAME_OPS else op(df[d.from_], d)
        except DeriveError as e:
            raise DeriveError(f"derived.{name}: {e}") from e
    return out
