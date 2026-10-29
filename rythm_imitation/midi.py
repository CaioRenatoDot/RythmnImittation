"""Escrita de arquivos MIDI (Standard MIDI File, formato 0) sem dependências."""

from __future__ import annotations

import struct

from .synth import INSTRUMENTS
from .theory import Pattern

TPQ = 480  # ticks por semínima (divisível por 3 e por 4: tercinas e semicolcheias exatas)


def _varlen(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def pattern_to_midi(pattern: Pattern, bpm: float, instrument: str) -> bytes:
    inst = INSTRUMENTS[instrument]
    channel = 9 if inst.percussion else 0
    events: list[tuple[int, int, bytes]] = []  # (tick, ordem, dados)

    tempo = int(round(60_000_000 / bpm))
    events.append((0, 0, b"\xff\x51\x03" + tempo.to_bytes(3, "big")))
    events.append((0, 0, bytes([0xFF, 0x58, 0x04, pattern.beats_per_measure, 2, 24, 8])))
    events.append((0, 0, b"\xff\x03" + _varlen(len(b"RythmImitation")) + b"RythmImitation"))
    if not inst.percussion:
        events.append((0, 1, bytes([0xC0 | channel, inst.gm_program])))

    for note in pattern.sounding():
        key = 76 if inst.percussion else note.pitch
        on = int(note.start * TPQ)
        off = int((note.start + note.dur) * TPQ)
        if not inst.percussion:
            off = on + max(1, int((off - on) * 0.95))
        events.append((on, 3, bytes([0x90 | channel, key, 96])))
        events.append((off, 2, bytes([0x80 | channel, key, 0])))  # note-off antes do próximo on

    end = pattern.total_beats * TPQ
    events.sort(key=lambda ev: (ev[0], ev[1]))
    track, last = bytearray(), 0
    for tick, _, data in events:
        track += _varlen(tick - last) + data
        last = tick
    track += _varlen(max(0, end - last)) + b"\xff\x2f\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ)
    return header + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def write_midi(path: str, pattern: Pattern, bpm: float, instrument: str) -> None:
    with open(path, "wb") as fh:
        fh.write(pattern_to_midi(pattern, bpm, instrument))
