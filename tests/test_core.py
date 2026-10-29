import struct
import wave
from fractions import Fraction as F

import numpy as np
import pytest

from rythm_imitation import midi, scoring, synth, theory


@pytest.mark.parametrize("level", [1, 2, 3, 4])
@pytest.mark.parametrize("ts", [2, 3, 4, 5])
@pytest.mark.parametrize("rests", [True, False])
def test_measures_are_always_complete(level, ts, rests):
    for seed in range(40):
        p = theory.generate(level, ts, 4, rests=rests, seed=seed)
        for m in range(4):
            total = sum((n.dur for n in p.notes if n.measure == m), F(0))
            assert total == ts
            assert any(not n.rest for n in p.notes if n.measure == m)
        assert p.notes[-1].start + p.notes[-1].dur == p.total_beats
        if not rests:
            assert not any(n.rest for n in p.notes)


def test_levels_only_use_allowed_figures():
    for seed in range(60):
        p = theory.generate(1, 4, 4, seed=seed)
        assert all(n.event.base >= 1 and not n.event.dotted for n in p.notes)
        p = theory.generate(2, 4, 4, seed=seed)
        assert all(n.event.base >= F(1, 2) and n.event.tuplet == 0 for n in p.notes)


def test_two_beat_figures_do_not_cross_middle_of_even_measures():
    for seed in range(80):
        p = theory.generate(3, 4, 2, seed=seed)
        for n in p.notes:
            if n.dur >= 2 and n.event.base >= 2:
                assert (n.start % 4) in (0, 2)


def test_generation_is_reproducible_and_varied():
    a = theory.generate(3, 4, 2, seed=123)
    b = theory.generate(3, 4, 2, seed=123)
    assert [(n.start, n.event, n.pitch) for n in a.notes] == [(n.start, n.event, n.pitch) for n in b.notes]
    texts = {theory.generate(3, 4, 2, seed=s).rhythm_text() for s in range(30)}
    assert len(texts) > 20


def test_melody_stays_in_scale_and_resolves_to_tonic():
    for name, sc in theory.SCALES.items():
        for seed in range(20):
            p = theory.generate(2, 4, 2, scale=name, seed=seed)
            pitches = [n.pitch for n in p.sounding()]
            assert set(pitches) <= set(sc.notes)
            assert pitches[-1] % 12 == sc.tonic % 12


def test_note_names():
    assert theory.note_name(60) == "Dó4"
    assert theory.note_name(69) == "Lá4"
    assert theory.note_name(63) == "Mi♭4"
    assert theory.spell(64) == (30, "")  # Mi4 na primeira linha da clave de sol


def test_default_settings_keep_original_six_seconds_at_100_bpm():
    p = theory.generate()
    r = synth.render(p, 100, "Piano elétrico")
    assert len(r.samples) == 6 * synth.SR
    assert p.duration_seconds(100) == pytest.approx(6.0)


@pytest.mark.parametrize("instrument", list(synth.INSTRUMENTS))
def test_render_is_clean(instrument):
    p = theory.generate(4, 4, 2, seed=5)
    r = synth.render(p, 120, instrument, metronome=True, count_in=True)
    y = r.samples
    assert len(y) == round((4 + 8) * 0.5 * synth.SR)
    assert r.pattern_start == pytest.approx(2.0)
    assert np.isfinite(y).all()
    assert 0.25 < np.max(np.abs(y)) <= 0.9
    assert abs(np.mean(y)) < 2e-3
    assert abs(y[0]) < 1e-3 and abs(y[-1]) < 1e-3


def test_training_render_layout():
    p = theory.generate(2, 4, 2, seed=1)
    r = synth.render_training(p, 120, "Marimba")
    beat = 0.5
    assert r.pattern_start == pytest.approx(4 * beat)
    assert r.tap_start == pytest.approx(4 * beat + 8 * beat + 4 * beat)
    assert r.seconds == pytest.approx(r.tap_start + 8 * beat + beat)


def test_fit_duration():
    y = np.ones(1000, dtype=np.float32)
    assert len(synth.fit_duration(y, 1.0)) == synth.SR
    cut = synth.fit_duration(np.ones(synth.SR * 2, dtype=np.float32), 1.0)
    assert len(cut) == synth.SR and cut[-1] == 0


def test_wav_roundtrip(tmp_path):
    p = theory.generate(seed=9)
    r = synth.render(p, 100, "Violão")
    path = tmp_path / "x.wav"
    synth.write_wav(str(path), r.samples)
    with wave.open(str(path)) as wf:
        assert wf.getframerate() == synth.SR
        assert wf.getnframes() == 6 * synth.SR


def test_midi_structure():
    p = theory.generate(4, 3, 3, seed=2)
    data = midi.pattern_to_midi(p, 90, "Marimba")
    assert data[:4] == b"MThd"
    fmt, ntracks, tpq = struct.unpack(">HHH", data[8:14])
    assert (fmt, ntracks, tpq) == (0, 1, midi.TPQ)
    assert data[14:18] == b"MTrk"
    length = struct.unpack(">I", data[18:22])[0]
    assert len(data) == 22 + length
    assert data.endswith(b"\xff\x2f\x00")
    assert data.count(b"\x90") >= len(p.sounding())


def test_scoring_perfect_and_misses():
    exp = [0.0, 0.5, 1.0, 1.5]
    assert scoring.score_taps(exp, exp).percent == 100
    r = scoring.score_taps(exp, [0.01, 0.52, 1.5])
    assert [n.status for n in r.notes] == ["perfeito", "perfeito", "perdeu", "perfeito"]
    assert r.percent == 75
    r = scoring.score_taps(exp, exp + [0.25])
    assert len(r.extras) == 1 and r.percent == 100 - 30 / 4


def test_scoring_detects_tendency():
    exp = [0.0, 0.5, 1.0, 1.5]
    r = scoring.score_taps(exp, [t - 0.06 for t in exp])
    assert all(n.status == "bom" for n in r.notes)
    assert r.mean_offset_ms == pytest.approx(-60)
    assert "adiantado" in r.summary()
    assert scoring.score_taps(exp, []).percent == 0
