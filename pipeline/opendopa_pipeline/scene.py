"""シーンJSONの検証。`packages/shared/schema/scene.schema.json` を正として読む(ADR-0012 A2)。"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SHARED = Path(__file__).resolve().parents[2] / "packages" / "shared"
SCENE_SCHEMA = SHARED / "schema" / "scene.schema.json"


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCENE_SCHEMA.read_text(encoding="utf-8")))


def validate_scene(data: Any) -> list[str]:
    """スキーマに合わない箇所を `パス メッセージ` の一覧で返す。空なら合格。"""
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(map(str, e.absolute_path))} {e.message}" for e in errors]
