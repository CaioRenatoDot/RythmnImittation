# -*- mode: python ; coding: utf-8 -*-
# Gere com:  python build.py   (cria o ícone e chama o PyInstaller com este arquivo)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'unittest', 'pydoc', 'doctest', 'matplotlib', 'scipy', 'pandas', 'IPython'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RythmImitation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='build/RythmImitation.ico',
    version='build/version_info.txt',
)
