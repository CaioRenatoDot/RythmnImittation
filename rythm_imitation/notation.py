"""Desenho de partitura (clave de sol) em um Canvas do Tk.

O espaçamento horizontal é proporcional ao tempo, então o cursor de
reprodução anda em linha reta e passa exatamente por cima de cada nota.
"""

from __future__ import annotations

import math
import tkinter as tk
from fractions import Fraction as F

from .theory import Pattern, note_name, spell

SP = 10                 # distância entre as linhas da pauta
ROW_H = 150
STAFF_TOP = 48          # dentro da linha (row)
STEM = 34
BOTTOM_LINE_STEP = 30   # Mi4 = primeira linha
MIDDLE_LINE_STEP = 34   # Si4 = terceira linha

PAPER = "#f6f1e4"
INK = "#1e1e24"
MUTED = "#8a8578"
ACCENT = "#1f6fd1"
STATUS_COLORS = {"perfeito": "#159a55", "bom": "#69b52a", "ok": "#e08a00", "perdeu": "#d23a3a"}


def _ellipse(cx: float, cy: float, rx: float, ry: float, angle_deg: float = -20, n: int = 18):
    a = math.radians(angle_deg)
    pts = []
    for k in range(n):
        th = 2 * math.pi * k / n
        x, y = rx * math.cos(th), ry * math.sin(th)
        pts += [cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)]
    return pts


