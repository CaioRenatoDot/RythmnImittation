"""Gera o executável do Windows em dist/RythmImitation.exe.

Uso:
    python -m venv .venv
    .venv\\Scripts\\pip install -r requirements-dev.txt
    .venv\\Scripts\\python build.py
"""

import os
import subprocess
import sys

from PIL import Image

from rythm_imitation import APP_NAME, AUTHOR, __version__

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}), prodvers=({v}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', '{author}'),
      StringStruct('FileDescription', '{name} - gerador e treinador de ritmos'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"""


def main() -> None:
    os.makedirs(BUILD, exist_ok=True)
    logo = Image.open(os.path.join(ROOT, "logo.png")).convert("RGBA")
    logo.save(os.path.join(BUILD, "RythmImitation.ico"),
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    parts = [int(p) for p in __version__.split(".")] + [0] * 4
    with open(os.path.join(BUILD, "version_info.txt"), "w", encoding="utf-8") as fh:
        fh.write(VERSION_INFO.format(v=", ".join(map(str, parts[:4])), version=__version__,
                                     name=APP_NAME, author=AUTHOR))

    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "RythmImitation.spec"],
                   cwd=ROOT, check=True)
    exe = os.path.join(ROOT, "dist", "RythmImitation.exe")
    print(f"\nPronto: {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
