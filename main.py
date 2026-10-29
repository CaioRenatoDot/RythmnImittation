"""Ponto de entrada: `python main.py` (também usado pelo PyInstaller).

`RythmImitation.exe --selftest relatorio.txt` abre a janela, toca um ritmo em
volume zero e grava um relatório — útil para validar o executável gerado.
"""

import sys


def selftest(report_path: str) -> None:
    import time
    import traceback

    lines = []
    try:
        from rythm_imitation import __version__
        from rythm_imitation.app import App
        from rythm_imitation.resources import resource_path
        import os

        lines.append(f"versao={__version__}")
        lines.append(f"logo={os.path.exists(resource_path('logo.png'))}")
        app = App()
        app.player.volume = 0.0

        def check():
            app.toggle_play()
            t0 = time.perf_counter()
            while time.perf_counter() - t0 < 1.0:
                app.root.update()
            lines.append(f"backend={app.player.backend}")
            lines.append(f"tocando={app.player.playing}")
            lines.append(f"posicao={app.player.position()}")
            lines.append(f"erro_audio={app.player.last_error}")
            lines.append(f"notas={len(app.pattern.sounding())}")
            app._on_close()

        app.root.after(800, check)
        app.run()
        lines.append("OK")
    except Exception:
        lines.append(traceback.format_exc())
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        selftest(sys.argv[2])
    else:
        from rythm_imitation.app import main

        main()
