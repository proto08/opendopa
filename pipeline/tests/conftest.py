from pathlib import Path
from typing import Any

import pytest
import yaml

from opendopa_pipeline.spec import DatasetDef

EXAMPLE = Path(__file__).parents[2] / "datasets" / "_example.yaml"


@pytest.fixture
def make_dataset():
    """_example.yaml を土台に、指定したキーを置き換えた DatasetDef を作る。"""

    def make(**overrides: Any) -> DatasetDef:
        data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
        data.update(overrides)
        return DatasetDef.model_validate(data)

    return make
