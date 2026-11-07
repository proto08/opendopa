"""ハッシュタグ(docs/hashtag_design.md §3)。元データから機械的に作る。LLM は使わない。

- データ種別のタグ: `datasets/<id>.yaml` の `tag:`(表示名)。ID の slug は `DATASET_TAG_SLUGS` で引く
- 地域のタグ: `region_from:` の列の値から、都道府県の正規化表(`PREFECTURE_TABLE`)で引く。
  取れない行は地域タグを付けない(元データにない地名を作らない)
"""

import math
import re
from collections.abc import Mapping
from typing import Any, NamedTuple


class Prefecture(NamedTuple):
    name: str  # 正式名称(北海道・東京都・京都府・大阪府・その他は県)
    slug: str
    yomi: str  # かな。検索用


# 並びは JIS X 0401 の順。`sort` はこの順に付ける
PREFECTURE_TABLE: tuple[Prefecture, ...] = (
    Prefecture("北海道", "hokkaido", "ほっかいどう"),
    Prefecture("青森県", "aomori", "あおもりけん"),
    Prefecture("岩手県", "iwate", "いわてけん"),
    Prefecture("宮城県", "miyagi", "みやぎけん"),
    Prefecture("秋田県", "akita", "あきたけん"),
    Prefecture("山形県", "yamagata", "やまがたけん"),
    Prefecture("福島県", "fukushima", "ふくしまけん"),
    Prefecture("茨城県", "ibaraki", "いばらきけん"),
    Prefecture("栃木県", "tochigi", "とちぎけん"),
    Prefecture("群馬県", "gunma", "ぐんまけん"),
    Prefecture("埼玉県", "saitama", "さいたまけん"),
    Prefecture("千葉県", "chiba", "ちばけん"),
    Prefecture("東京都", "tokyo", "とうきょうと"),
    Prefecture("神奈川県", "kanagawa", "かながわけん"),
    Prefecture("新潟県", "niigata", "にいがたけん"),
    Prefecture("富山県", "toyama", "とやまけん"),
    Prefecture("石川県", "ishikawa", "いしかわけん"),
    Prefecture("福井県", "fukui", "ふくいけん"),
    Prefecture("山梨県", "yamanashi", "やまなしけん"),
    Prefecture("長野県", "nagano", "ながのけん"),
    Prefecture("岐阜県", "gifu", "ぎふけん"),
    Prefecture("静岡県", "shizuoka", "しずおかけん"),
    Prefecture("愛知県", "aichi", "あいちけん"),
    Prefecture("三重県", "mie", "みえけん"),
    Prefecture("滋賀県", "shiga", "しがけん"),
    Prefecture("京都府", "kyoto", "きょうとふ"),
    Prefecture("大阪府", "osaka", "おおさかふ"),
    Prefecture("兵庫県", "hyogo", "ひょうごけん"),
    Prefecture("奈良県", "nara", "ならけん"),
    Prefecture("和歌山県", "wakayama", "わかやまけん"),
    Prefecture("鳥取県", "tottori", "とっとりけん"),
    Prefecture("島根県", "shimane", "しまねけん"),
    Prefecture("岡山県", "okayama", "おかやまけん"),
    Prefecture("広島県", "hiroshima", "ひろしまけん"),
    Prefecture("山口県", "yamaguchi", "やまぐちけん"),
    Prefecture("徳島県", "tokushima", "とくしまけん"),
    Prefecture("香川県", "kagawa", "かがわけん"),
    Prefecture("愛媛県", "ehime", "えひめけん"),
    Prefecture("高知県", "kochi", "こうちけん"),
    Prefecture("福岡県", "fukuoka", "ふくおかけん"),
    Prefecture("佐賀県", "saga", "さがけん"),
    Prefecture("長崎県", "nagasaki", "ながさきけん"),
    Prefecture("熊本県", "kumamoto", "くまもとけん"),
    Prefecture("大分県", "oita", "おおいたけん"),
    Prefecture("宮崎県", "miyazaki", "みやざきけん"),
    Prefecture("鹿児島県", "kagoshima", "かごしまけん"),
    Prefecture("沖縄県", "okinawa", "おきなわけん"),
)

PREFECTURES: list[str] = [p.name for p in PREFECTURE_TABLE]
_BY_NAME = {p.name: p for p in PREFECTURE_TABLE}


def _short(name: str) -> str:
    """「東京都」→「東京」。北海道は、そのまま。"""
    return name if name == "北海道" else name[:-1]


# 表記ゆれ(「東京」)は、全文がその表記と一致するときだけ引く(「東京ドーム」を東京都にしない)
_BY_SHORT = {_short(p.name): p for p in PREFECTURE_TABLE}
_PREFIX = re.compile("^(" + "|".join(PREFECTURES) + ")")

# `tag:`(表示名)→ ID の slug。複数のデータセットが同じタグを持てる(設計 §3.1)
DATASET_TAG_SLUGS: dict[str, str] = {
    "レンタカー": "rental",
    "事故": "accident",
    "空き家": "akiya",
    "鉄道": "rail",
    "内航海運": "naiko",
    "飛行計画": "flightplan",
}


def find_prefecture(text: str) -> Prefecture | None:
    """先頭の都道府県名(「東京都千代田区」)、または全文が省略形(「東京」)なら、その都道府県。

    先頭にないとき(海外の長い文など)は `None`。
    """
    s = text.strip()
    m = _PREFIX.match(s)
    return _BY_NAME[m.group(1)] if m else _BY_SHORT.get(s)


def dataset_tag(label: str) -> dict[str, str]:
    return {"id": f"dataset:{DATASET_TAG_SLUGS[label]}", "kind": "dataset", "label": label}


def region_tag(pref: Prefecture) -> dict[str, str]:
    return {"id": f"region:{pref.slug}", "kind": "region", "label": pref.name}


def scene_tags(
    tag: str | None, region_from: list[str], row: Mapping[str, Any]
) -> list[dict[str, str]]:
    """シーンJSON の `tags`。データ種別、続けて地域(`region_from` の列の順。重複は除く)。"""
    out = [dataset_tag(tag)] if tag else []
    seen: set[str] = set()
    for col in region_from:
        value = row.get(col)
        missing = value is None or (isinstance(value, float) and math.isnan(value))
        pref = None if missing else find_prefecture(str(value))
        if pref is not None and pref.slug not in seen:
            seen.add(pref.slug)
            out.append(region_tag(pref))
    return out
