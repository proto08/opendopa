"""プロバイダー名 → 実装。新しいプロバイダーは `register` で登録するだけで使える。"""

from __future__ import annotations

import os
from collections.abc import Callable

from opendopa_pipeline.decider.base import Decider
from opendopa_pipeline.spec import DatasetDef

# 工場関数: データセット定義を受け取り、Decider を返す
Factory = Callable[[DatasetDef], Decider]

DEFAULT_PROVIDER = "rules"
_FACTORIES: dict[str, Factory] = {}


def register(name: str, factory: Factory) -> None:
    """プロバイダーを登録する(同名は上書き)。"""
    _FACTORIES[name] = factory


def provider_name_from_env() -> str:
    """環境変数 `DECIDER_PROVIDER`(既定 `rules`)。"""
    return os.environ.get("DECIDER_PROVIDER") or DEFAULT_PROVIDER


def create_decider(name: str, dataset: DatasetDef) -> Decider:
    try:
        factory = _FACTORIES[name]
    except KeyError:
        known = ", ".join(sorted(_FACTORIES))
        raise ValueError(
            f"DECIDER_PROVIDER={name!r} は登録されていません(登録済み: {known})"
        ) from None
    return factory(dataset)


def _register_builtin() -> None:
    from opendopa_pipeline.decider.rules import RulesDecider
    from opendopa_pipeline.decider.strands_azure import NAME, StrandsAzureDecider

    register("rules", RulesDecider.from_dataset)
    register(NAME, StrandsAzureDecider.from_dataset)


_register_builtin()
