"""Teoria musical: figuras, compassos, escalas e geração de padrões rítmicos.

Todas as durações são frações da semínima (1 = uma batida em compassos x/4),
o que mantém a aritmética exata mesmo com tercinas.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from fractions import Fraction as F

# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """Uma figura escrita (nota ou pausa)."""

    base: F                # 4 semibreve, 2 mínima, 1 semínima, 1/2 colcheia, 1/4 semicolcheia
    rest: bool = False
    dotted: bool = False
    tuplet: int = 0        # 3 = tercina

    @property
    def dur(self) -> F:
        d = self.base
        if self.dotted:
            d = d * F(3, 2)
        if self.tuplet == 3:
            d = d * F(2, 3)
        return d

    @property
    def flags(self) -> int:
        """Quantidade de colchetes/barras (0 para semínima ou maior)."""
        if self.base <= F(1, 4):
            return 2
        if self.base <= F(1, 2):
            return 1
        return 0

    @property
    def name(self) -> str:
        names = {F(4): "semibreve", F(2): "mínima", F(1): "semínima",
                 F(1, 2): "colcheia", F(1, 4): "semicolcheia"}
        n = names[self.base]
        if self.rest:
            n = "pausa de " + n
        if self.dotted:
            n += " pontuada"
        if self.tuplet == 3:
            n += " (tercina)"
        return n

    @property
    def symbol(self) -> str:
        if self.rest:
            sym = {F(4): "𝄻", F(2): "𝄼", F(1): "𝄽", F(1, 2): "𝄾", F(1, 4): "𝄿"}[self.base]
        else:
            sym = {F(4): "𝅝", F(2): "𝅗𝅥", F(1): "♩", F(1, 2): "♪", F(1, 4): "𝅘𝅥𝅯"}[self.base]
        if self.dotted:
            sym += "."
        return sym


w = Event(F(4))
h = Event(F(2))
hr = Event(F(2), rest=True)
q = Event(F(1))
qr = Event(F(1), rest=True)
qd = Event(F(1), dotted=True)
e = Event(F(1, 2))
er = Event(F(1, 2), rest=True)
ed = Event(F(1, 2), dotted=True)
s = Event(F(1, 4))
sr = Event(F(1, 4), rest=True)
t = Event(F(1, 2), tuplet=3)


@dataclass(frozen=True)
class Cell:
    """Célula rítmica: um bloco de figuras que ocupa um número inteiro de batidas."""

    level: int
    weight: float
    events: tuple[Event, ...]

    @property
    def beats(self) -> int:
        total = sum((ev.dur for ev in self.events), F(0))
        assert total.denominator == 1, self.events
        return int(total)

    @property
    def has_rest(self) -> bool:
        return any(ev.rest for ev in self.events)

    @property
    def has_note(self) -> bool:
        return any(not ev.rest for ev in self.events)


CELLS: tuple[Cell, ...] = (
    # Nível 1 - semibreve, mínima, semínima e suas pausas
    Cell(1, 10, (q,)),
    Cell(1, 3, (qr,)),
    Cell(1, 5, (h,)),
    Cell(1, 1, (hr,)),
    Cell(1, 1, (w,)),
    # Nível 2 - colcheias e semínima pontuada
    Cell(2, 10, (e, e)),
    Cell(2, 3, (er, e)),
    Cell(2, 2, (e, er)),
    Cell(2, 4, (qd, e)),
    # Nível 3 - semicolcheias, colcheia pontuada e síncope
    Cell(3, 6, (s, s, s, s)),
    Cell(3, 5, (e, s, s)),
    Cell(3, 5, (s, s, e)),
    Cell(3, 4, (ed, s)),
    Cell(3, 3, (e, q, e)),
    Cell(3, 2, (sr, s, s, s)),
    # Nível 4 - tercinas, "scotch snap" e contratempos
    Cell(4, 5, (t, t, t)),
    Cell(4, 3, (s, e, s)),
    Cell(4, 3, (s, ed)),
    Cell(4, 2, (er, s, s)),
    Cell(4, 2, (er, q, e)),
)

LEVELS = {1: "1 · Iniciante", 2: "2 · Básico", 3: "3 · Intermediário", 4: "4 · Avançado"}
LEVEL_HINTS = {
    1: "semibreves, mínimas, semínimas e pausas",
    2: "+ colcheias e semínima pontuada",
    3: "+ semicolcheias, colcheia pontuada e síncope",
    4: "+ tercinas e contratempos",
}

TIME_SIGNATURES = {"2/4": 2, "3/4": 3, "4/4": 4, "5/4": 5}

# ---------------------------------------------------------------------------
# Escalas e nomes de notas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scale:
    name: str
    notes: tuple[int, ...]   # números MIDI, em ordem crescente
    tonic: int


SCALES: dict[str, Scale] = {sc.name: sc for sc in (
    Scale("Clássico (Dó-Mi-Sol-Lá)", (60, 64, 67, 69, 72), 60),
    Scale("Dó maior", (60, 62, 64, 65, 67, 69, 71, 72, 74), 60),
    Scale("Lá menor", (57, 59, 60, 62, 64, 65, 67, 69, 71, 72), 57),
    Scale("Pentatônica maior (Sol)", (62, 64, 67, 69, 71, 74, 76), 67),
    Scale("Pentatônica menor (Lá)", (57, 60, 62, 64, 67, 69, 72), 57),
    Scale("Blues (Lá)", (57, 60, 62, 63, 64, 67, 69, 72), 57),
    Scale("Nota única (Lá 440 Hz)", (69,), 69),
)}

_PC_SPELLING = {
    # classe de altura -> (índice da letra C=0..B=6, acidente)
    0: (0, ""), 1: (0, "♯"), 2: (1, ""), 3: (2, "♭"), 4: (2, ""), 5: (3, ""),
    6: (3, "♯"), 7: (4, ""), 8: (4, "♯"), 9: (5, ""), 10: (6, "♭"), 11: (6, ""),
}
_LETTERS_PT = ("Dó", "Ré", "Mi", "Fá", "Sol", "Lá", "Si")


def spell(midi: int) -> tuple[int, str]:
    """Retorna (passo diatônico absoluto, acidente). Dó4 (MIDI 60) = 28."""
    octave = midi // 12 - 1
    letter, acc = _PC_SPELLING[midi % 12]
    return octave * 7 + letter, acc


def note_name(midi: int, octave: bool = True) -> str:
    step, acc = spell(midi)
    name = _LETTERS_PT[step % 7] + acc
    return f"{name}{step // 7}" if octave else name


def midi_to_hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


# ---------------------------------------------------------------------------
# Padrões
# ---------------------------------------------------------------------------


@dataclass
class Note:
    start: F            # em batidas, desde o início do padrão
    event: Event
    pitch: int | None   # MIDI; None para pausas
    group: int          # id da célula (usado para agrupar barras de ligação)
    measure: int

    @property
    def dur(self) -> F:
        return self.event.dur

    @property
    def rest(self) -> bool:
        return self.event.rest


@dataclass
class Pattern:
    notes: list[Note]
    beats_per_measure: int
    measures: int
    level: int
    scale: str
    seed: int
    meta: dict = field(default_factory=dict)

    @property
    def total_beats(self) -> int:
        return self.beats_per_measure * self.measures

    @property
    def time_signature(self) -> str:
        return f"{self.beats_per_measure}/4"

    def sounding(self) -> list[Note]:
        return [n for n in self.notes if not n.rest]

    def onsets(self) -> list[F]:
        return [n.start for n in self.notes if not n.rest]

    def duration_seconds(self, bpm: float) -> float:
        return self.total_beats * 60.0 / bpm

    def rhythm_text(self) -> str:
        """Representação textual com barras de compasso, ex.: '♩ ♪♪ | 𝅗𝅥 ♩'."""
        out, last_measure, last_group = [], 0, None
        for n in self.notes:
            if n.measure != last_measure:
                out.append(" |")
                last_measure = n.measure
            sep = "" if n.group == last_group and n.event.flags else " "
            out.append(sep + n.event.symbol)
            last_group = n.group
        return "".join(out).strip()

    def melody_text(self) -> str:
        return " ".join(note_name(n.pitch) for n in self.notes if n.pitch is not None)


def _cell_fits(cell: Cell, pos: int, beats_per_measure: int) -> bool:
    if pos + cell.beats > beats_per_measure:
        return False
    if cell.beats == 4:
        return pos == 0
    if cell.beats == 2 and beats_per_measure % 2 == 0:
        # em compassos pares, figuras de 2 tempos não atravessam o meio do compasso
        return pos % 2 == 0
    return True


def _pool(level: int, rests: bool) -> list[Cell]:
    return [c for c in CELLS if c.level <= level and (rests or not c.has_rest)]


def _weight(cell: Cell, level: int) -> float:
    # dá destaque às figuras novas do nível escolhido
    return cell.weight * (2.2 if cell.level == level and level > 1 else 1.0)


def _measure_cells(rng: random.Random, pool: list[Cell], level: int,
                   beats_per_measure: int, last: bool) -> list[Cell]:
    for _ in range(200):
        pos, cells = 0, []
        while pos < beats_per_measure:
            remaining = beats_per_measure - pos
            if last and remaining <= 2:
                # cadência: termina com uma nota mais longa na maioria das vezes
                if remaining == 2 and pos % 2 == 0 and rng.random() < 0.45:
                    cells.append(Cell(1, 1, (h,)))
                    break
                if remaining == 1 and rng.random() < 0.7:
                    cells.append(Cell(1, 1, (q,)))
                    break
            options = [c for c in pool if _cell_fits(c, pos, beats_per_measure)]
            cell = rng.choices(options, weights=[_weight(c, level) for c in options])[0]
            cells.append(cell)
            pos += cell.beats
        if any(c.has_note for c in cells):
            return cells
    return [Cell(1, 1, (q,))] * beats_per_measure


def _melody(rng: random.Random, scale: Scale, count: int) -> list[int]:
    notes = scale.notes
    if len(notes) == 1 or count == 0:
        return [notes[0]] * count
    steps = (-4, -3, -2, -1, 0, 1, 2, 3, 4)
    weights = (0.2, 0.4, 1.2, 3.0, 1.2, 3.0, 1.2, 0.4, 0.2)
    idx = notes.index(scale.tonic)
    out = []
    for _ in range(count):
        out.append(notes[idx])
        nxt = idx + rng.choices(steps, weights)[0]
        if nxt < 0 or nxt >= len(notes):      # reflete nas bordas da escala
            nxt = idx - (nxt - idx)
        idx = max(0, min(len(notes) - 1, nxt))
    if count > 1:
        # resolve na tônica (a mais próxima da penúltima nota)
        tonics = [n for n in notes if n % 12 == scale.tonic % 12]
        out[-1] = min(tonics, key=lambda n: abs(n - out[-2]))
    return out


def generate(level: int = 2, beats_per_measure: int = 2, measures: int = 5,
             scale: str = "Clássico (Dó-Mi-Sol-Lá)", rests: bool = True,
             seed: int | None = None) -> Pattern:
    """Gera um padrão rítmico com melodia.

    Os padrões são reprodutíveis: a mesma semente e os mesmos parâmetros
    produzem sempre o mesmo resultado.
    """
    if seed is None:
        seed = random.randrange(1_000_000)
    rng = random.Random(f"{seed}-{level}-{beats_per_measure}-{measures}-{rests}")
    pool = _pool(level, rests)

    notes: list[Note] = []
    start, group = F(0), 0
    for m in range(measures):
        cells = _measure_cells(rng, pool, level, beats_per_measure, last=m == measures - 1)
        if m == 0 and level <= 2 and cells[0].events[0].rest:
            cells[0] = Cell(1, 1, (q,)) if cells[0].beats == 1 else Cell(1, 1, (h,))
        for cell in cells:
            for ev in cell.events:
                notes.append(Note(start, ev, None, group, m))
                start += ev.dur
            group += 1

    sc = SCALES.get(scale) or next(iter(SCALES.values()))
    melody = iter(_melody(rng, sc, sum(1 for n in notes if not n.rest)))
    for n in notes:
        if not n.rest:
            n.pitch = next(melody)

    return Pattern(notes, beats_per_measure, measures, level, sc.name, seed)
