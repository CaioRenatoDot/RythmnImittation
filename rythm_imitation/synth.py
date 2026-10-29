"""Síntese de áudio com numpy: instrumentos, metrônomo e exportação."""

from __future__ import annotations

import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from .theory import Pattern, midi_to_hz

SR = 44100
TARGET_RMS = 0.22
TWO_PI = 2 * np.pi


def _fade(y: np.ndarray, attack_s: float, release_s: float) -> np.ndarray:
    """Aplica rampas lineares de entrada/saída (remove os 'cliques')."""
    n = len(y)
    a = min(n, max(1, int(attack_s * SR)))
    r = min(n, max(1, int(release_s * SR)))
    y[:a] *= np.linspace(0.0, 1.0, a)
    y[n - r:] *= np.linspace(1.0, 0.0, r)
    return y


# ---------------------------------------------------------------------------
# Instrumentos: cada um recebe (frequência, nº de amostras) e devolve um array
# ---------------------------------------------------------------------------


def _epiano(f: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    index = 1.6 * np.exp(-t * 5.0)
    y = np.sin(TWO_PI * f * t + index * np.sin(TWO_PI * f * t))
    y += 0.12 * np.sin(TWO_PI * 2 * f * t) * np.exp(-t * 3.0)
    y *= np.exp(-t * 1.8)
    return _fade(y, 0.004, 0.04)


def _marimba(f: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    y = np.sin(TWO_PI * f * t) * np.exp(-t * 4.5)
    y += 0.35 * np.sin(TWO_PI * 3.93 * f * t) * np.exp(-t * 16)
    y += 0.08 * np.sin(TWO_PI * 9.2 * f * t) * np.exp(-t * 40)
    return _fade(y, 0.002, 0.03)


def _pluck(f: float, n: int) -> np.ndarray:
    """Violão por Karplus-Strong (vetorizado em blocos de um período)."""
    period = SR / f
    p = max(2, int(period))
    frac = period - p      # atraso fracionário por interpolação linear (afinação exata)
    rng = np.random.default_rng(int(f * 1000))
    y = np.zeros(n + p + 1)
    burst = rng.uniform(-1, 1, p + 1)
    burst = np.convolve(burst, np.ones(3) / 3, mode="same")  # ataque menos áspero
    burst -= burst.mean()                                     # sem offset DC
    y[:p + 1] = burst
    k = p + 1
    while k < len(y):
        end = min(k + p, len(y))
        y[k:end] = 0.995 * ((1 - frac) * y[k - p:end - p] + frac * y[k - p - 1:end - p - 1])
        k = end
    y = y[:n].copy()
    return _fade(y, 0.001, 0.04)


def _flute(f: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(TWO_PI * 5.2 * t) * np.clip((t - 0.15) * 4, 0, 1)
    phase = TWO_PI * f * np.cumsum(vib) / SR
    y = np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.05 * np.sin(3 * phase)
    rng = np.random.default_rng(7)
    y += 0.02 * rng.standard_normal(n) * np.exp(-t * 12)
    return _fade(y, 0.035, 0.05)


def _sine(f: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    return _fade(np.sin(TWO_PI * f * t), 0.005, 0.025)


def _woodblock(f: float, n: int) -> np.ndarray:
    t = np.arange(n) / SR
    y = np.sin(TWO_PI * 880 * t) * np.exp(-t * 55)
    y += 0.6 * np.sin(TWO_PI * 1410 * t) * np.exp(-t * 70)
    rng = np.random.default_rng(3)
    y += 0.4 * rng.uniform(-1, 1, n) * np.exp(-t * 400)
    return _fade(y, 0.0005, 0.01)


@dataclass(frozen=True)
class Instrument:
    name: str
    fn: object
    gate: float          # fração da figura que a nota sustenta
    ring: float          # segundos extras que a nota pode soar (instrumentos percussivos)
    gain: float
    gm_program: int      # programa General MIDI (para exportação .mid)
    percussion: bool = False


INSTRUMENTS: dict[str, Instrument] = {i.name: i for i in (
    Instrument("Piano elétrico", _epiano, 0.95, 0.0, 0.9, 4),
    Instrument("Marimba", _marimba, 1.0, 0.45, 1.0, 12),
    Instrument("Violão", _pluck, 1.0, 0.5, 1.1, 24),
    Instrument("Flauta", _flute, 0.9, 0.0, 0.7, 73),
    Instrument("Senoide (clássico)", _sine, 0.9, 0.0, 0.7, 80),
    Instrument("Bloco de madeira (só ritmo)", _woodblock, 1.0, 0.12, 1.0, 76, percussion=True),
)}


@lru_cache(maxsize=512)
def _note_sound(instrument: str, midi: int, n: int) -> np.ndarray:
    y = INSTRUMENTS[instrument].fn(midi_to_hz(midi), n).astype(np.float32)
    y.setflags(write=False)
    return y


@lru_cache(maxsize=4)
def _click(accent: bool) -> np.ndarray:
    n = int(0.05 * SR)
    t = np.arange(n) / SR
    f = 1760 if accent else 1175
    y = np.sin(TWO_PI * f * t) * np.exp(-t * 90) * (0.55 if accent else 0.38)
    y = _fade(y, 0.0005, 0.005).astype(np.float32)
    y.setflags(write=False)
    return y


# ---------------------------------------------------------------------------
# Mixagem
# ---------------------------------------------------------------------------


class _Mixer:
    def __init__(self, seconds: float):
        self.buf = np.zeros(int(round(seconds * SR)), dtype=np.float32)

    def add(self, at_s: float, y: np.ndarray, gain: float = 1.0) -> None:
        i = int(round(at_s * SR))
        if i >= len(self.buf):
            return
        seg = y[: len(self.buf) - i]
        self.buf[i:i + len(seg)] += seg * gain

    def add_clicks(self, start_s: float, beats: int, beat_s: float, beats_per_measure: int,
                   gain: float = 1.0) -> None:
        for b in range(beats):
            self.add(start_s + b * beat_s, _click(b % beats_per_measure == 0), gain)

    def add_pattern(self, start_s: float, pattern: Pattern, beat_s: float, instrument: str) -> None:
        inst = INSTRUMENTS[instrument]
        for note in pattern.sounding():
            dur_s = float(note.dur) * beat_s
            n = int((dur_s * inst.gate + inst.ring) * SR)
            self.add(start_s + float(note.start) * beat_s,
                     _note_sound(instrument, note.pitch, n), 0.45 * inst.gain)

    def finish(self, normalize: bool = True) -> np.ndarray:
        y = self.buf
        if len(y) > 64:
            y[-64:] *= np.linspace(1, 0, 64)  # sem clique no corte final
        peak = float(np.max(np.abs(y))) if len(y) else 0.0
        if normalize and peak > 0:
            # nivela o volume percebido entre instrumentos sem deixar o pico passar de -1 dBFS
            rms = float(np.sqrt(np.mean(y * y)))
            y *= min(0.89 / peak, TARGET_RMS / rms)
        return y


@dataclass
class Rendered:
    samples: np.ndarray
    pattern_start: float        # segundos até o primeiro tempo do padrão
    tap_start: float | None = None  # segundos até o primeiro tempo da imitação (modo treino)

    @property
    def seconds(self) -> float:
        return len(self.samples) / SR


def render(pattern: Pattern, bpm: float, instrument: str, metronome: bool = False,
           count_in: bool = False) -> Rendered:
    """Renderiza o padrão; o comprimento é exatamente compassos x tempos x batida."""
    beat_s = 60.0 / bpm
    lead = pattern.beats_per_measure * beat_s if count_in else 0.0
    mix = _Mixer(lead + pattern.total_beats * beat_s)
    if count_in:
        mix.add_clicks(0, pattern.beats_per_measure, beat_s, pattern.beats_per_measure)
    if metronome:
        mix.add_clicks(lead, pattern.total_beats, beat_s, pattern.beats_per_measure, 0.8)
    mix.add_pattern(lead, pattern, beat_s, instrument)
    return Rendered(mix.finish(), lead)


def render_training(pattern: Pattern, bpm: float, instrument: str,
                    metronome: bool = True) -> Rendered:
    """Áudio do modo treino: contagem, padrão, nova contagem e espaço para imitar."""
    beat_s = 60.0 / bpm
    bpm_m = pattern.beats_per_measure
    lead = bpm_m * beat_s
    body = pattern.total_beats * beat_s
    tap_start = lead + body + lead
    mix = _Mixer(tap_start + body + beat_s)
    mix.add_clicks(0, bpm_m, beat_s, bpm_m)
    if metronome:
        mix.add_clicks(lead, pattern.total_beats, beat_s, bpm_m, 0.8)
    mix.add_pattern(lead, pattern, beat_s, instrument)
    mix.add_clicks(lead + body, bpm_m, beat_s, bpm_m)
    if metronome:
        mix.add_clicks(tap_start, pattern.total_beats, beat_s, bpm_m, 0.8)
    return Rendered(mix.finish(), lead, tap_start)


def render_clicks(beats: int, bpm: float, beats_per_measure: int = 4) -> np.ndarray:
    """Só metrônomo (usado na calibração de latência)."""
    beat_s = 60.0 / bpm
    mix = _Mixer(beats * beat_s + 0.3)
    mix.add_clicks(0, beats, beat_s, beats_per_measure)
    return mix.finish(normalize=False)


def fit_duration(samples: np.ndarray, seconds: float) -> np.ndarray:
    """Completa com silêncio ou corta (com fade) para a duração exata."""
    n = int(round(seconds * SR))
    if len(samples) >= n:
        out = samples[:n].copy()
        fade = min(n, int(0.02 * SR))
        if len(samples) > n and fade:
            out[-fade:] *= np.linspace(1, 0, fade)
        return out
    return np.concatenate([samples, np.zeros(n - len(samples), dtype=samples.dtype)])


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------


def to_pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()


def write_wav(path: str, samples: np.ndarray) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(to_pcm16(samples))


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def write_mp3(path: str, samples: np.ndarray) -> None:
    exe = ffmpeg_path()
    if not exe:
        raise RuntimeError("ffmpeg não encontrado no PATH — instale-o para exportar MP3.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    subprocess.run(
        [exe, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1",
         "-i", "-", "-b:a", "192k", path],
        input=to_pcm16(samples), check=True, creationflags=flags, capture_output=True,
    )
