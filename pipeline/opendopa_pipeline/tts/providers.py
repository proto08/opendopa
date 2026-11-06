"""TTS のプロバイダー(`TTS_PROVIDER=none|voicevox|azure`)。

どちらも 1 行(字幕 1 つ)の文を mp3 のバイト列にして返す。VOICEVOX は wav を返すので mp3 に変換する。
HTTP は標準ライブラリだけで呼ぶ(`post` を差し替えればテストできる)。
"""

from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, Protocol
from xml.sax.saxutils import escape

import lameenc
from mutagen.mp3 import MP3

TIMEOUT_SEC = 60
# (url, body, headers) → レスポンスのバイト列
Post = Callable[[str, bytes, Mapping[str, str]], bytes]


class TtsError(ValueError):
    pass


class Synthesizer(Protocol):
    def synthesize(self, text: str) -> bytes:
        """文を読み上げた mp3 のバイト列。"""
        ...


def _post(url: str, body: bytes, headers: Mapping[str, str]) -> bytes:
    req = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:  # noqa: S310
        return res.read()


def wav_to_mp3(wav: bytes) -> bytes:
    """16bit PCM の wav を mp3 にする(VOICEVOX 用。lameenc を使う)。"""
    import wave

    with wave.open(io.BytesIO(wav)) as w:
        if w.getsampwidth() != 2:
            raise TtsError("16bit の wav だけ変換できます")
        enc = lameenc.Encoder()
        enc.set_bit_rate(64)
        enc.set_in_sample_rate(w.getframerate())
        enc.set_channels(w.getnchannels())
        enc.set_quality(2)
        return bytes(enc.encode(w.readframes(w.getnframes())) + enc.flush())


def mp3_duration(mp3: bytes) -> float:
    """mp3 の長さ(秒、小数2桁)。"""
    try:
        sec = MP3(io.BytesIO(mp3)).info.length
    except Exception as e:  # mutagen の例外は種類が多い
        raise TtsError(f"mp3 の長さを測れません: {e}") from e
    return round(sec, 2)


class VoiceVox:
    """VOICEVOX ENGINE(`VOICEVOX_URL`、既定 http://localhost:50021)。

    声は `VOICEVOX_SPEAKER`(スタイルID。既定 3 = ずんだもん ノーマル)、
    速度は `VOICEVOX_SPEED`(既定 1.0)。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:50021",
        speaker: int = 3,
        speed: float = 1.0,
        post: Post = _post,
    ) -> None:
        self.base_url, self.speaker, self.speed, self._post = (
            base_url.rstrip("/"),
            speaker,
            speed,
            post,
        )

    def synthesize(self, text: str) -> bytes:
        q = urllib.parse.urlencode({"text": text, "speaker": self.speaker})
        query = json.loads(self._post(f"{self.base_url}/audio_query?{q}", b"", {}))
        query["speedScale"] = self.speed
        wav = self._post(
            f"{self.base_url}/synthesis?speaker={self.speaker}",
            json.dumps(query).encode(),
            {"Content-Type": "application/json"},
        )
        return wav_to_mp3(wav)


class Azure:
    """Azure AI Speech の REST(`AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`)。mp3 で受け取る。"""

    def __init__(
        self,
        key: str,
        region: str,
        voice: str = "ja-JP-NanamiNeural",
        post: Post = _post,
    ) -> None:
        self.key, self.region, self.voice, self._post = key, region, voice, post

    def synthesize(self, text: str) -> bytes:
        ssml = (
            f'<speak version="1.0" xml:lang="ja-JP"><voice name="{self.voice}">'
            f"{escape(text)}</voice></speak>"
        )
        return self._post(
            f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
            ssml.encode(),
            {
                "Ocp-Apim-Subscription-Key": self.key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            },
        )


def provider_name_from_env(env: Mapping[str, str] | None = None) -> str:
    return (env if env is not None else os.environ).get("TTS_PROVIDER", "none") or "none"


def create_synthesizer(name: str, env: Mapping[str, str] | None = None) -> Synthesizer | None:
    """`none` のときは `None`(音声を作らない)。"""
    e: Mapping[str, Any] = env if env is not None else os.environ
    if name == "none":
        return None
    if name == "voicevox":
        try:
            return VoiceVox(
                e.get("VOICEVOX_URL") or "http://localhost:50021",
                int(e.get("VOICEVOX_SPEAKER") or 3),
                float(e.get("VOICEVOX_SPEED") or 1.0),
            )
        except ValueError as err:
            raise TtsError(f"VOICEVOX_SPEAKER / VOICEVOX_SPEED が数ではありません: {err}") from err
    if name == "azure":
        if not e.get("AZURE_SPEECH_KEY") or not e.get("AZURE_SPEECH_REGION"):
            raise TtsError(
                "TTS_PROVIDER=azure には AZURE_SPEECH_KEY と AZURE_SPEECH_REGION が必要です"
            )
        return Azure(e["AZURE_SPEECH_KEY"], e["AZURE_SPEECH_REGION"])
    raise TtsError(f"TTS_PROVIDER は none / voicevox / azure のどれか: {name}")
