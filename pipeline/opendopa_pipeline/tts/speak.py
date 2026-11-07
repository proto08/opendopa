"""TTS 用の整形(設計書 §8.7)。`tts_dict.yaml` の読み替えを、TTS に渡す文だけに適用する。"""

from __future__ import annotations

from pathlib import Path

import yaml

DICT_PATH = Path(__file__).resolve().parents[2] / "tts_dict.yaml"


def load_dict(path: Path | str = DICT_PATH) -> dict[str, str]:
    """`{表記: 読み}`。ファイルがなければ空。"""
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ValueError(f"{p}: 「表記: 読み」の形で書いてください")
    return data


def apply_dict(text: str, words: dict[str, str]) -> str:
    """辞書の語を読みに置き換える。長い語を先に置き換える(辞書にない語はそのまま)。"""
    for word in sorted(words, key=len, reverse=True):
        text = text.replace(word, words[word])
    return text
