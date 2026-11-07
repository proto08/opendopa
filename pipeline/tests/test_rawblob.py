import pytest

from opendopa_pipeline.ingest import load_frame, raw_files
from opendopa_pipeline.rawblob import RawBlobError, fetch_raw


class _Blob:
    def __init__(self, name):
        self.name = name


class _Download:
    def __init__(self, data):
        self.data = data

    def readall(self):
        return self.data


class _Container:
    container_name = "raw"

    def __init__(self, files):
        self.files = files

    def list_blobs(self, name_starts_with=""):
        return [_Blob(n) for n in self.files if n.startswith(name_starts_with)]

    def download_blob(self, name):
        return _Download(self.files[name])


class _Service:
    def __init__(self, files):
        self.container = _Container(files)
        self.asked = None

    def get_container_client(self, name):
        self.asked = name
        return self.container


def test_fetch_raw_downloads_supported_files_directly_under_dataset(tmp_path) -> None:
    svc = _Service(
        {
            "d1/b.csv": b"A\n2\n",
            "d1/a.csv": b"A\n1\n",
            "d1/sub/c.csv": b"x",
            "d1/readme.txt": b"x",
            "d10/z.csv": b"x",
        }
    )
    counts = fetch_raw(["d1"], tmp_path, env={"RAW_BLOB_CONTAINER": "mine"}, service=svc)
    assert counts == {"d1": 2}
    assert svc.asked == "mine"
    assert sorted(p.name for p in (tmp_path / "data/raw/d1").iterdir()) == ["a.csv", "b.csv"]


def test_fetch_raw_fails_when_dataset_has_no_files(tmp_path) -> None:
    with pytest.raises(RawBlobError, match="d2"):
        fetch_raw(["d2"], tmp_path, env={}, service=_Service({"d1/a.csv": b"x"}))


def test_fetch_raw_needs_connection_string(tmp_path) -> None:
    with pytest.raises(RawBlobError, match="STORAGE_CONNECTION_STRING"):
        fetch_raw(["d1"], tmp_path, env={})


def test_blob_mode_reads_every_file_in_name_order(tmp_path, make_dataset, monkeypatch) -> None:
    folder = tmp_path / "data/raw/ds"
    folder.mkdir(parents=True)
    (folder / "b.csv").write_text("A\n2\n", encoding="utf-8")
    (folder / "a.csv").write_text("A\n1\n", encoding="utf-8")
    (folder / "memo.txt").write_text("x", encoding="utf-8")
    d = make_dataset(id="ds", files=["data/raw/ds/a.csv"])
    assert raw_files(d, tmp_path) == ["data/raw/ds/a.csv"]  # 既定は files
    monkeypatch.setenv("RAW_SOURCE", "blob")
    assert raw_files(d, tmp_path) == ["data/raw/ds/a.csv", "data/raw/ds/b.csv"]
    assert list(load_frame(d, tmp_path)["A"]) == [1, 2]
