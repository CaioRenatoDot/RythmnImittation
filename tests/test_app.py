import csv
import queue

import pytest

tk = pytest.importorskip("tkinter")

from rythm_imitation import theory  # noqa: E402
from rythm_imitation.app import App  # noqa: E402


@pytest.fixture
def app():
    try:
        a = App()
    except tk.TclError as exc:  # sem display
        pytest.skip(str(exc))
    a.player.volume = 0.0
    a.root.update()
    a.new_pattern(seed=1)
    yield a
    a._on_close()


def test_every_setting_combination_renders(app):
    for ts in theory.TIME_SIGNATURES:
        for level in theory.LEVELS.values():
            app.ts_var.set(ts)
            app.level_var.set(level)
            app.measures_var.set(8)
            app._on_structure()
            app.root.update()
            assert app.pattern.time_signature == ts
            assert app.score.find_all()
            r = app._render()
            assert len(r.samples) > 0


def test_structure_change_keeps_seed_and_history(app):
    seed = app.pattern.seed
    app.level_var.set(theory.LEVELS[4])
    app._on_structure()
    assert app.pattern.seed == seed and app.pattern.level == 4
    app.new_pattern()
    assert app.history[-1] == seed
    app.previous_pattern()
    assert app.pattern.seed == seed


def test_training_score_without_audio(app):
    app.rendered = app._render(training=True)
    app.mode = "train"
    app.taps = [float(o) * app.beat_s + 0.01 for o in app.pattern.onsets()]
    app._finish_training()
    assert app.phase_var.get().startswith("100%")
    assert app.mode == "idle"
    assert app.score.statuses and set(app.score.statuses) == {"perfeito"}


def test_batch_writes_files_and_answer_key(app, tmp_path):
    app.fmt_mid_var.set(True)
    app.exp_fixed_var.set(True)
    app.exp_seconds_var.set(6.0)
    params = dict(level=3, beats_per_measure=4, measures=2, scale="Dó maior", rests=True)
    app._batch_worker(str(tmp_path), 3, [".wav", ".mid"], params, 100, "Marimba", False, False, 6.0, True)
    msgs = []
    while True:
        try:
            msgs.append(app._batch_queue.get_nowait())
        except queue.Empty:
            break
    assert msgs[-1][0] == "done"
    assert len(list(tmp_path.glob("*.wav"))) == 3
    assert len(list(tmp_path.glob("*.mid"))) == 3
    key = next(tmp_path.glob("gabarito_*.csv"))
    rows = list(csv.reader(key.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0][0] == "arquivo" and len(rows) == 4
    assert rows[1][8] == "6,000"


def test_invalid_numbers_do_not_crash(app):
    app.root.setvar(str(app.latency_var), "abc")
    assert app._latency_s() == 0.0
    app.exp_fixed_var.set(True)
    app.root.setvar(str(app.exp_seconds_var), "x")
    with pytest.raises(ValueError):
        app._fixed_seconds()
