"""Offline Kokoro ONNX speech for Hoshi; no audio files or network calls."""

from __future__ import annotations

from pathlib import Path


NEURAL_NICOLE = "Kokoro — Nicole (soft, low)"
NEURAL_SARAH = "Kokoro — Sarah (composed)"
NEURAL_HEART = "Kokoro — Heart (warm)"
NEURAL_KORE = "Kokoro — Kore (mature, clear)"

NEURAL_VOICES = {
    NEURAL_NICOLE: "af_nicole",
    NEURAL_SARAH: "af_sarah",
    NEURAL_HEART: "af_heart",
    NEURAL_KORE: "af_kore",
}

VOICE_DIR = Path(__file__).resolve().parent / "voice_models"
MODEL_PATH = VOICE_DIR / "kokoro-v1.0.fp16.onnx"
VOICES_PATH = VOICE_DIR / "voices-v1.0.bin"


def models_ready() -> bool:
    """Reject empty/incomplete downloads before loading the engine."""
    return (
        MODEL_PATH.is_file() and MODEL_PATH.stat().st_size > 120_000_000
        and VOICES_PATH.is_file() and VOICES_PATH.stat().st_size > 20_000_000
    )


def speaking_speed(rate: int) -> float:
    """Translate Hoshi's familiar rate slider into Kokoro's speed scale."""
    return max(0.80, min(1.20, round(1.0 + int(rate) * 0.04, 2)))


class LocalNeuralVoice:
    """Initialize once, in the dedicated speech thread, and synthesize in RAM."""

    def __init__(self):
        if not models_ready():
            raise FileNotFoundError("Neural voice files are missing or incomplete")
        from kokoro_onnx import Kokoro

        self.engine = Kokoro(str(MODEL_PATH), str(VOICES_PATH))

    def create(self, text: str, selected_voice: str, rate: int):
        voice_id = NEURAL_VOICES[selected_voice]
        return self.engine.create(
            text, voice=voice_id, speed=speaking_speed(rate), lang="en-us"
        )

    def close(self) -> None:
        voices = getattr(self.engine, "voices", None)
        close = getattr(voices, "close", None)
        if callable(close):
            close()
