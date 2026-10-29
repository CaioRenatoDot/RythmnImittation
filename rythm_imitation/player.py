"""Reprodução de áudio em tempo real.

Usa ``sounddevice`` (PortAudio). O callback registra em que instante cada
bloco chega de fato ao alto-falante, então ``position()`` devolve o ponto do
áudio que está sendo *ouvido* agora — já descontada a latência da placa. Isso
mantém o cursor da partitura e a pontuação do modo treino sincronizados.
Se o PortAudio não estiver disponível, cai para o ``winsound`` do Windows.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time

import numpy as np

from .synth import SR, write_wav

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - depende do sistema
    sd = None


def output_devices() -> list[tuple[int | None, str]]:
    """Dispositivos de saída da API de áudio padrão: [(índice, nome)]."""
    devices: list[tuple[int | None, str]] = [(None, "Padrão do sistema")]
    if sd is None:
        return devices
    try:
        default_out = sd.default.device[1]
        hostapi = sd.query_devices(default_out)["hostapi"] if default_out is not None and default_out >= 0 else 0
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_output_channels"] > 0 and dev["hostapi"] == hostapi:
                devices.append((i, dev["name"]))
    except Exception:
        pass
    return devices


class Player:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream = None
        self._data = np.zeros(0, dtype=np.float32)
        self._pos = 0
        self._loop = False
        self._ref: tuple[int, float] | None = None  # (amostra, perf_counter em que é ouvida)
        self._playing = False
        self._fallback_t0: float | None = None
        self._fallback_file: str | None = None
        self.volume = 0.9
        self.device: int | None = None
        self.backend = "sounddevice" if sd is not None else "winsound"
        self.last_error: str | None = None

    # -- API pública -------------------------------------------------------

    @property
    def playing(self) -> bool:
        if self._fallback_t0 is not None and not self._loop:
            if time.perf_counter() - self._fallback_t0 > len(self._data) / SR + 0.3:
                self._fallback_t0 = None
                self._playing = False
        return self._playing

    @property
    def length(self) -> float:
        return len(self._data) / SR

    def play(self, samples: np.ndarray, loop: bool = False) -> None:
        self.stop()
        with self._lock:
            self._data = np.ascontiguousarray(samples, dtype=np.float32)
            self._pos = 0
            self._loop = loop
            self._ref = None
        self.last_error = None
        if sd is not None:
            try:
                self._start_stream()
                return
            except Exception as exc:  # dispositivo ocupado/indisponível
                self.last_error = str(exc)
                self._stream = None
        self._play_fallback()

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                pass
        if self._fallback_t0 is not None:
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            self._fallback_t0 = None
        self._playing = False
        self._ref = None

    def position(self) -> float | None:
        """Segundos do áudio que estão saindo do alto-falante agora."""
        now = time.perf_counter()
        if self._fallback_t0 is not None:
            pos = now - self._fallback_t0
            return pos % self.length if self._loop and self.length else pos
        ref = self._ref
        if not self._playing or ref is None:
            return None
        pos = (ref[0] + (now - ref[1]) * SR) / SR
        if pos < 0:
            return 0.0
        if self._loop and self.length:
            return pos % self.length
        return min(pos, self.length)

    def close(self) -> None:
        self.stop()
        if self._fallback_file and os.path.exists(self._fallback_file):
            try:
                os.remove(self._fallback_file)
            except OSError:
                pass

    # -- implementação -----------------------------------------------------

    def _start_stream(self) -> None:
        dev = self.device
        channels = 2
        try:
            info = sd.query_devices(dev if dev is not None else sd.default.device[1])
            channels = 1 if info["max_output_channels"] < 2 else 2
        except Exception:
            pass
        self._channels = channels
        stream = sd.OutputStream(
            samplerate=SR, channels=channels, dtype="float32", device=dev,
            latency="low", callback=self._callback, finished_callback=self._finished,
        )
        self._stream = stream
        self._playing = True
        stream.start()

    def _callback(self, outdata, frames, time_info, status) -> None:
        now = time.perf_counter()
        with self._lock:
            data, pos, n = self._data, self._pos, len(self._data)
            dac = time_info.outputBufferDacTime
            cur = time_info.currentTime
            delay = dac - cur if dac and cur and dac >= cur else (self._stream.latency if self._stream else 0.0)
            self._ref = (pos, now + delay)

            chunk = data[pos:pos + frames]
            if self._loop and n and len(chunk) < frames:
                reps = int(np.ceil((frames - len(chunk)) / n)) + 1
                chunk = np.concatenate([chunk, np.tile(data, reps)])[:frames]
                self._pos = (pos + frames) % n
            else:
                self._pos = pos + frames
            out = np.zeros(frames, dtype=np.float32)
            out[:len(chunk)] = chunk[:frames]
            out *= self.volume
        outdata[:] = out[:, None]
        if not self._loop and self._pos >= n:
            # deixa o último bloco ser tocado e então encerra
            raise sd.CallbackStop

    def _finished(self) -> None:
        self._playing = False

    def _play_fallback(self) -> None:
        try:
            import winsound
        except ImportError:
            self.last_error = self.last_error or "Nenhum backend de áudio disponível."
            return
        if self._fallback_file is None:
            fd, self._fallback_file = tempfile.mkstemp(suffix=".wav", prefix="rythm_")
            os.close(fd)
        write_wav(self._fallback_file, self._data * self.volume)
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        if self._loop:
            flags |= winsound.SND_LOOP
        winsound.PlaySound(self._fallback_file, flags)
        self.backend = "winsound"
        self._fallback_t0 = time.perf_counter()
        self._playing = True
