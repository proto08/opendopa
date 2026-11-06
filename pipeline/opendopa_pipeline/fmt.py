"""数字・日付の日本語表記(docs/data.md §8.5「数字の日本語表記」)。

原稿に出る数字は、すべてここを通す(原稿側で独自に整形しない)。
金額は丸めてよいが、元の値から再計算して誤差 0.5% 以内に収める。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# 金額の表記の誤差の上限(元の値に対する割合)
MAX_MONEY_ERROR = Decimal("0.005")

_MONEY_UNITS: list[tuple[int, str]] = [(10**12, "兆"), (10**8, "億"), (10**4, "万")]
_LOWER_UNIT = {"兆": (10**8, "億"), "億": (10**4, "万"), "万": (1, "")}

_DATETIME = re.compile(
    r"^\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::\d{2})?)?\s*$"
)


def _dec(value: float | int | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _round(x: Decimal, places: str = "1") -> Decimal:
    """四捨五入(0.5 は切り上げ)。"""
    return x.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def format_yen(value: float | int | str | Decimal | None, multiplier: int = 1) -> str | None:
    """金額を「約2兆円」「1,234万円」「9,999円」の形にする。

    `value * multiplier` が円の額(千円の列なら `multiplier=1000`)。
    1万以上は「万」、1億以上は「億」、1兆以上は「兆」。小数は1桁まで。
    1桁の丸めで誤差が 0.5% を超えるとき(1.04億 → 1.0億 など)は、
    「1億400万円」のように下の単位まで書く。丸めたら「約」を付ける。
    """
    if value is None:
        return None
    v = _dec(value) * multiplier
    sign = "マイナス" if v < 0 else ""
    a = abs(v)

    if a < 10_000:
        n = _round(a, "1")
        return sign + ("約" if n != a else "") + f"{int(n):,}円"

    size, unit = next((s, u) for s, u in _MONEY_UNITS if a >= s)
    q = _round(a / size, "0.1")
    # 丸めて次の単位に繰り上がるとき(9999.96万 → 1億)
    for bigger, bunit in reversed(_MONEY_UNITS):
        if bigger > size and q * size >= bigger:
            size, unit = bigger, bunit
            q = _round(a / size, "0.1")
            break
    approx_value = q * size
    if abs(approx_value - a) / a <= MAX_MONEY_ERROR:
        num = f"{int(q):,}" if q == q.to_integral_value() else f"{q:,.1f}"
        return sign + ("約" if approx_value != a else "") + f"{num}{unit}円"

    # 1桁では誤差が大きいので、1つ下の単位まで書く
    lower_size, lower_unit = _LOWER_UNIT[unit]
    hi = int(a // size)
    lo = int(_round((a - hi * size) / lower_size, "1"))
    if lo * lower_size >= size:
        hi, lo = hi + 1, 0
    text = f"{hi:,}{unit}" + (f"{lo:,}{lower_unit}" if lo else "") + "円"
    return sign + ("約" if hi * size + lo * lower_size != a else "") + text


def format_sen_yen(value: float | int | str | Decimal | None) -> str | None:
    """千円の列の値を、円の表記にする。2,008,428,041千円 → 約2兆円。"""
    return format_yen(value, multiplier=1000)


def parse_yen(text: str) -> Decimal:
    """`format_yen` の出力を円の額に戻す(誤差の検査・品質ゲート用)。"""
    s = text.removeprefix("マイナス").removeprefix("約").removesuffix("円")
    sizes = {"兆": 10**12, "億": 10**8, "万": 10**4, "": 1}
    total = Decimal(0)
    for num, unit in re.findall(r"([\d,]+(?:\.\d+)?)(兆|億|万)?", s):
        total += Decimal(num.replace(",", "")) * sizes[unit]
    return -total if text.startswith("マイナス") else total


def format_percent(value: float | int | str | Decimal | None) -> str | None:
    """パーセント。小数1桁まで(12.3456 → 12.3%、12.0 → 12%)。"""
    if value is None:
        return None
    q = _round(_dec(value), "0.1")
    return (f"{int(q)}" if q == q.to_integral_value() else f"{q}") + "%"


def format_rank(value: float | int | None) -> str | None:
    return None if value is None else f"{int(value):,}位"


def format_decimal(value: float | int | str | Decimal | None) -> str | None:
    """小数1桁までの数(3.456 → 3.5、12.0 → 12、1234.5 → 1,234.5)。単位は付けない。"""
    if value is None:
        return None
    q = _round(_dec(value), "0.1")
    return f"{int(q):,}" if q == q.to_integral_value() else f"{q:,}"


def format_count(value: float | int | None) -> str | None:
    return None if value is None else f"{int(value):,}件"


def parse_datetime(value: Any) -> datetime | None:
    """`2022/12/6 11:20` や `1980/3/1` を読む。読めなければ `None`。

    時刻のない値は 0 時 0 分になる(時刻の有無は `format_datetime` が元の文字列で見る)。
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if not isinstance(value, str):
        return None
    m = _DATETIME.match(value)
    if not m:
        return None
    y, mo, d, h, mi = m.groups()
    try:
        return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0))
    except ValueError:
        return None


def format_datetime(value: Any, fmt: str = "ymdhm") -> str | None:
    """日付を日本語にする。

    `ymdhm`: `2022/12/6 11:20` → `2022年12月6日11時20分`(分が 0 なら `11時`)。
    元の値に時刻がなければ `1980年3月1日`。`ymd`: 常に日付まで。
    読めない値は `None`。
    """
    if fmt not in ("ymdhm", "ymd"):
        raise ValueError(f"未知の日付の表示形: {fmt!r}(ymdhm / ymd)")
    dt = parse_datetime(value)
    if dt is None:
        return None
    text = f"{dt.year}年{dt.month}月{dt.day}日"
    has_time = not isinstance(value, str) or bool(_DATETIME.match(value).group(4))  # type: ignore[union-attr]
    if fmt == "ymd" or not has_time:
        return text
    text += f"{dt.hour}時"
    return text + (f"{dt.minute}分" if dt.minute else "")


# 表示形の名前 → 関数。YAML の `fmt:` で選ぶ
FORMATTERS: dict[str, Callable[[Any], str | None]] = {
    "yen": format_yen,
    "sen_yen": format_sen_yen,
    "percent": format_percent,
    "rank": format_rank,
    "count": format_count,
    "decimal": format_decimal,
}


def format_value(kind: str, value: Any) -> str | None:
    """表示形の名前で整形する。値が欠損(`None`・NaN)なら `None`。"""
    try:
        f = FORMATTERS[kind]
    except KeyError:
        raise ValueError(f"未知の表示形: {kind!r}(使えるのは {', '.join(FORMATTERS)})") from None
    if value is None or (isinstance(value, float) and value != value):
        return None
    return f(value)
