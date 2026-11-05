import pytest

from opendopa_pipeline.comments import FORBIDDEN_IN_CALM, generate_comments, pool_name
from opendopa_pipeline.spec import parse_comment_rule
from opendopa_pipeline.util import stable_int

EXPECTED_SEED = 8600599185814807554


def calm_ds(make_dataset):
    return make_dataset(
        comments={
            "pool_calm": ["気をつけたい", "無事でよかった", "安全第一", "草"],
            "rule": "INJ == 'あり' -> none; else calm",
        }
    )


def test_same_video_id_same_comments_and_count_and_times(make_dataset) -> None:
    d = calm_ds(make_dataset)
    a = generate_comments(d, {"INJ": "なし"}, "example-0001", 24.8)
    assert a == generate_comments(d, {"INJ": "なし"}, "example-0001", 24.8)
    assert a != generate_comments(d, {"INJ": "なし"}, "example-0002", 24.8)
    for i in range(1, 60):
        cs = generate_comments(d, {"INJ": "なし"}, f"example-{i:04d}", 15.0 + i % 16)
        assert 6 <= len(cs) <= 12
        assert all(0 <= c["t"] <= 15.0 + i % 16 for c in cs)
        assert [c["t"] for c in cs] == sorted(c["t"] for c in cs)


def test_stable_int_is_fixed_across_processes() -> None:
    # hash() は実行ごとに変わる。sha256 由来の値は固定。変わると既存の動画のコメントが変わる
    assert stable_int("comments", "accident-0001") == EXPECTED_SEED


def test_rule_none_gives_empty_and_calm_has_no_forbidden_words(make_dataset) -> None:
    d = calm_ds(make_dataset)
    assert generate_comments(d, {"INJ": "あり"}, "example-0001", 20.0) == []
    assert pool_name(d, {"INJ": "あり"}) == "none"
    for i in range(30):
        for c in generate_comments(d, {"INJ": "なし"}, f"v-{i}", 20.0):
            assert not any(w in c["text"] for w in FORBIDDEN_IN_CALM)
            assert c["style"] == "normal"


def test_default_pool_without_rule(make_dataset) -> None:
    d = make_dataset(comments={})
    cs = generate_comments(d, {}, "example-0003", 20.0)
    assert 6 <= len(cs) <= 12 and all(c["style"] in ("normal", "yellow") for c in cs)
    assert pool_name(make_dataset(comments={"pool_calm": ["a"]}), {}) == "calm"


def test_rule_syntax_is_checked_at_load(make_dataset) -> None:
    assert parse_comment_rule("a == 1 -> none; else calm") == [("a == 1", "none"), (None, "calm")]
    with pytest.raises(ValueError):
        make_dataset(comments={"rule": "それっぽい文"})
    with pytest.raises(ValueError):
        make_dataset(comments={"rule": "a ==  -> none"})
