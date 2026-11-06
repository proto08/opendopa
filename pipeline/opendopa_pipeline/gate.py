"""品質ゲート(docs/data.md §8.6)。通らない行は `excluded` にして理由を記録する。

各検査は単体で呼べる関数で、問題の説明の一覧(空なら合格)を返す。
`check_all` が行ごとの検査をまとめ、`check_duplicates` が動画をまたぐ重複を調べる。
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from opendopa_pipeline.decider.rules import PII_PATTERNS
from opendopa_pipeline.ingest import is_missing
from opendopa_pipeline.script import MAX_SEC, MIN_SEC

# 推測・責任の追及を示す言い回し。原稿にあれば除外する(設計書 §0.2、docs/data.md §8.6)
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "原因は",
    "原因が",
    "責任は",
    "責任が",
    "のせい",
    "せいで",
    "過失",
    "怠った",
    "おそらく",
    "違いない",
    "疑われ",
    "と推測",
    "と思われ",
)

# 個人情報らしい文字列(電話・メール・番地は decider.rules と共通。氏名と郵便番号を足す)
PII_TEXT_PATTERNS: dict[str, re.Pattern[str]] = {
    **PII_PATTERNS,
    # 氏名らしい文字列: 漢字2〜4字+「氏」「さん」(「同氏」のような1字は対象外)
    "name": re.compile(r"(?<![一-龥々])[一-龥々]{2,4}(?:氏|さん)(?![一-龥々])"),
    "postal": re.compile(r"〒\s*\d{3}-?\d{4}|(?<!\d)\d{3}-\d{4}(?!\d)"),
}

# 負傷の部位・症状を示す語(設計書 §0.2・§15.2「負傷の部位や症状は読まない」)。
# 部位の語は、機体の部品(腕部固定金具、機首部)や別の語(運転手、不足、目的)にも使われる。
# そこで、負傷を示す語と同じ文にあるときだけ、部位とみなす(「機体に接触」は負傷を示さない)。
_BODY_STRICT = re.compile(
    r"顔|鼻|肘|膝|腕|皮膚|頭部|素手|手のひら|手の平|手の甲|足の甲"
    r"|指(?![示定導摘令針標揮])|(?:左|右|両)(?:手|足|目|耳|肩|脚)"
)
_BODY_BROAD = re.compile(
    r"手(?=に|を|が|の)|足(?=に|を|が|の)|目(?=に|を|が)|頭|首|肩|腰|胸|腹|背中"
)
_INJURY_WORD = re.compile(r"負傷|けが|怪我|打撲|裂傷|切創|創傷|傷を負|骨折|出血|挟まれ|巻き込まれ")
_CONTACT_WORD = re.compile(r"接触|当たっ|当たり")
_NOT_BODY = re.compile(r"運転手|相手|選手|助手|不足|満足|補足|充足|機首|機体の首")
_SENTENCE_END = re.compile(r"(?<=[。!?!?])")

FALLBACK_WARN_RATE = 0.30  # 1データセットでフォールバックがこれを超えたら警告

_KANJI_DIGIT = {
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_KANJI_UNIT = {"十": 10, "百": 100, "千": 1000}
# 漢数字は、数を数える語の前にあるものだけを数字として扱う(「一部」「万一」を数字にしない)
_COUNTERS = "件人機年月日時分秒円台隻本回号位名個"
_KANJI_NUM = re.compile(f"[〇一二三四五六七八九十百千]+(?=[{_COUNTERS}])")
_ARABIC_NUM = re.compile(r"\d+(?:\.\d+)?")
_COMMA = re.compile(r"(?<=\d),(?=\d)")


def kanji_to_int(text: str) -> int | None:
    """漢数字を整数にする(三十二 → 32、二〇二二 → 2022)。読めなければ `None`。"""
    if not text:
        return None
    if all(c in _KANJI_DIGIT for c in text):  # 位取りなし(二〇二二)
        return int("".join(str(_KANJI_DIGIT[c]) for c in text))
    total, cur = 0, 0
    for c in text:
        if c in _KANJI_DIGIT:
            cur = _KANJI_DIGIT[c]
        elif c in _KANJI_UNIT:
            total += (cur or 1) * _KANJI_UNIT[c]
            cur = 0
        else:
            return None
    return total + cur


def extract_numbers(text: str) -> list[str]:
    """文に出る数字を、正規化した文字列で取り出す。

    全角は半角に、桁区切り(1,234)は取り、先頭の 0 と小数の末尾の 0 は落とす
    (`007` → `7`、`1.50` → `1.5`)。数を数える語の前の漢数字も数字として読む。
    """
    s = _COMMA.sub("", unicodedata.normalize("NFKC", text))
    out = [_norm_num(m) for m in _ARABIC_NUM.findall(s)]
    for m in _KANJI_NUM.findall(s):
        n = kanji_to_int(m)
        if n is not None:
            out.append(str(n))
    return out


def _norm_num(s: str) -> str:
    if "." in s:
        whole, frac = s.split(".", 1)
        frac = frac.rstrip("0")
        return (str(int(whole)) + "." + frac) if frac else str(int(whole))
    return str(int(s))


def _flat(v: Any) -> Iterable[str]:
    if is_missing(v):
        return
    if isinstance(v, list | tuple):
        for x in v:
            yield from _flat(x)
    else:
        yield str(v)


def allowed_numbers(row: Mapping[str, Any], numbers: Sequence[Mapping[str, Any]] = ()) -> set[str]:
    """原稿に出てよい数字: 元の行の値(`derived` / `stats` の列を含む)と、`numbers` の記録。"""
    allowed: set[str] = set()
    for v in row.values():
        for s in _flat(v):
            allowed.update(extract_numbers(s))
    for rec in numbers:
        for key in ("display", "value", "inputs"):
            val = rec.get(key)
            vals = val.values() if isinstance(val, Mapping) else [val]
            for x in vals:
                for s in _flat(x):
                    allowed.update(extract_numbers(s))
    return allowed


# ---- 行ごとの検査(問題の説明の一覧を返す。空なら合格) ----


def check_unreplaced(lines: Sequence[str]) -> list[str]:
    """穴が残っていない(`{` `}` がない)。"""
    return [f"穴が残っています: {x}" for x in lines if "{" in x or "}" in x]


def check_numbers(
    lines: Sequence[str],
    row: Mapping[str, Any],
    numbers: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    """原稿に出る数字が、すべて `numbers` か元の行の値のどれかと一致する。"""
    allowed = allowed_numbers(row, numbers)
    bad = sorted({n for x in lines for n in extract_numbers(x)} - allowed)
    return [f"元データにない数字: {n}" for n in bad]


def check_required(required: Sequence[str], row: Mapping[str, Any]) -> list[str]:
    """YAML の `required` の列が空でない。"""
    return [f"必須の列が空: {c}" for c in required if is_missing(row.get(c))]


def check_length(duration_sec: float, lo: float = MIN_SEC, hi: float = MAX_SEC) -> list[str]:
    """推定秒数が 15〜30 秒に入る。"""
    if lo - 1e-6 <= duration_sec <= hi + 1e-6:
        return []
    return [f"推定秒数が範囲外: {duration_sec:.1f}秒(許容 {lo:g}〜{hi:g}秒)"]


def check_pii(lines: Sequence[str]) -> list[str]:
    """氏名・電話・メール・番地・郵便番号らしい文字列がない。"""
    text = "\n".join(lines)
    return [f"個人情報らしい文字列({k})" for k, p in PII_TEXT_PATTERNS.items() if p.search(text)]


def check_forbidden(lines: Sequence[str]) -> list[str]:
    """「原因は」「責任は」「〜のせい」など、推測を示す言い回しがない。"""
    text = "".join(lines)
    return [f"禁止表現: {w}" for w in FORBIDDEN_PHRASES if w in text]


def check_casualty_detail(lines: Sequence[str]) -> list[str]:
    """負傷の部位・症状(顔、指、骨折など)が原稿に出ていない(設計書 §15.2)。

    負傷を示す語と同じ文に部位の語があるとき、または部位の語のすぐ後ろ(8字以内)に
    「接触」があるとき(「左腕に接触し」)、不合格にする。
    """
    found: list[str] = []
    for line in lines:
        for sentence in _SENTENCE_END.split(line):
            plain = _NOT_BODY.sub("", sentence)
            strict = _BODY_STRICT.search(plain)
            hit = None
            if _INJURY_WORD.search(plain):
                hit = strict or _BODY_BROAD.search(plain)
            elif strict and _CONTACT_WORD.search(plain[strict.end() : strict.end() + 8]):
                hit = strict
            if hit is not None:
                found.append(f"負傷の部位・症状: {hit.group()}")
    return list(dict.fromkeys(found))


def check_decisions(decisions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """判断で除外になった行(`pii` の確率が上限を超えた行など)。"""
    return [f"判断 {did} で除外" for did, rec in decisions.items() if rec.get("excluded")]


def script_text_key(lines: Sequence[str]) -> str:
    """重複の判定に使う原稿の文字列(空白の違いは無視する)。"""
    return re.sub(r"\s+", "", "".join(lines))


def check_duplicates(texts: Iterable[str | None]) -> list[bool]:
    """原稿の列に対して、先に出たものと同じ原稿なら `True`(2本目以降を除外する)。

    `None`(原稿がない行)は `False`。
    """
    seen: set[str] = set()
    out: list[bool] = []
    for t in texts:
        if t is None:
            out.append(False)
        elif t in seen:
            out.append(True)
        else:
            seen.add(t)
            out.append(False)
    return out


def check_all(
    *,
    lines: Sequence[str],
    duration_sec: float,
    row: Mapping[str, Any],
    numbers: Sequence[Mapping[str, Any]],
    required: Sequence[str],
    extra_texts: Sequence[str] = (),
) -> dict[str, list[str]]:
    """行ごとの検査をまとめて実行する。不合格の検査だけ、理由コード → 説明の一覧で返す。

    `extra_texts` は字幕以外の表示文(見出し・チップ・コメント)。負傷の部位の検査だけに足す。
    """
    results = {
        "missing": check_required(required, row),
        "unreplaced": check_unreplaced(lines),
        "number_mismatch": check_numbers(lines, row, numbers),
        "length": check_length(duration_sec),
        "pii": check_pii(lines),
        "forbidden": check_forbidden(lines),
        "casualty_detail": check_casualty_detail([*lines, *extra_texts]),
    }
    return {k: v for k, v in results.items() if v}


# ---- 結果のまとめ ----


def summarize(secs: Sequence[float]) -> dict[str, float | None]:
    """推定秒数の最小・中央・最大。"""
    if not secs:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(min(secs), 2),
        "median": round(statistics.median(secs), 2),
        "max": round(max(secs), 2),
    }


def count_reasons(reasons: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(reasons).items(), key=lambda kv: (-kv[1], kv[0])))
