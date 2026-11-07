"""ハッシュタグ(#151。docs/hashtag_design.md §3)。"""

from pathlib import Path

import pytest

from opendopa_pipeline.spec import load_dataset
from opendopa_pipeline.tags import (
    DATASET_TAG_SLUGS,
    PREFECTURE_TABLE,
    find_prefecture,
    scene_tags,
)

DATASETS = sorted((Path(__file__).parents[2] / "datasets").glob("[!_]*.yaml"))


def test_table_has_47_unique_prefectures() -> None:
    assert len(PREFECTURE_TABLE) == 47
    for field in ("name", "slug", "yomi"):
        assert len({getattr(p, field) for p in PREFECTURE_TABLE}) == 47


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("北海道札幌市", "hokkaido"),
        ("東京都千代田区", "tokyo"),
        ("東京", "tokyo"),  # 表記ゆれ(省略形)
        ("京都", "kyoto"),
        (" 沖縄県 ", "okinawa"),
        ("神奈川県横浜市", "kanagawa"),
    ],
)
def test_find_prefecture(text: str, slug: str) -> None:
    pref = find_prefecture(text)
    assert pref is not None and pref.slug == slug


@pytest.mark.parametrize(
    "text",
    [
        "",
        "不明",
        "東京ドーム周辺",  # 省略形は全文が一致するときだけ
        "上空の航空機が、東京都の上を飛んだ。" * 5,  # 先頭にない(海外の長い文など)
        "Tokyo",
    ],
)
def test_find_prefecture_none(text: str) -> None:
    assert find_prefecture(text) is None


def test_scene_tags_dataset_and_region() -> None:
    row = {"LOC": "北海道札幌市"}
    assert scene_tags("事故", ["LOC"], row) == [
        {"id": "dataset:accident", "kind": "dataset", "label": "事故"},
        {"id": "region:hokkaido", "kind": "region", "label": "北海道"},
    ]


def test_scene_tags_missing_or_unknown_has_no_region() -> None:
    for value in (None, float("nan"), "", "海外の長い文。" * 10):
        tags = scene_tags("事故", ["LOC"], {"LOC": value})
        assert [t["kind"] for t in tags] == ["dataset"]
    assert [t["kind"] for t in scene_tags("事故", ["NOPE"], {})] == ["dataset"]


def test_scene_tags_dedups_regions_in_column_order() -> None:
    row = {"A": "山口県", "B": "山口県", "C": "石川県"}
    ids = [t["id"] for t in scene_tags("内航海運", ["A", "B", "C"], row)]
    assert ids == ["dataset:naiko", "region:yamaguchi", "region:ishikawa"]


def test_scene_tags_no_tag_no_region_from_is_empty() -> None:
    assert scene_tags(None, [], {"LOC": "東京都"}) == []


@pytest.mark.parametrize("path", DATASETS, ids=lambda p: p.stem)
def test_every_dataset_has_a_dataset_tag(path: Path) -> None:
    ds = load_dataset(path)
    assert ds.tag in DATASET_TAG_SLUGS
    if ds.id.startswith("rail_"):
        assert ds.tag == "鉄道" and ds.region_from == []  # 運輸局は都道府県でない
    if ds.id in ("naiko_ship",):
        assert ds.region_from == []  # Address は事業者の所在地(使わない)
