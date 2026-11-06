"""埋め込みのプロバイダー(`EMBED_PROVIDER=azure|local`)。

どちらも長さ 1 に正規化して返す。モデルが違うベクトルは混ぜない(`model` に名前を残す)。
"""

from __future__ import annotations

import os
from typing import Any, Literal, Protocol

import numpy as np

Kind = Literal["passage", "query"]
BATCH = 64
LOCAL_MODEL = "intfloat/multilingual-e5-large"
AZURE_MODEL = "text-embedding-3-small"


class EmbedProvider(Protocol):
    model: str

    def embed(self, texts: list[str], kind: Kind = "passage") -> np.ndarray:
        """`(len(texts), dim)` の、各行が長さ 1 の配列。"""
        ...


def normalize(a: np.ndarray) -> np.ndarray:
    """各行を長さ 1 にする。ゼロベクトルはそのまま(0 除算しない)。"""
    a = np.asarray(a, dtype=np.float64)
    norm = np.linalg.norm(a, axis=-1, keepdims=True)
    return a / np.where(norm == 0, 1.0, norm)


class LocalEmbed:
    """`intfloat/multilingual-e5-large`(1024 次元)。`passage: ` / `query: ` を先頭に付ける。"""

    model = LOCAL_MODEL

    def __init__(self, st_model: Any | None = None) -> None:
        if st_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ValueError(
                    "EMBED_PROVIDER=local には sentence-transformers が必要です"
                    "(`uv sync --extra local`)"
                ) from e
            st_model = SentenceTransformer(LOCAL_MODEL)
        self._m = st_model

    def embed(self, texts: list[str], kind: Kind = "passage") -> np.ndarray:
        prefixed = [f"{kind}: {t}" for t in texts]
        return normalize(self._m.encode(prefixed, batch_size=BATCH, normalize_embeddings=False))


class AzureEmbed:
    """Azure OpenAI `text-embedding-3-small`(`dimensions` を指定)。"""

    def __init__(
        self, client: Any | None = None, deployment: str | None = None, dim: int | None = None
    ) -> None:
        self.deployment = deployment or _require_env("AZURE_OPENAI_EMBED_DEPLOYMENT")
        self.dim = dim or int(os.environ.get("EMBED_DIM") or 1024)
        self.model = f"azure/{AZURE_MODEL}"
        if client is None:
            from openai import AzureOpenAI

            client = AzureOpenAI(
                azure_endpoint=_require_env("AZURE_OPENAI_ENDPOINT"),
                api_key=_require_env("AZURE_OPENAI_API_KEY"),
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION") or "2024-10-21",
            )
        self._client = client

    def embed(self, texts: list[str], kind: Kind = "passage") -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH):
            res = self._client.embeddings.create(
                model=self.deployment, input=texts[i : i + BATCH], dimensions=self.dim
            )
            out.extend(d.embedding for d in sorted(res.data, key=lambda d: d.index))
        return normalize(np.array(out))


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"環境変数 {name} が設定されていません")
    return value


def provider_name_from_env() -> str:
    """環境変数 `EMBED_PROVIDER`(既定 `local`)。"""
    return os.environ.get("EMBED_PROVIDER") or "local"


def create_embedder(name: str | None = None) -> EmbedProvider:
    name = name or provider_name_from_env()
    if name == "azure":
        return AzureEmbed()
    if name == "local":
        return LocalEmbed()
    raise ValueError(f"EMBED_PROVIDER={name!r} は未対応です(azure / local)")
