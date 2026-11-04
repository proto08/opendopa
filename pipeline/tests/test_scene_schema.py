"""pipeline と web の契約(シーンJSON)のテスト。TS 側は packages/shared/src/validate.test.ts。"""

import copy
import json

import pytest
from pydantic import ValidationError

from opendopa_pipeline.generated.scene import Scene
from opendopa_pipeline.scene import SHARED, validate_scene

FIXTURES = sorted((SHARED / "fixtures").glob("*.json"))


def load(name: str) -> dict:
    return json.loads((SHARED / "fixtures" / name).read_text(encoding="utf-8"))


def test_four_fixtures() -> None:
    assert len(FIXTURES) == 4


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_is_valid(path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert validate_scene(data) == []
    Scene.model_validate(data)


BAD = {
    "headline 41字": lambda s: s.update(headline="あ" * 41),
    "durationSec 14.9": lambda s: s.update(durationSec=14.9),
    "durationSec 30.1": lambda s: s.update(durationSec=30.1),
    "sparkline 13点": lambda s: s.update(sparkline=[{"x": i, "y": i} for i in range(13)]),
    "comments.style = red": lambda s: s["comments"][0].update(style="red"),
    "map.type = line": lambda s: s.update(map={"type": "line"}),
    "color = red": lambda s: s.update(color="red"),
    "wmChar 2文字": lambda s: s.update(wmChar="機機"),
}


@pytest.mark.parametrize("mutate", BAD.values(), ids=BAD.keys())
def test_invalid_scene_is_rejected(mutate) -> None:
    data = copy.deepcopy(load("accident-0001.json"))
    mutate(data)
    assert validate_scene(data) != []


def test_headline_40_chars_is_valid() -> None:
    data = load("accident-0001.json")
    data["headline"] = "あ" * 40
    assert validate_scene(data) == []


def test_generated_model_rejects_duration_out_of_range() -> None:
    data = load("accident-0001.json")
    data["durationSec"] = 40
    with pytest.raises(ValidationError):
        Scene.model_validate(data)
