import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pydub.generators import Sine
from pydub import AudioSegment
from PIL import Image, ImageTk
import os
import random

BPM = 100
BEAT_DURATION_MS = int(60000 / BPM)  # 600 ms por batida
TOTAL_AUDIO_DURATION_MS = 6000       # 6 segundos

def get_symbol_duration_ms(symbol):
    if symbol == "♩":
        return BEAT_DURATION_MS         # 600 ms
    elif symbol == "♪":
        return BEAT_DURATION_MS // 2   # 300 ms
    elif symbol == "𝅗𝅥":
        return BEAT_DURATION_MS * 2    # 1200 ms
    return BEAT_DURATION_MS

def create_melodic_pattern_audio(pattern, melody):
    audio = AudioSegment.silent(duration=0)
    for i, symbol in enumerate(pattern):
        tone = melody[i % len(melody)]
        duration = get_symbol_duration_ms(symbol)
        tone = tone[:min(len(tone), duration - 10)]
        silence = AudioSegment.silent(duration=duration - len(tone))
        audio += tone + silence

    # Garante que tenha exatamente 6000ms no final
    if len(audio) < TOTAL_AUDIO_DURATION_MS:
        audio += AudioSegment.silent(duration=TOTAL_AUDIO_DURATION_MS - len(audio))
    elif len(audio) > TOTAL_AUDIO_DURATION_MS:
        audio = audio[:TOTAL_AUDIO_DURATION_MS]
    return audio

def gerar_audios():
    pasta = pasta_var.get()
    if not pasta:
        messagebox.showwarning("Aviso", "Escolha uma pasta para salvar os áudios.")
        return

    try:
        num_musicas = int(num_musicas_var.get())
        if num_musicas < 1 or num_musicas > 10:
            raise ValueError("Escolha um número entre 1 e 10.")
    except ValueError as e:
        messagebox.showwarning("Aviso", f"Erro: {e}")
        return

    def generate_random_melody():
        notas = [
            Sine(261.63).to_audio_segment(duration=100).apply_gain(-3),  # C4
            Sine(329.63).to_audio_segment(duration=100).apply_gain(-3),  # E4
            Sine(392.00).to_audio_segment(duration=100).apply_gain(-3),  # G4
            Sine(523.25).to_audio_segment(duration=100).apply_gain(-3),  # C5
            Sine(440.00).to_audio_segment(duration=100).apply_gain(-3),  # A4
        ]
        return [random.choice(notas) for _ in range(16)]

    # Padrões rítmicos com duração total de 10 batidas (6000 ms)
    patterns = [
        ["♩"] * 10,
        ["♪"] * 20,
        ["♩", "♪", "♩", "♪", "♩", "♪", "♩", "♪", "♩", "♪"],  # 5 semínimas + 5 colcheias = 7.5 beats → ajusta com 𝅗𝅥
        ["𝅗𝅥", "𝅗𝅥", "♩", "♩", "♪", "♪"],  # 2x2 + 2x1 + 2x0.5 = 7 beats → ajusta
        ["♩", "♩", "♩", "♩", "♩", "♩", "♪", "♪", "♪", "♪"],  # 6x1 + 4x0.5 = 8 beats
        ["𝅗𝅥", "♩", "♩", "𝅗𝅥", "♪", "♪"],  # 2+1+1+2+0.5+0.5 = 7 beats
    ]

    # Completa os padrões para que totalizem 10 batidas
    def completar_pattern(pattern):
        total_beats = sum({
            "♩": 1, "♪": 0.5, "𝅗𝅥": 2
        }[s] for s in pattern)
        while total_beats < 10:
            pattern.append("♪")
            total_beats += 0.5
        return pattern

    for i in range(num_musicas):
        pattern_base = patterns[i % len(patterns)]
        pattern = completar_pattern(pattern_base.copy())
        melody = generate_random_melody()
        audio = create_melodic_pattern_audio(pattern, melody)

        filename = os.path.join(pasta, f"padrao_melodico_{i+1}.wav")
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(pasta, f"padrao_melodico_{i+1}_{counter}.wav")
            counter += 1

        audio.export(filename, format="wav")

    messagebox.showinfo("Sucesso", f"{num_musicas} áudios salvos em:\n{pasta}")

# ---- INTERFACE GRÁFICA ----

app = ttk.Window(title="Gerador de Ritmos Melódicos (CaioRenatoDot)", themename="darkly", size=(800, 600))

imagem_caminho = "logo.png"
if os.path.exists(imagem_caminho):
    imagem = Image.open(imagem_caminho)
    imagem = imagem.resize((120, 120))
    imagem_tk = ImageTk.PhotoImage(imagem)
    ttk.Label(app, image=imagem_tk).pack(pady=(20, 10))

pasta_var = ttk.StringVar()
num_musicas_var = ttk.StringVar()

def escolher_pasta():
    pasta = filedialog.askdirectory()
    pasta_var.set(pasta)

ttk.Label(app, text="Gerador de Padrões Rítmicos Melódicos", font=("Segoe UI", 18, "bold")).pack(pady=10)
ttk.Label(app, text="Selecione a pasta de destino:", font=("Segoe UI", 12)).pack(pady=5)

frame = ttk.Frame(app)
frame.pack(pady=10)

ttk.Entry(frame, textvariable=pasta_var, width=40, font=("Segoe UI", 12)).pack(side=ttk.LEFT, padx=10, pady=5)
ttk.Button(frame, text="Procurar", command=escolher_pasta, bootstyle="info").pack(side=ttk.LEFT)

ttk.Label(app, text="Quantas músicas você deseja gerar?", font=("Segoe UI", 12)).pack(pady=5)
ttk.Entry(app, textvariable=num_musicas_var, width=5, font=("Segoe UI", 12)).pack(pady=5)

ttk.Button(app, text="Gerar Áudios", command=gerar_audios, bootstyle="success", width=20).pack(pady=20)

ttk.Label(app, text="Feito por CaioRenatoDot", font=("Segoe UI", 8), foreground="#888").pack(side="bottom", pady=5)

app.mainloop()
