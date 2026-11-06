"""LLM のプロバイダー(設計書 §0.4、`LLM_PROVIDER=azure|none`)。

実行時(ユーザーが見ている最中)には使わない。
Batch の中で、クラスタ名やテンプレート案を作るときだけ使う。
"""

from __future__ import annotations

import os
from typing import Protocol


class LlmProvider(Protocol):
    def complete(self, system: str, user: str) -> str:
        """システム指示とユーザー入力を渡し、返答の文字列を返す。"""
        ...


class AzureLlm:
    """Azure OpenAI のチャットモデル。デプロイ名は `AZURE_OPENAI_CHAT_DEPLOYMENT`。"""

    def __init__(self, client: object | None = None, deployment: str | None = None) -> None:
        self.deployment = deployment or _require_env("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if client is None:
            from openai import AzureOpenAI

            client = AzureOpenAI(
                azure_endpoint=_require_env("AZURE_OPENAI_ENDPOINT"),
                api_key=_require_env("AZURE_OPENAI_API_KEY"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION") or "2024-10-21",
            )
        self._client = client

    def complete(self, system: str, user: str) -> str:
        res = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=self.deployment,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
        )
        return res.choices[0].message.content or ""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"環境変数 {name} が設定されていません")
    return value


def provider_name_from_env() -> str:
    """環境変数 `LLM_PROVIDER`(既定 `none`)。"""
    return os.environ.get("LLM_PROVIDER") or "none"


def create_llm(name: str | None = None) -> LlmProvider | None:
    """`none` のときは None(呼び出し側が機械的なフォールバックを使う)。"""
    name = name or provider_name_from_env()
    if name == "none":
        return None
    if name == "azure":
        return AzureLlm()
    raise ValueError(f"LLM_PROVIDER={name!r} は未対応です(azure / none)")
