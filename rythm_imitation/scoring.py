"""Pontuação do modo treino: compara as batidas do usuário com o ritmo esperado."""

from __future__ import annotations

from dataclasses import dataclass, field

PERFECT_S = 0.045
GOOD_S = 0.090
EXTRA_PENALTY = 30
POINTS = {"perfeito": 100, "bom": 80, "ok": 50, "perdeu": 0}


@dataclass
class NoteResult:
    expected: float
    status: str               # perfeito | bom | ok | perdeu
    error: float | None       # tap - esperado (s); negativo = adiantado


@dataclass
class ScoreResult:
    notes: list[NoteResult]
    extras: list[float] = field(default_factory=list)
    percent: float = 0.0
    window: float = 0.0

    @property
    def mean_offset_ms(self) -> float | None:
        errs = [n.error for n in self.notes if n.error is not None]
        return 1000 * sum(errs) / len(errs) if errs else None

    def count(self, status: str) -> int:
        return sum(1 for n in self.notes if n.status == status)

    @property
    def grade(self) -> str:
        if self.percent >= 90:
            return "Excelente!"
        if self.percent >= 75:
            return "Muito bom!"
        if self.percent >= 50:
            return "Bom começo"
        return "Continue praticando"

    def summary(self) -> str:
        parts = [f"{self.percent:.0f}% — {self.grade}",
                 f"{self.count('perfeito')} perfeitas · {self.count('bom')} boas · "
                 f"{self.count('ok')} ok · {self.count('perdeu')} perdidas · {len(self.extras)} extras"]
        off = self.mean_offset_ms
        if off is not None and abs(off) >= 15:
            parts.append(f"tendência: {abs(off):.0f} ms {'adiantado' if off < 0 else 'atrasado'}")
        return "\n".join(parts)


def match_window(expected: list[float]) -> float:
    gaps = [b - a for a, b in zip(expected, expected[1:]) if b > a]
    if not gaps:
        return 0.2
    return max(0.08, min(0.2, 0.45 * min(gaps)))


def _classify(err: float, window: float) -> str | None:
    a = abs(err)
    if a <= PERFECT_S:
        return "perfeito"
    if a <= GOOD_S:
        return "bom"
    if a <= window:
        return "ok"
    return None


def score_taps(expected: list[float], taps: list[float]) -> ScoreResult:
    """Alinha batidas e notas esperadas (ambas em segundos) maximizando a pontuação.

    Programação dinâmica no estilo distância de edição: cada nota pode ser
    acertada por uma batida dentro da janela ou perdida; cada batida que sobra
    conta como extra e desconta pontos.
    """
    expected = sorted(expected)
    taps = sorted(taps)
    window = match_window(expected)
    ne, nt = len(expected), len(taps)
    neg = float("-inf")
    dp = [[neg] * (nt + 1) for _ in range(ne + 1)]
    back: list[list[str]] = [[""] * (nt + 1) for _ in range(ne + 1)]
    dp[0][0] = 0.0
    for i in range(ne + 1):
        for j in range(nt + 1):
            cur = dp[i][j]
            if cur == neg:
                continue
            if i < ne and cur > dp[i + 1][j]:                       # nota perdida
                dp[i + 1][j], back[i + 1][j] = cur, "miss"
            if j < nt and cur - EXTRA_PENALTY > dp[i][j + 1]:       # batida extra
                dp[i][j + 1], back[i][j + 1] = cur - EXTRA_PENALTY, "extra"
            if i < ne and j < nt:
                status = _classify(taps[j] - expected[i], window)
                if status:
                    # desempate por erro menor, para escolher a batida mais próxima
                    val = cur + POINTS[status] - abs(taps[j] - expected[i])
                    if val > dp[i + 1][j + 1]:
                        dp[i + 1][j + 1], back[i + 1][j + 1] = val, "hit"

    notes: list[NoteResult] = []
    extras: list[float] = []
    i, j = ne, nt
    while i or j:
        step = back[i][j]
        if step == "hit":
            err = taps[j - 1] - expected[i - 1]
            notes.append(NoteResult(expected[i - 1], _classify(err, window), err))
            i, j = i - 1, j - 1
        elif step == "miss":
            notes.append(NoteResult(expected[i - 1], "perdeu", None))
            i -= 1
        else:
            extras.append(taps[j - 1])
            j -= 1
    notes.reverse()
    extras.reverse()

    total = sum(POINTS[n.status] for n in notes) - EXTRA_PENALTY * len(extras)
    percent = max(0.0, min(100.0, 100.0 * total / (100 * ne))) if ne else 0.0
    return ScoreResult(notes, extras, percent, window)
