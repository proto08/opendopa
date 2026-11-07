"""元 CSV を Blob から取り込む(Issue #144)。

Blob のコンテナ `raw`(`RAW_BLOB_CONTAINER` で変えられる)の `<dataset_id>/` 配下を、
`<root>/data/raw/<dataset_id>/` に置く。取り込んだあとは、`RAW_SOURCE=blob` で
`ingest.raw_files` がその配下をすべて読む。コンテナの作成と CSV の配置は人が行う。
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from opendopa_pipeline.ingest import supported_suffixes

DEFAULT_CONTAINER = "raw"


class RawBlobError(ValueError):
    pass


def fetch_raw(
    dataset_ids: Iterable[str],
    root: Path,
    *,
    env: Mapping[str, str] | None = None,
    service: Any = None,
) -> dict[str, int]:
    """データセットごとに、Blob の `<id>/` 配下の元データを取り込み、ファイル数を返す。

    取り込めるファイルが 1 つもないデータセットがあれば、エラーにする(空のまま洗い替えて、
    動画が消えるのを防ぐ)。`service` はテスト用の差し替え(BlobServiceClient 相当)。
    """
    e = os.environ if env is None else env
    if service is None:
        conn_str = e.get("STORAGE_CONNECTION_STRING")
        if not conn_str:
            raise RawBlobError("STORAGE_CONNECTION_STRING が設定されていません")
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient.from_connection_string(conn_str)
    container = service.get_container_client(e.get("RAW_BLOB_CONTAINER") or DEFAULT_CONTAINER)

    counts: dict[str, int] = {}
    for dataset_id in dataset_ids:
        folder = root / "data" / "raw" / dataset_id
        n = 0
        for blob in container.list_blobs(name_starts_with=f"{dataset_id}/"):
            rel = blob.name.removeprefix(f"{dataset_id}/")
            # 直下のファイルだけ(サブフォルダは読まない)。対応する拡張子だけ
            if "/" in rel or Path(rel).suffix.lower() not in supported_suffixes():
                continue
            folder.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_bytes(container.download_blob(blob.name).readall())
            n += 1
        if n == 0:
            raise RawBlobError(
                f"Blob の {container.container_name}/{dataset_id}/ に元データ"
                f"({', '.join(supported_suffixes())})がありません"
            )
        counts[dataset_id] = n
    return counts
