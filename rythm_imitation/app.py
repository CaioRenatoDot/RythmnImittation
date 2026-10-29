"""Interface gráfica do RythmImitation."""

from __future__ import annotations

import csv
import os
import queue
import random
import statistics
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from . import APP_NAME, AUTHOR, __version__
from .midi import write_midi
from .notation import MUTED, PAPER, STATUS_COLORS, ScoreView
from .player import Player, output_devices
from .resources import resource_path
from .scoring import score_taps
from .synth import (INSTRUMENTS, SR, Rendered, ffmpeg_path, fit_duration, render, render_clicks,
                    render_training, write_mp3, write_wav)
from .theory import LEVEL_HINTS, LEVELS, SCALES, TIME_SIGNATURES, Pattern, generate

FONT = "Segoe UI"
TAP_PENDING = "#8a8578"
TEXT_INPUT_CLASSES = {"TEntry", "Entry", "TSpinbox", "Spinbox", "Text"}
CALIB_BPM, CALIB_LEAD, CALIB_BEATS = 90, 4, 16


class App:
    def __init__(self) -> None:
        self.root = ttk.Window(title=f"{APP_NAME} — gerador e treinador de ritmos",
                               themename="darkly", size=(1240, 820), minsize=(1060, 700))
        self.style = ttk.Style()
        self.player = Player()
        self.pattern: Pattern | None = None
        self.history: list[int] = []
        self.rendered: Rendered | None = None
        self.mode = "idle"            # idle | play | train | calib
        self.taps: list[float] = []
        self.scores: list[float] = []
        self._render_cache: dict[tuple, Rendered] = {}
        self._tick_id: str | None = None
        self._space_down = False
        self._batch_queue: queue.Queue = queue.Queue()
        self._batch_running = False
        self._ffmpeg = ffmpeg_path()

        self._init_vars()
        self._load_images()
        self._build()
        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, lambda: self.new_pattern())

    # ------------------------------------------------------------------ setup

    def _init_vars(self) -> None:
        r = self.root
        self.bpm_var = tk.IntVar(r, 100)
        self.ts_var = tk.StringVar(r, "2/4")
        self.measures_var = tk.IntVar(r, 5)
        self.level_var = tk.StringVar(r, LEVELS[2])
        self.scale_var = tk.StringVar(r, next(iter(SCALES)))
        self.instrument_var = tk.StringVar(r, "Piano elétrico")
        self.rests_var = tk.BooleanVar(r, True)
        self.metro_var = tk.BooleanVar(r, False)
        self.countin_var = tk.BooleanVar(r, True)
        self.loop_var = tk.BooleanVar(r, False)
        self.names_var = tk.BooleanVar(r, True)
        self.volume_var = tk.DoubleVar(r, 85)
        self.latency_var = tk.IntVar(r, 0)
        self.device_var = tk.StringVar(r)
        self.seed_var = tk.StringVar(r)
        self.status_var = tk.StringVar(r, "Pronto.")
        self.duration_var = tk.StringVar(r)
        self.summary_var = tk.StringVar(r)
        self.level_hint_var = tk.StringVar(r, LEVEL_HINTS[2])
        self.ear_var = tk.BooleanVar(r, False)
        self.phase_var = tk.StringVar(r, "Modo treino")
        self.result_var = tk.StringVar(r, "Pressione  T  (ou o botão “Treinar”) para ouvir o ritmo e depois "
                                          "imitá-lo com a barra de ESPAÇO.")
        self.best_var = tk.StringVar(r, "")
        # exportação
        self.exp_metro_var = tk.BooleanVar(r, False)
        self.exp_countin_var = tk.BooleanVar(r, False)
        self.exp_fixed_var = tk.BooleanVar(r, False)
        self.exp_seconds_var = tk.DoubleVar(r, 6.0)
        self.folder_var = tk.StringVar(r, os.path.join(os.path.expanduser("~"), "Music", "RythmImitation"))
        self.qty_var = tk.IntVar(r, 10)
        self.fmt_wav_var = tk.BooleanVar(r, True)
        self.fmt_mp3_var = tk.BooleanVar(r, False)
        self.fmt_mid_var = tk.BooleanVar(r, False)
        self.csv_var = tk.BooleanVar(r, True)
        self.open_folder_var = tk.BooleanVar(r, True)

    def _load_images(self) -> None:
        self.logo_img = self.icon_img = None
        path = resource_path("logo.png")
        if os.path.exists(path):
            # o Tk lê PNG nativamente; reduzir por amostragem mantém o pixel-art nítido
            full = tk.PhotoImage(master=self.root, file=path)
            factor = max(1, full.width() // 64)
            self.logo_img = full.subsample(factor, factor)
            self.icon_img = full.subsample(max(1, factor // 2), max(1, factor // 2))
            self.root.iconphoto(True, self.icon_img)

    def _build(self) -> None:
        root = self.root
        colors = self.style.colors

        # cabeçalho
        header = ttk.Frame(root, padding=(18, 12, 18, 6))
        header.pack(fill="x")
        if self.logo_img:
            tk.Label(header, image=self.logo_img, bd=0, bg=PAPER).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, text=APP_NAME, font=(FONT, 22, "bold")).pack(anchor="w")
        ttk.Label(titles, text="Gere, ouça, exporte e imite padrões rítmicos melódicos",
                  font=(FONT, 11), foreground=colors.light).pack(anchor="w")
        ttk.Label(header, text=f"v{__version__}", foreground=colors.light).pack(side="right", anchor="n")

        ttk.Separator(root).pack(fill="x", padx=18)

        body = ttk.Frame(root, padding=(18, 10))
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_sidebar(body).grid(row=0, column=0, sticky="nsw", padx=(0, 14))

        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=0, column=1, sticky="nsew")
        self.notebook.add(self._build_practice(self.notebook), text="  🎵  Praticar  ")
        self.notebook.add(self._build_batch(self.notebook), text="  📦  Gerar em lote  ")

        # barra de status
        status = ttk.Frame(root, padding=(18, 4, 18, 8))
        status.pack(fill="x", side="bottom")
        ttk.Label(status, textvariable=self.status_var, foreground=colors.light).pack(side="left")
        ttk.Label(status, text=f"Feito por {AUTHOR}", font=(FONT, 8), foreground="#888").pack(side="right")

    def _section(self, parent, text: str) -> None:
        ttk.Label(parent, text=text.upper(), font=(FONT, 8, "bold"),
                  foreground=self.style.colors.info).pack(anchor="w", pady=(12, 4))

    def _labeled(self, parent, text: str, widget_factory, tip: str | None = None):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=text, width=13).pack(side="left")
        widget = widget_factory(row)
        widget.pack(side="left", fill="x", expand=True)
        if tip:
            ttk.ToolTip(widget, text=tip, wraplength=260)
        return widget

    def _combo(self, values, var, callback):
        def factory(parent):
            cb = ttk.Combobox(parent, values=list(values), textvariable=var, state="readonly", width=24)
            cb.bind("<<ComboboxSelected>>", lambda e: (callback(), self.score.focus_set()))
            return cb
        return factory

    def _toggle(self, parent, text: str, var, command=None, tip: str | None = None):
        cb = ttk.Checkbutton(parent, text=text, variable=var, bootstyle="round-toggle",
                             command=command, takefocus=False)
        cb.pack(anchor="w", pady=3)
        if tip:
            ttk.ToolTip(cb, text=tip, wraplength=260)
        return cb

    def _build_sidebar(self, parent) -> ttk.Frame:
        side = ttk.Frame(parent, width=310)

        self._section(side, "Ritmo")
        bpm_row = ttk.Frame(side)
        bpm_row.pack(fill="x", pady=3)
        ttk.Label(bpm_row, text="Andamento", width=13).pack(side="left")
        self.bpm_label = ttk.Label(bpm_row, text="100 BPM", width=8, font=(FONT, 10, "bold"))
        self.bpm_label.pack(side="right")
        scale = ttk.Scale(bpm_row, from_=40, to=200, variable=self.bpm_var, command=self._on_bpm,
                          bootstyle="info", takefocus=False)
        scale.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self._labeled(side, "Compasso", self._combo(TIME_SIGNATURES, self.ts_var, self._on_structure))

        def measures_factory(parent):
            return ttk.Spinbox(parent, from_=1, to=8, textvariable=self.measures_var, width=6,
                               command=self._on_structure, state="readonly")
        self._labeled(side, "Compassos", measures_factory)
        ttk.Label(side, textvariable=self.duration_var, foreground=self.style.colors.light,
                  font=(FONT, 9)).pack(anchor="e")

        self._labeled(side, "Dificuldade", self._combo(LEVELS.values(), self.level_var, self._on_structure),
                      tip="Cada nível acrescenta figuras novas e dá mais destaque a elas.")
        ttk.Label(side, textvariable=self.level_hint_var, foreground=self.style.colors.light,
                  font=(FONT, 9)).pack(anchor="e")
        self._toggle(side, "Incluir pausas", self.rests_var, self._on_structure)

        self._section(side, "Som")
        self._labeled(side, "Escala", self._combo(SCALES, self.scale_var, self._on_structure))
        self._labeled(side, "Instrumento", self._combo(INSTRUMENTS, self.instrument_var, self._on_sound))
        vol_row = ttk.Frame(side)
        vol_row.pack(fill="x", pady=3)
        ttk.Label(vol_row, text="Volume", width=13).pack(side="left")
        ttk.Scale(vol_row, from_=0, to=100, variable=self.volume_var, bootstyle="info", takefocus=False,
                  command=lambda v: setattr(self.player, "volume", float(v) / 100)).pack(
            side="left", fill="x", expand=True)
        self.player.volume = self.volume_var.get() / 100

        self._devices = output_devices()
        self.device_var.set(self._devices[0][1])
        self._labeled(side, "Saída", self._combo([d[1] for d in self._devices], self.device_var, self._on_device),
                      tip="Dispositivo de áudio usado para tocar.")

        self._section(side, "Reprodução")
        self._toggle(side, "Contagem inicial (1 compasso)", self.countin_var, self._on_sound)
        self._toggle(side, "Metrônomo", self.metro_var, self._on_sound)
        self._toggle(side, "Repetir em loop", self.loop_var, self._on_sound)
        self._toggle(side, "Mostrar nomes das notas", self.names_var, self._on_names)

        lat = ttk.Frame(side)
        lat.pack(fill="x", pady=3)
        ttk.Label(lat, text="Latência (ms)", width=13).pack(side="left")
        spin = ttk.Spinbox(lat, from_=-200, to=400, increment=5, textvariable=self.latency_var, width=6)
        spin.pack(side="left", fill="x", expand=True)
        ttk.ToolTip(spin, text="Compensação do atraso do seu teclado/fone no modo treino. Use “Calibrar” "
                               "para medir automaticamente.", wraplength=260)
        ttk.Button(lat, text="Calibrar", bootstyle="info-outline", command=self.toggle_calibration,
                   takefocus=False).pack(side="left", padx=(6, 0))
        return side

    def _build_practice(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=12)
        colors = self.style.colors

        info = ttk.Frame(tab)
        info.pack(fill="x", pady=(0, 8))
        ttk.Label(info, textvariable=self.summary_var, font=(FONT, 11)).pack(side="left")
        seed_box = ttk.Frame(info)
        seed_box.pack(side="right")
        ttk.Label(seed_box, text="Semente", foreground=colors.light).pack(side="left", padx=(0, 6))
        seed_entry = ttk.Entry(seed_box, textvariable=self.seed_var, width=9)
        seed_entry.pack(side="left")
        seed_entry.bind("<Return>", lambda e: self._load_seed())
        ttk.ToolTip(seed_entry, text="Digite uma semente e tecle Enter para recriar exatamente o mesmo ritmo.")

        frame = tk.Frame(tab, bg=PAPER, bd=0, highlightthickness=1, highlightbackground=colors.border)
        frame.pack(fill="both", expand=True)
        self.score = ScoreView(frame, height=330, takefocus=True)
        self.score.pack(fill="both", expand=True, padx=6, pady=6)
        self.score.bind("<Button-1>", lambda e: self.score.focus_set())

        transport = ttk.Frame(tab)
        transport.pack(fill="x", pady=(10, 4))
        self.play_btn = ttk.Button(transport, text="▶  Tocar", bootstyle="success", width=12,
                                   command=self.toggle_play, takefocus=False)
        self.play_btn.pack(side="left")
        btn = ttk.Button(transport, text="◀", bootstyle="secondary", width=3, command=self.previous_pattern,
                         takefocus=False)
        btn.pack(side="left", padx=(8, 0))
        ttk.ToolTip(btn, text="Ritmo anterior")
        ttk.Button(transport, text="🎲  Novo ritmo", bootstyle="info", command=self.new_pattern,
                   takefocus=False).pack(side="left", padx=(4, 0))
        self.train_btn = ttk.Button(transport, text="🎯  Treinar", bootstyle="warning", command=self.toggle_train,
                                    takefocus=False)
        self.train_btn.pack(side="left", padx=(8, 0))
        ttk.Button(transport, text="🎹  MIDI…", bootstyle="light-outline", command=self.save_midi,
                   takefocus=False).pack(side="right")
        ttk.Button(transport, text="💾  Salvar áudio…", bootstyle="light-outline", command=self.save_audio,
                   takefocus=False).pack(side="right", padx=(0, 6))
        ttk.Label(tab, text="Atalhos:  Espaço tocar/parar · N novo · T treinar · Esc parar · Ctrl+S salvar",
                  font=(FONT, 8), foreground=colors.light).pack(anchor="w")

        # painel do treino
        trainer = ttk.Labelframe(tab, text=" Modo treino — imitação ", padding=10)
        trainer.pack(fill="x", pady=(8, 0))
        self.pad = tk.Label(trainer, text="TOQUE\nAQUI", width=10, height=3, bg=colors.dark, fg="#bbb",
                            font=(FONT, 12, "bold"), cursor="hand2", relief="flat")
        self.pad.pack(side="left", padx=(0, 14))
        self.pad.bind("<ButtonPress-1>", lambda e: self.tap())
        texts = ttk.Frame(trainer)
        texts.pack(side="left", fill="both", expand=True)
        self.phase_label = ttk.Label(texts, textvariable=self.phase_var, font=(FONT, 15, "bold"))
        self.phase_label.pack(anchor="w")
        ttk.Label(texts, textvariable=self.result_var, font=(FONT, 10), wraplength=560,
                  justify="left").pack(anchor="w", pady=(2, 0))
        right = ttk.Frame(trainer)
        right.pack(side="right", fill="y")
        ear = ttk.Checkbutton(right, text="Treino de ouvido", variable=self.ear_var, bootstyle="round-toggle",
                              takefocus=False)
        ear.pack(anchor="e")
        ttk.ToolTip(ear, text="Esconde as notas durante o treino: você imita só de ouvido e a partitura "
                              "aparece no final, com o resultado.", wraplength=260)
        ttk.Label(right, textvariable=self.best_var, font=(FONT, 10), foreground=colors.light,
                  justify="right").pack(anchor="e", pady=(8, 0))
        return tab

    def _build_batch(self, parent) -> ttk.Frame:
        tab = ttk.Frame(parent, padding=16)
        colors = self.style.colors
        ttk.Label(tab, text="Gere vários arquivos de uma vez usando as configurações da barra lateral. "
                            "Cada arquivo recebe um ritmo e uma melodia novos.",
                  wraplength=700, foreground=colors.light).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Pasta de destino", width=18).pack(side="left")
        ttk.Entry(row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Procurar…", bootstyle="info", command=self._choose_folder,
                   takefocus=False).pack(side="left", padx=(6, 0))

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Quantidade", width=18).pack(side="left")
        ttk.Spinbox(row, from_=1, to=500, textvariable=self.qty_var, width=7).pack(side="left")

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Formatos", width=18).pack(side="left")
        for text, var in (("WAV", self.fmt_wav_var), ("MP3", self.fmt_mp3_var), ("MIDI", self.fmt_mid_var)):
            cb = ttk.Checkbutton(row, text=text, variable=var, takefocus=False)
            cb.pack(side="left", padx=(0, 14))
            if text == "MP3" and not self._ffmpeg:
                cb.configure(state="disabled")
                ttk.ToolTip(cb, text="Instale o ffmpeg (e coloque-o no PATH) para exportar MP3.")

        opts = ttk.Labelframe(tab, text=" Opções de áudio (valem também para “Salvar áudio…”) ", padding=10)
        opts.pack(fill="x", pady=(12, 4))
        self._toggle(opts, "Incluir metrônomo no arquivo", self.exp_metro_var)
        self._toggle(opts, "Incluir contagem inicial no arquivo", self.exp_countin_var)
        fixed = ttk.Frame(opts)
        fixed.pack(anchor="w", pady=3)
        ttk.Checkbutton(fixed, text="Forçar duração exata de", variable=self.exp_fixed_var,
                        bootstyle="round-toggle", takefocus=False).pack(side="left")
        ttk.Spinbox(fixed, from_=1, to=120, increment=0.5, textvariable=self.exp_seconds_var,
                    width=6).pack(side="left", padx=6)
        ttk.Label(fixed, text="segundos (completa com silêncio ou corta)").pack(side="left")

        extra = ttk.Frame(tab)
        extra.pack(fill="x", pady=(8, 4))
        self._toggle(extra, "Gerar gabarito (CSV com figuras, notas e sementes)", self.csv_var)
        self._toggle(extra, "Abrir a pasta ao terminar", self.open_folder_var)

        run = ttk.Frame(tab)
        run.pack(fill="x", pady=(14, 4))
        self.batch_btn = ttk.Button(run, text="⚙  Gerar arquivos", bootstyle="success", width=20,
                                    command=self.run_batch, takefocus=False)
        self.batch_btn.pack(side="left")
        self.batch_progress = ttk.Progressbar(run, bootstyle="success-striped", maximum=100)
        self.batch_progress.pack(side="left", fill="x", expand=True, padx=12)

        self.batch_log = tk.Listbox(tab, height=8, bg=colors.inputbg, fg=colors.fg, bd=0,
                                    highlightthickness=0, font=("Consolas", 9), activestyle="none")
        self.batch_log.pack(fill="both", expand=True, pady=(8, 0))
        return tab

    def _bind_keys(self) -> None:
        r = self.root
        r.bind_all("<KeyPress-space>", self._on_space)
        r.bind_all("<KeyRelease-space>", lambda e: setattr(self, "_space_down", False))
        r.bind_all("<KeyPress-Return>", self._on_enter)
        for key, action in (("n", self.new_pattern), ("t", self.toggle_train)):
            r.bind_all(f"<KeyPress-{key}>", lambda e, a=action: self._shortcut(e, a))
            r.bind_all(f"<KeyPress-{key.upper()}>", lambda e, a=action: self._shortcut(e, a))
        r.bind_all("<Escape>", lambda e: self.stop())
        r.bind_all("<Control-s>", lambda e: self.save_audio())
        r.bind_all("<Control-m>", lambda e: self.save_midi())

    # ----------------------------------------------------------- utilidades

    def _typing(self, event) -> bool:
        try:
            return event.widget.winfo_class() in TEXT_INPUT_CLASSES
        except (AttributeError, tk.TclError):
            return False

    def _shortcut(self, event, action):
        if not self._typing(event) and self.notebook.index("current") == 0:
            action()

    @property
    def beat_s(self) -> float:
        return 60.0 / max(1, self.bpm_var.get())

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _update_duration(self) -> None:
        beats = TIME_SIGNATURES[self.ts_var.get()] * self.measures_var.get()
        secs = beats * self.beat_s
        self.duration_var.set(f"{beats} tempos · {secs:.2f} s".replace(".", ","))

    # ---------------------------------------------------------- callbacks

    def _on_bpm(self, value) -> None:
        bpm = int(round(float(value)))
        if bpm != self.bpm_var.get():
            self.bpm_var.set(bpm)
        self.bpm_label.configure(text=f"{bpm} BPM")
        self._update_duration()
        self._on_sound()

    def _on_structure(self) -> None:
        self.new_pattern(seed=self._current_seed())

    def _on_sound(self) -> None:
        # o áudio pronto (e a pontuação do treino) dependem destes ajustes
        if self.mode in ("play", "train"):
            self.stop()

    def _on_names(self) -> None:
        self.score.show_names = self.names_var.get()
        self.score.redraw()

    def _on_device(self) -> None:
        name = self.device_var.get()
        self.player.device = next((i for i, n in self._devices if n == name), None)
        self.stop()
        self._set_status(f"Saída de áudio: {name}")

    def _on_space(self, event):
        if self._typing(event) or self.notebook.index("current") != 0:
            return None
        if self._space_down:          # ignora a repetição automática da tecla
            return "break"
        self._space_down = True
        if self.mode in ("train", "calib"):
            self.tap()
        else:
            self.toggle_play()
        return "break"

    def _on_enter(self, event):
        if self.mode in ("train", "calib") and not self._typing(event):
            self.tap()
            return "break"
        return None

    # ------------------------------------------------------------ padrões

    def _current_seed(self) -> int | None:
        return self.pattern.seed if self.pattern else None

    def _level(self) -> int:
        return next(k for k, v in LEVELS.items() if v == self.level_var.get())

    def _generate(self, seed: int | None) -> Pattern:
        return generate(level=self._level(), beats_per_measure=TIME_SIGNATURES[self.ts_var.get()],
                        measures=int(self.measures_var.get()), scale=self.scale_var.get(),
                        rests=self.rests_var.get(), seed=seed)

    def new_pattern(self, seed: int | None = None) -> None:
        self.stop()
        if self.pattern is not None and seed is None:
            self.history.append(self.pattern.seed)
            self.history = self.history[-50:]
        self.pattern = self._generate(seed)
        self.seed_var.set(str(self.pattern.seed))
        p = self.pattern
        self.level_hint_var.set(LEVEL_HINTS[p.level])
        self.summary_var.set(f"{len(p.sounding())} notas  ·  {p.measures} × {p.time_signature}  ·  "
                             f"{LEVELS[p.level].split(' · ')[1]}  ·  {p.scale}")
        self.score.show_names = self.names_var.get()
        self.score.set_pattern(self.pattern)
        self._update_duration()
        n = len(self.pattern.sounding())
        self._set_status(f"Novo ritmo: {n} notas, {self.pattern.measures} compasso(s) de "
                         f"{self.pattern.time_signature}, semente {self.pattern.seed}.")
        self._reset_trainer()

    def previous_pattern(self) -> None:
        if not self.history:
            self._set_status("Não há ritmo anterior.")
            return
        seed = self.history.pop()
        self.pattern = None
        self.new_pattern(seed=seed)

    def _load_seed(self) -> None:
        try:
            seed = int(self.seed_var.get().strip())
        except ValueError:
            messagebox.showwarning(APP_NAME, "A semente deve ser um número inteiro.", parent=self.root)
            return
        if self.pattern is not None:
            self.history.append(self.pattern.seed)
        self.new_pattern(seed=seed)
        self.score.focus_set()

    def _reset_trainer(self) -> None:
        self.phase_var.set("Modo treino")
        self.phase_label.configure(foreground=self.style.colors.fg)
        self.result_var.set("Pressione  T  (ou o botão “Treinar”) para ouvir o ritmo e depois imitá-lo "
                            "com a barra de ESPAÇO, Enter ou clicando em “Toque aqui”.")
        self.scores = []
        self.best_var.set("")

    # --------------------------------------------------------- reprodução

    def _render(self, training: bool = False) -> Rendered:
        key = (self.pattern.seed, self.pattern.level, self.pattern.beats_per_measure, self.pattern.measures,
               self.pattern.scale, self.rests_var.get(), self.bpm_var.get(), self.instrument_var.get(),
               training or self.metro_var.get(), training or self.countin_var.get(), training)
        if key not in self._render_cache:
            if len(self._render_cache) > 8:
                self._render_cache.clear()
            if training:
                self._render_cache[key] = render_training(self.pattern, self.bpm_var.get(),
                                                          self.instrument_var.get())
            else:
                self._render_cache[key] = render(self.pattern, self.bpm_var.get(), self.instrument_var.get(),
                                                 metronome=self.metro_var.get(),
                                                 count_in=self.countin_var.get())
        return self._render_cache[key]

    def toggle_play(self) -> None:
        if self.mode != "idle":
            self.stop()
            return
        if self.pattern is None:
            return
        self.rendered = self._render()
        self.score.set_results(None, [])
        self.score.playhead_color = "#1f6fd1"
        self.mode = "play"
        self.player.play(self.rendered.samples, loop=self.loop_var.get())
        self._after_start()
        self.play_btn.configure(text="■  Parar", bootstyle="danger")
        self._set_status("Tocando…" + ("  (loop)" if self.loop_var.get() else ""))
        self._tick()

    def _after_start(self) -> None:
        if self.player.last_error and self.player.backend == "winsound":
            self._set_status(f"Áudio em modo compatível (winsound): {self.player.last_error}")
        elif not self.player.playing:
            messagebox.showerror(APP_NAME, "Não foi possível tocar o áudio.\n\n"
                                 f"{self.player.last_error or 'Dispositivo indisponível.'}", parent=self.root)

    def stop(self) -> None:
        was_training = self.mode == "train"
        was_calib = self.mode == "calib"
        if self._tick_id:
            self.root.after_cancel(self._tick_id)
            self._tick_id = None
        self.player.stop()
        self.mode = "idle"
        if hasattr(self, "score"):
            self.score.set_hidden(False)
            self.score.set_playhead(None)
        if hasattr(self, "play_btn"):
            self.play_btn.configure(text="▶  Tocar", bootstyle="success")
            self.train_btn.configure(text="🎯  Treinar", bootstyle="warning")
        if was_training or was_calib:
            self.phase_var.set("Calibração interrompida" if was_calib else "Treino interrompido")
            self.phase_label.configure(foreground=self.style.colors.fg)
            self._set_status(self.phase_var.get() + ".")

    def _tick(self) -> None:
        self._tick_id = None
        if self.mode == "idle":
            return
        if not self.player.playing:
            if self.mode == "train":
                self._finish_training()
            elif self.mode == "calib":
                self._finish_calibration()
            else:
                self.stop()
                self._set_status("Pronto.")
            return
        pos = self.player.position()
        if pos is not None and self.mode == "calib":
            beat = int(pos * CALIB_BPM / 60)
            if beat < CALIB_LEAD:
                self._phase(f"Calibração — escute…  {beat + 1}", self.style.colors.info)
            else:
                self._phase(f"Toque junto com cada clique!  {beat - CALIB_LEAD + 1}/{CALIB_BEATS - CALIB_LEAD}",
                            self.style.colors.success)
        elif pos is not None and self.rendered is not None:
            if self.mode == "play":
                beat = (pos - self.rendered.pattern_start) / self.beat_s
                self.score.set_playhead(beat)
                if beat < 0:
                    self._set_status(f"Contagem… {int(pos / self.beat_s) + 1}")
                elif self.status_var.get().startswith("Contagem"):
                    self._set_status("Tocando…")
            else:
                self._train_tick(pos)
        self._tick_id = self.root.after(15, self._tick)

    # -------------------------------------------------------------- treino

    def toggle_train(self) -> None:
        if self.mode == "train":
            self.stop()
            return
        self.stop()
        if self.pattern is None:
            return
        self.rendered = self._render(training=True)
        self.taps = []
        self.score.set_results(None, [])
        self.score.set_hidden(self.ear_var.get())
        self.mode = "train"
        self.player.play(self.rendered.samples, loop=False)
        self._after_start()
        self.train_btn.configure(text="■  Parar treino", bootstyle="danger")
        self.result_var.set("Escute o ritmo. Depois da segunda contagem, toque junto com o metrônomo.")
        self._set_status("Treino: ouça com atenção…")
        self._tick()

    def _train_tick(self, pos: float) -> None:
        r, beat_s = self.rendered, self.beat_s
        body = self.pattern.total_beats * beat_s
        colors = self.style.colors
        if pos < r.pattern_start:
            self._phase(f"Ouça…  {int(pos / beat_s) + 1}", colors.info)
            self.score.set_playhead(None)
        elif pos < r.pattern_start + body:
            self._phase("Ouça o ritmo 🎧", colors.info)
            self.score.playhead_color = "#1f6fd1"
            self.score.set_playhead((pos - r.pattern_start) / beat_s)
        elif pos < r.tap_start:
            count = int((pos - r.pattern_start - body) / beat_s) + 1
            self._phase(f"Sua vez em…  {count}", colors.warning)
            self.score.set_playhead(None)
        else:
            self._phase("Sua vez! Toque o ritmo  ⌨", colors.success)
            self.score.playhead_color = "#9a9486"
            self.score.set_playhead((pos - r.tap_start) / beat_s)

    def _phase(self, text: str, color: str) -> None:
        if self.phase_var.get() != text:
            self.phase_var.set(text)
            self.phase_label.configure(foreground=color)

    def tap(self) -> None:
        if self.mode == "calib":
            pos = self.player.position()
            if pos is not None:
                self.taps.append(pos)
                self._flash_pad()
            return
        if self.mode != "train" or self.rendered is None:
            return
        pos = self.player.position()
        if pos is None:
            return
        t = pos - self._latency_s() - self.rendered.tap_start
        if t < -0.5 * self.beat_s:
            return  # cedo demais: ainda é a parte de ouvir
        self.taps.append(t)
        self.score.add_tap(t / self.beat_s, TAP_PENDING)
        self._flash_pad()

    def _latency_s(self) -> float:
        try:
            return int(self.latency_var.get()) / 1000.0
        except (tk.TclError, ValueError):
            return 0.0

    def _fixed_seconds(self) -> float | None:
        if not self.exp_fixed_var.get():
            return None
        try:
            secs = float(self.exp_seconds_var.get())
        except (tk.TclError, ValueError):
            raise ValueError("A duração exata deve ser um número de segundos.") from None
        if not 0.5 <= secs <= 600:
            raise ValueError("A duração exata deve ficar entre 0,5 e 600 segundos.")
        return secs

    def _flash_pad(self) -> None:
        self.pad.configure(bg=self.style.colors.success, fg="white")
        self.root.after(90, lambda: self.pad.configure(bg=self.style.colors.dark, fg="#bbb"))

    def _finish_training(self) -> None:
        self.mode = "idle"
        self.score.hidden = False
        self.score.set_playhead(None)
        self.train_btn.configure(text="🎯  Treinar", bootstyle="warning")
        beat_s = self.beat_s
        expected = [float(o) * beat_s for o in self.pattern.onsets()]
        res = score_taps(expected, self.taps)
        taps = [((n.expected + n.error) / beat_s, STATUS_COLORS[n.status]) for n in res.notes
                if n.error is not None]
        taps += [(t / beat_s, STATUS_COLORS["perdeu"]) for t in res.extras]
        self.score.set_results([n.status for n in res.notes], taps)

        color = (self.style.colors.success if res.percent >= 75 else
                 self.style.colors.warning if res.percent >= 50 else self.style.colors.danger)
        self._phase(f"{res.percent:.0f}%  —  {res.grade}", color)
        lines = res.summary().split("\n")[1:]
        off = res.mean_offset_ms
        if off is not None and abs(off) >= 40:
            lines[-1] += "  — se acontecer sempre, use “Calibrar” na barra lateral."
        if not self.taps:
            lines = ["Nenhuma batida registrada. Use ESPAÇO, Enter ou clique em “Toque aqui”."]
        self.result_var.set("\n".join(lines) + "\nPressione T para tentar de novo ou N para um ritmo novo.")
        self.scores.append(res.percent)
        hist = " → ".join(f"{s:.0f}" for s in self.scores[-5:])
        self.best_var.set(f"Melhor: {max(self.scores):.0f}%\nTentativas: {len(self.scores)}\nHistórico: {hist}")
        self._set_status(f"Treino concluído: {res.percent:.0f}%.")

    # ---------------------------------------------------------- calibração

    def toggle_calibration(self) -> None:
        if self.mode == "calib":
            self.stop()
            return
        self.stop()
        self.notebook.select(0)
        self.taps = []
        self.rendered = None
        self.mode = "calib"
        self.player.play(render_clicks(CALIB_BEATS, CALIB_BPM), loop=False)
        self._after_start()
        self.result_var.set(f"Escute {CALIB_LEAD} cliques e então toque ESPAÇO exatamente junto com cada "
                            "um dos próximos. O app mede o atraso do seu sistema.")
        self._set_status("Calibrando latência…")
        self._tick()

    def _finish_calibration(self) -> None:
        self.mode = "idle"
        beat = 60.0 / CALIB_BPM
        clicks = [k * beat for k in range(CALIB_LEAD, CALIB_BEATS)]
        diffs = []
        for t in self.taps:
            nearest = min(clicks, key=lambda c: abs(c - t))
            if abs(t - nearest) < beat / 2:
                diffs.append(t - nearest)
        if len(diffs) < 6:
            self._phase("Calibração incompleta", self.style.colors.warning)
            self.result_var.set("Poucas batidas registradas. Clique em “Calibrar” e toque junto com os cliques.")
            self._set_status("Calibração incompleta.")
            return
        ms = 1000 * statistics.median(diffs)
        spread = 1000 * statistics.pstdev(diffs)
        value = int(round(ms / 5) * 5)
        self.latency_var.set(value)
        self._phase(f"Latência calibrada: {value:+d} ms", self.style.colors.success)
        if spread < 25:
            quality = "ótima consistência"
        elif spread < 45:
            quality = "boa consistência"
        else:
            quality = "batidas irregulares — talvez valha repetir"
        self.result_var.set(f"{len(diffs)} batidas medidas, variação de ±{spread:.0f} ms ({quality}).\n"
                            "O valor foi aplicado ao modo treino. Pressione T para treinar.")
        self._set_status(f"Latência calibrada em {value:+d} ms.")

    # ----------------------------------------------------------- exportação

    def _export_samples(self, pattern: Pattern):
        r = render(pattern, self.bpm_var.get(), self.instrument_var.get(),
                   metronome=self.exp_metro_var.get(), count_in=self.exp_countin_var.get())
        samples = r.samples
        fixed = self._fixed_seconds()
        if fixed:
            samples = fit_duration(samples, fixed)
        return samples

    def save_audio(self) -> None:
        if self.pattern is None:
            return
        types = [("Áudio WAV", "*.wav")] + ([("Áudio MP3", "*.mp3")] if self._ffmpeg else [])
        path = filedialog.asksaveasfilename(parent=self.root, title="Salvar áudio", defaultextension=".wav",
                                            filetypes=types, initialfile=f"ritmo_{self.pattern.seed}.wav")
        if not path:
            return
        try:
            samples = self._export_samples(self.pattern)
            if path.lower().endswith(".mp3"):
                write_mp3(path, samples)
            else:
                write_wav(path, samples)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível salvar:\n{exc}", parent=self.root)
            return
        self._set_status(f"Áudio salvo em {path}")

    def save_midi(self) -> None:
        if self.pattern is None:
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Salvar MIDI", defaultextension=".mid",
                                            filetypes=[("MIDI", "*.mid")],
                                            initialfile=f"ritmo_{self.pattern.seed}.mid")
        if not path:
            return
        try:
            write_midi(path, self.pattern, self.bpm_var.get(), self.instrument_var.get())
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível salvar:\n{exc}", parent=self.root)
            return
        self._set_status(f"MIDI salvo em {path}")

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, initialdir=self.folder_var.get() or None)
        if folder:
            self.folder_var.set(folder)

    def run_batch(self) -> None:
        if self._batch_running:
            return
        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showwarning(APP_NAME, "Escolha uma pasta para salvar os arquivos.", parent=self.root)
            return
        try:
            qty = int(self.qty_var.get())
            if not 1 <= qty <= 500:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showwarning(APP_NAME, "A quantidade deve ser um número entre 1 e 500.", parent=self.root)
            return
        exts = [ext for ext, var in ((".wav", self.fmt_wav_var), (".mp3", self.fmt_mp3_var),
                                     (".mid", self.fmt_mid_var)) if var.get()]
        if ".mp3" in exts and not self._ffmpeg:
            exts.remove(".mp3")
        if not exts:
            messagebox.showwarning(APP_NAME, "Selecione pelo menos um formato.", parent=self.root)
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível criar a pasta:\n{exc}", parent=self.root)
            return

        params = dict(
            level=self._level(), beats_per_measure=TIME_SIGNATURES[self.ts_var.get()],
            measures=int(self.measures_var.get()), scale=self.scale_var.get(), rests=self.rests_var.get(),
        )
        bpm, instrument = self.bpm_var.get(), self.instrument_var.get()
        metro, countin = self.exp_metro_var.get(), self.exp_countin_var.get()
        try:
            fixed = self._fixed_seconds()
        except ValueError as exc:
            messagebox.showwarning(APP_NAME, str(exc), parent=self.root)
            return
        want_csv = self.csv_var.get()

        self._batch_running = True
        self.batch_btn.configure(state="disabled")
        self.batch_progress.configure(value=0)
        self.batch_log.delete(0, "end")
        threading.Thread(target=self._batch_worker, daemon=True,
                         args=(folder, qty, exts, params, bpm, instrument, metro, countin, fixed, want_csv)).start()
        self.root.after(50, self._poll_batch)

    def _batch_worker(self, folder, qty, exts, params, bpm, instrument, metro, countin, fixed, want_csv) -> None:
        rows = []
        try:
            for i in range(qty):
                pattern = generate(seed=random.randrange(1_000_000), **params)
                stem = os.path.join(folder, f"padrao_melodico_{i + 1:03d}")
                counter = 1
                while any(os.path.exists(stem + ext) for ext in exts):
                    stem = os.path.join(folder, f"padrao_melodico_{i + 1:03d}_{counter}")
                    counter += 1
                samples = None
                if ".wav" in exts or ".mp3" in exts:
                    samples = render(pattern, bpm, instrument, metronome=metro, count_in=countin).samples
                    if fixed:
                        samples = fit_duration(samples, fixed)
                for ext in exts:
                    if ext == ".wav":
                        write_wav(stem + ext, samples)
                    elif ext == ".mp3":
                        write_mp3(stem + ext, samples)
                    else:
                        write_midi(stem + ext, pattern, bpm, instrument)
                name = os.path.basename(stem)
                secs = len(samples) / SR if samples is not None else pattern.duration_seconds(bpm)
                rows.append([name, bpm, pattern.time_signature, pattern.measures, LEVELS[pattern.level],
                             pattern.scale, instrument, pattern.seed, f"{secs:.3f}".replace(".", ","),
                             pattern.rhythm_text(), pattern.melody_text()])
                self._batch_queue.put(("progress", i + 1, qty, f"{name}{'/'.join(exts)}  ·  {pattern.rhythm_text()}"))
            csv_path = None
            if want_csv:
                csv_path = os.path.join(folder, time.strftime("gabarito_%Y%m%d_%H%M%S.csv"))
                with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
                    w = csv.writer(fh, delimiter=";")
                    w.writerow(["arquivo", "bpm", "compasso", "compassos", "nivel", "escala", "instrumento",
                                "semente", "duracao_s", "figuras", "notas"])
                    w.writerows(rows)
            self._batch_queue.put(("done", folder, qty, csv_path))
        except Exception as exc:
            self._batch_queue.put(("error", str(exc)))

    def _poll_batch(self) -> None:
        try:
            while True:
                msg = self._batch_queue.get_nowait()
                if msg[0] == "progress":
                    _, done, total, line = msg
                    self.batch_progress.configure(value=100 * done / total)
                    self.batch_log.insert("end", line)
                    self.batch_log.see("end")
                    self._set_status(f"Gerando… {done}/{total}")
                elif msg[0] == "done":
                    _, folder, qty, csv_path = msg
                    self._batch_done()
                    if csv_path:
                        self.batch_log.insert("end", f"Gabarito: {os.path.basename(csv_path)}")
                    self.batch_log.see("end")
                    self._set_status(f"{qty} arquivo(s) gerado(s) em {folder}")
                    if self.open_folder_var.get() and hasattr(os, "startfile"):
                        os.startfile(folder)
                    return
                elif msg[0] == "error":
                    self._batch_done()
                    messagebox.showerror(APP_NAME, f"Erro ao gerar os arquivos:\n{msg[1]}", parent=self.root)
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll_batch)

    def _batch_done(self) -> None:
        self._batch_running = False
        self.batch_btn.configure(state="normal")

    # ---------------------------------------------------------------- fim

    def _on_close(self) -> None:
        self.stop()
        self.player.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    App().run()