class ScoreView(tk.Canvas):
    def __init__(self, master, **kw):
        kw.setdefault("background", PAPER)
        kw.setdefault("highlightthickness", 0)
        super().__init__(master, **kw)
        self.pattern: Pattern | None = None
        self.show_names = True
        self.statuses: list[str] | None = None   # um por nota tocada
        self.taps: list[tuple[float, str]] = []  # (batida, cor)
        self.playhead_color = ACCENT
        self.hidden = False                      # treino de ouvido: só a pauta, sem as notas
        self.hidden_text = "🎧  Ouça e imite — as notas aparecem no final"
        self._top = 12.0
        self._note_items: dict[int, list[tuple[int, str]]] = {}
        self._layout: list[tuple[int, float, float]] = []  # por compasso: (linha, x0, x1)
        self._inner = (14.0, 12.0)
        self._playhead = None
        self._lit: int | None = None
        self._message = "Clique em “Novo ritmo” para começar"
        self.k = max(1.0, self.winfo_fpixels("1i") / 96)  # escala de DPI do Windows
        self.bind("<Configure>", lambda e: self.redraw())

    # -- API ---------------------------------------------------------------

    def set_pattern(self, pattern: Pattern | None) -> None:
        self.pattern = pattern
        self.statuses = None
        self.taps = []
        self.redraw()

    def set_results(self, statuses: list[str] | None, taps: list[tuple[float, str]]) -> None:
        self.statuses = statuses
        self.taps = taps
        self.redraw()

    def set_hidden(self, hidden: bool) -> None:
        if hidden != self.hidden:
            self.hidden = hidden
            self.redraw()

    def set_message(self, text: str) -> None:
        self._message = text
        self.redraw()

    def required_height(self, width: int) -> int:
        if not self.pattern:
            return int(2 * ROW_H * self.k)
        return int((24 + self._rows_for(width / self.k) * ROW_H) * self.k)

    def set_playhead(self, beat: float | None) -> None:
        """Posiciona o cursor (em batidas) e destaca a nota que está soando."""
        if self.pattern is None or beat is None or beat < 0 or beat > self.pattern.total_beats:
            if self._playhead is not None:
                self.itemconfigure(self._playhead, state="hidden")
            self._light(None)
            return
        row, x = self._beat_xy(beat)
        y0 = self._top + row * ROW_H + STAFF_TOP - 30
        if self._playhead is None:
            self._playhead = self.create_line(0, 0, 0, 0, fill=self.playhead_color, width=2)
        self.itemconfigure(self._playhead, fill=self.playhead_color)
        k = self.k
        self.coords(self._playhead, x * k, y0 * k, x * k, (y0 + 4 * SP + 60) * k)
        self.itemconfigure(self._playhead, state="normal")
        self.tag_raise(self._playhead)
        lit = None
        for i, n in enumerate(self.pattern.notes):
            if not n.rest and n.start <= beat < n.start + n.dur:
                lit = i
                break
        self._light(lit)

    # -- layout ------------------------------------------------------------

    def _rows_for(self, width: int) -> int:
        p = self.pattern
        avail = max(200, width - 112)
        # figuras curtas pedem mais espaço por tempo; até 3 linhas de pauta
        shortest = min((float(n.dur) for n in p.notes), default=1.0)
        px_per_beat = max(46.0, 24.0 / shortest)
        per_row = max(1, min(p.measures, int(avail // px_per_beat) // p.beats_per_measure))
        return min(3, math.ceil(p.measures / per_row))

    def _compute_layout(self, width: int) -> None:
        p = self.pattern
        rows = self._rows_for(width)
        per_row = math.ceil(p.measures / rows)
        # mesma largura de compasso em todas as linhas, para o tempo ficar alinhado
        mw = (width - 92 - 20) / per_row
        self._layout = []
        for m in range(p.measures):
            row, col = divmod(m, per_row)
            x0 = 92 + col * mw
            self._layout.append((row, x0, x0 + mw))

    def _beat_xy(self, beat: float) -> tuple[int, float]:
        p = self.pattern
        m = min(p.measures - 1, int(beat // p.beats_per_measure))
        row, x0, x1 = self._layout[m]
        frac = (beat - m * p.beats_per_measure) / p.beats_per_measure
        pad_l, pad_r = self._inner
        return row, x0 + pad_l + frac * (x1 - x0 - pad_l - pad_r)

    def _y(self, row: int, step: float) -> float:
        bottom = self._top + row * ROW_H + STAFF_TOP + 4 * SP
        return bottom - (step - BOTTOM_LINE_STEP) * SP / 2

    # -- desenho -----------------------------------------------------------

    def redraw(self) -> None:
        self.delete("all")
        self._playhead = None
        self._lit = None
        self._note_items = {}
        self._name_x: dict[int, float] = {}
        width = max(self.winfo_width(), 300) / self.k
        if self.pattern is None:
            self.create_text(width / 2, max(self.winfo_height(), 200) / self.k / 2, text=self._message,
                             fill=MUTED, font=("Segoe UI", 13))
            self.scale("all", 0, 0, self.k, self.k)
            return
        self._compute_layout(width)
        rows = self._layout[-1][0] + 1
        # centraliza as pautas na altura disponível
        self._top = max(4.0, (self.winfo_height() / self.k - rows * ROW_H) / 2 + 8)
        self._draw_staves(width)
        if self.hidden:
            self.create_text(width / 2, self._y(rows - 1, 30) + 30, text=self.hidden_text,
                             fill=MUTED, font=("Segoe UI", 12))
            self._draw_taps()
            self.scale("all", 0, 0, self.k, self.k)
            return
        sounding_index = 0
        groups: dict[int, list[int]] = {}
        for i, n in enumerate(self.pattern.notes):
            color = INK
            if not n.rest:
                if self.statuses and sounding_index < len(self.statuses):
                    color = STATUS_COLORS.get(self.statuses[sounding_index], INK)
                sounding_index += 1
            self._note_items[i] = []
            if n.rest:
                self._draw_rest(i, color)
            else:
                self._draw_head(i, color)
                groups.setdefault(n.group, []).append(i)
        for idxs in groups.values():
            self._draw_stems(idxs)
        self._draw_taps()
        if self.statuses:
            self._draw_legend(width)
        self.scale("all", 0, 0, self.k, self.k)

    def _draw_legend(self, width: float) -> None:
        y = self.winfo_height() / self.k - 16
        x = width - 16
        items = (("perdida / extra", STATUS_COLORS["perdeu"]), ("ok", STATUS_COLORS["ok"]),
                 ("bom", STATUS_COLORS["bom"]), ("perfeito", STATUS_COLORS["perfeito"]))
        for label, color in items:
            t = self.create_text(x, y, text=label, anchor="e", fill=INK, font=("Segoe UI", 9))
            bx0, _, bx1, _ = self.bbox(t)
            x0 = x - (bx1 - bx0) / self.k   # a fonte já vem em pixels reais; o layout é lógico
            self.create_oval(x0 - 14, y - 5, x0 - 4, y + 5, fill=color, outline=color)
            x = x0 - 26

    def _draw_staves(self, width: int) -> None:
        p = self.pattern
        rows = max(r for r, _, _ in self._layout) + 1
        for row in range(rows):
            measures = [(m, x0, x1) for m, (r, x0, x1) in enumerate(self._layout) if r == row]
            left, right = 22, measures[-1][2]
            for k in range(5):
                y = self._y(row, BOTTOM_LINE_STEP + 2 * k)
                self.create_line(left, y, right, y, fill=INK, width=1)
            self.create_line(left, self._y(row, 38), left, self._y(row, 30), fill=INK, width=1)
            # clave de sol (glifo Unicode) com a espiral centrada na linha do Sol
            self.create_text(40, self._y(row, 32) - 6, text="\U0001D11E", fill=INK,
                             font=("Segoe UI Symbol", 36), anchor="center")
            if row == 0:
                for txt, step in ((str(p.beats_per_measure), 36), ("4", 32)):
                    self.create_text(72, self._y(row, step), text=txt, fill=INK,
                                     font=("Georgia", 19, "bold"))
            for m, x0, x1 in measures:
                top, bot = self._y(row, 38), self._y(row, 30)
                if m == p.measures - 1:
                    self.create_line(x1 - 7, top, x1 - 7, bot, fill=INK, width=1)
                    self.create_rectangle(x1 - 4, top, x1, bot, fill=INK, outline=INK)
                else:
                    self.create_line(x1, top, x1, bot, fill=INK, width=1)
                self.create_text(x0 + 4, top - 12, text=str(m + 1), fill=MUTED,
                                 font=("Segoe UI", 8), anchor="w")

    def _note_x(self, i: int) -> tuple[int, float]:
        n = self.pattern.notes[i]
        row, x = self._beat_xy(float(n.start))
        return row, x + 7

    def _add(self, i: int, item: int, kind: str) -> None:
        self._note_items[i].append((item, kind))

    def _draw_head(self, i: int, color: str) -> None:
        n = self.pattern.notes[i]
        row, x = self._note_x(i)
        step, acc = spell(n.pitch)
        y = self._y(row, step)
        # linhas suplementares
        for ledger in range(28, step - 1, -2):
            yy = self._y(row, ledger)
            self.create_line(x - 10, yy, x + 10, yy, fill=INK, width=1.3)
        for ledger in range(40, step + 1, 2):
            yy = self._y(row, ledger)
            self.create_line(x - 10, yy, x + 10, yy, fill=INK, width=1.3)
        hollow = n.event.base >= 2
        pts = _ellipse(x, y, 6.6, 4.6)
        if hollow:
            self._add(i, self.create_polygon(pts, fill=PAPER, outline=color, width=2, smooth=True), "outline")
        else:
            self._add(i, self.create_polygon(pts, fill=color, outline=color, smooth=True), "both")
        if acc:
            self._add(i, self.create_text(x - 15, y, text=acc, fill=color, font=("Segoe UI Symbol", 13)), "line")
        if n.event.dotted:
            dy = -SP / 2 if step % 2 == 0 else 0
            self._add(i, self.create_oval(x + 9, y + dy - 2, x + 13, y + dy + 2, fill=color, outline=color), "both")
        last_x = self._name_x.get(row, -1e9)
        if self.show_names and x - last_x >= 22:
            self._name_x[row] = x
            self._add(i, self.create_text(x, self._y(row, 30) + 34, text=note_name(n.pitch, octave=False),
                                          fill=color if self.statuses else MUTED, font=("Segoe UI", 8)), "name")

    def _stem_geometry(self, i: int, up: bool) -> tuple[int, float, float]:
        n = self.pattern.notes[i]
        row, x = self._note_x(i)
        y = self._y(row, spell(n.pitch)[0])
        return row, (x + 5.6 if up else x - 5.6), y

    def _draw_stems(self, idxs: list[int]) -> None:
        notes = self.pattern.notes
        stemmed = [i for i in idxs if notes[i].event.base < 4]
        # agrupa colcheias/semicolcheias consecutivas (sem pausas no meio) para as barras
        runs, cur = [], []
        for i in stemmed:
            if notes[i].event.flags and cur and i == cur[-1] + 1:
                cur.append(i)
                continue
            if cur:
                runs.append(cur)
            cur = [i]
        if cur:
            runs.append(cur)
        for run in runs:
            if len(run) == 1 or not all(notes[i].event.flags for i in run):
                for i in run:
                    self._draw_single_stem(i)
            else:
                self._draw_beamed(run)

    def _draw_single_stem(self, i: int) -> None:
        n = self.pattern.notes[i]
        step = spell(n.pitch)[0]
        up = step < MIDDLE_LINE_STEP
        row, sx, y = self._stem_geometry(i, up)
        end = y - STEM if up else y + STEM
        end = min(end, self._y(row, MIDDLE_LINE_STEP)) if up else max(end, self._y(row, MIDDLE_LINE_STEP))
        color = self._color_of(i)
        self._add(i, self.create_line(sx, y, sx, end, fill=color, width=1.4), "line")
        for k in range(n.event.flags):
            yy = end + (k * 8 if up else -k * 8)
            sign = 1 if up else -1
            pts = [sx, yy, sx + 4, yy + sign * 7, sx + 10, yy + sign * 12, sx + 8, yy + sign * 22]
            self._add(i, self.create_line(pts, fill=color, width=2.2, smooth=True), "line")

    def _draw_beamed(self, run: list[int]) -> None:
        notes = self.pattern.notes
        steps = [spell(notes[i].pitch)[0] for i in run]
        up = sum(steps) / len(steps) < MIDDLE_LINE_STEP
        geo = [self._stem_geometry(i, up) for i in run]
        ys = [g[2] for g in geo]
        beam_y = (min(ys) - STEM) if up else (max(ys) + STEM)
        mid = self._y(geo[0][0], MIDDLE_LINE_STEP)
        beam_y = min(beam_y, mid) if up else max(beam_y, mid)
        for i, (_, sx, y) in zip(run, geo):
            self._add(i, self.create_line(sx, y, sx, beam_y, fill=self._color_of(i), width=1.4), "line")
        thick, gap = 5, 8
        sign = 1 if up else -1

        def beam(xa: float, xb: float, level: int) -> None:
            y0 = beam_y + sign * level * gap
            y1 = y0 + sign * thick
            self.create_polygon(xa - 0.7, y0, xb + 0.7, y0, xb + 0.7, y1, xa - 0.7, y1, fill=INK, outline=INK)

        xs = [g[1] for g in geo]
        beam(xs[0], xs[-1], 0)
        # barras secundárias (semicolcheias): contínuas ou "tocos"
        k = 0
        while k < len(run):
            if notes[run[k]].event.flags < 2:
                k += 1
                continue
            j = k
            while j + 1 < len(run) and notes[run[j + 1]].event.flags >= 2:
                j += 1
            if j > k:
                beam(xs[k], xs[j], 1)
            else:
                stub = 9
                if k == 0:
                    beam(xs[k], xs[k] + stub, 1)
                else:
                    beam(xs[k] - stub, xs[k], 1)
            k = j + 1
        if notes[run[0]].event.tuplet == 3:
            ytxt = beam_y - 10 if up else min(ys) - 13
            self.create_text((xs[0] + xs[-1]) / 2, ytxt, text="3", fill=INK,
                             font=("Georgia", 10, "bold italic"))

    def _color_of(self, i: int) -> str:
        for item, kind in self._note_items.get(i, []):
            if kind in ("both", "outline"):
                return self.itemcget(item, "outline")
        return INK

    def _draw_rest(self, i: int, color: str) -> None:
        n = self.pattern.notes[i]
        row, x = self._note_x(i)
        mid = self._y(row, MIDDLE_LINE_STEP)
        base = n.event.base
        if base == 4:
            y = self._y(row, 36)
            self._add(i, self.create_rectangle(x - 6, y, x + 6, y + 5, fill=color, outline=color), "both")
        elif base == 2:
            y = mid
            self._add(i, self.create_rectangle(x - 6, y - 5, x + 6, y, fill=color, outline=color), "both")
        elif base == 1:
            # pausa de semínima: traço fino, cunha grossa, traço fino e gancho
            self._add(i, self.create_line(x - 3, mid - 15, x + 3, mid - 7, fill=color, width=1.6), "line")
            self._add(i, self.create_polygon(x + 1, mid - 9, x + 5, mid - 5, x - 1, mid + 1, x - 4, mid - 3,
                                             fill=color, outline=color), "both")
            self._add(i, self.create_line(x - 2, mid - 1, x + 4, mid + 6, fill=color, width=1.6), "line")
            self._add(i, self.create_line(x + 4, mid + 6, x - 3, mid + 4, x - 4, mid + 9, x + 1, mid + 14,
                                          fill=color, width=2.6, smooth=True), "line")
        else:
            hooks = 1 if base == F(1, 2) else 2
            top = mid - 6
            self._add(i, self.create_line(x + 5, top, x - 2, top + 9 + 8 * hooks, fill=color, width=1.6), "line")
            for k in range(hooks):
                hx = x + 5 - k * 3.2
                hy = top + k * 8
                self._add(i, self.create_oval(hx - 9, hy - 2, hx - 4, hy + 3, fill=color, outline=color), "both")
                self._add(i, self.create_line(hx - 6, hy + 2, hx - 2, hy + 3, hx, hy, fill=color, width=1.4,
                                              smooth=True), "line")

    def add_tap(self, beat: float, color: str) -> None:
        """Desenha uma batida do usuário em tempo real (modo treino)."""
        self.taps.append((beat, color))
        item = self._draw_tap(beat, color)
        if item is not None:
            self.scale(item, 0, 0, self.k, self.k)

    def _draw_taps(self) -> None:
        for beat, color in self.taps:
            self._draw_tap(beat, color)

    def _draw_tap(self, beat: float, color: str) -> int | None:
        if self.pattern is None or beat < -0.5 or beat > self.pattern.total_beats + 0.5:
            return None
        row, x = self._beat_xy(min(max(beat, 0), self.pattern.total_beats))
        x += 7
        y = self._y(row, 30) + 50
        return self.create_polygon(x - 5, y + 7, x + 5, y + 7, x, y, fill=color, outline=color)

    def _light(self, index: int | None) -> None:
        if index == self._lit:
            return
        if self._lit is not None:
            self._paint(self._lit, None)
        self._lit = index
        if index is not None:
            self._paint(index, ACCENT)

    def _paint(self, i: int, color: str | None) -> None:
        name_color = color
        if color is None:
            color, name_color = INK, MUTED
            if self.statuses:
                k = sum(1 for n in self.pattern.notes[:i] if not n.rest)
                if k < len(self.statuses):
                    color = name_color = STATUS_COLORS.get(self.statuses[k], INK)
        for item, kind in self._note_items.get(i, []):
            if kind == "outline":
                self.itemconfigure(item, outline=color)
            elif kind == "both":
                self.itemconfigure(item, fill=color, outline=color)
            elif kind == "line":
                self.itemconfigure(item, fill=color)
            elif kind == "name":
                self.itemconfigure(item, fill=name_color)
