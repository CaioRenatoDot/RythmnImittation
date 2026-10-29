"""Localização de arquivos empacotados (funciona no código-fonte e no .exe)."""

from __future__ import annotations

import os
import sys


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)
