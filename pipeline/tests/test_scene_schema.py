"""pipeline と web の契約(シーンJSON)のテスト。"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from opendopa_pipeline.generated.scene import Scene

SHARED = Path(__file__).resolve().parents[2] / "packages" / "shared"


def load_example() -> dict:
    return json.loads((SHARED / "examples" / "scene.accident.json").read_text(encoding="utf-8"))


def test_example_scene_is_valid() -> None:
    scene = Scene.model_validate(load_example())
    assert scene.videoId == "accident-0001"


def test_duration_out_of_range_is_rejected() -> None:
    data = load_example()
    data["durationSec"] = 40
    with pytest.raises(ValidationError):
        Scene.model_validate(data)
