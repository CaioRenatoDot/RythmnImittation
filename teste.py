import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox
from pydub.generators import Sine
from pydub import AudioSegment
from PIL import Image, ImageTk
import os
import random

def create_melodic_pattern_audio(pattern, melody, beat_duration=500):
    half_beat = beat_duration // 2
    double_beat = beat_duration * 2
    rest = AudioSegment.silent(duration=beat_duration)
    half_rest = AudioSegment.silent(duration=half_beat)
    double_rest = AudioSegment.silent(duration=double_beat)

    def melodic_beat(tone): return tone + rest[:-(len(tone))]
    def melodic_half_beat(tone): return tone + half_rest[:-(len(tone))]
    def melodic_double_beat(tone): return tone + double_rest[:-(len(tone))]

    audio = AudioSegment.silent(duration=0)
    for i, note in enumerate(pattern):
        tone = melody[i % len(melody)]
        if note == "♩":
            audio += melodic_beat(tone)
        elif note == "♪":
            audio += melodic_half_beat(tone)
        elif note == "𝅗𝅥":
            audio += melodic_double_beat(tone)
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

    bpm = 120
    beat_duration = int(60000 / bpm)

    def generate_random_melody():
        notes = [Sine(261.63).to_audio_segment(duration=100).apply_gain(-3),  # C4
                 Sine(329.63).to_audio_segment(duration=100).apply_gain(-3),  # E4
                 Sine(392.00).to_audio_segment(duration=100).apply_gain(-3),  # G4
                 Sine(523.25).to_audio_segment(duration=100).apply_gain(-3),  # C5
                 Sine(440.00).to_audio_segment(duration=100).apply_gain(-3)]  # A4
        melody = [random.choice(notes) for _ in range(8)]
        return melody

    patterns = [
        ["♩", "♩", "♪", "♪", "♩", "♩", "♪", "♪"] * 3,
        ["♪", "♪", "♩", "♩", "♪", "♪", "♩", "♩"] * 3,
        ["♩", "♪", "♩", "♪", "♩", "♪", "♩", "♪"] * 3,
        ["♩", "♩", "♩", "♩", "♪", "♪", "♪", "♪"] * 3,
        ["♪", "♩", "♩", "♪", "♩", "♪", "♪", "♩"] * 3,
    ]

    for i in range(num_musicas):
        pattern = patterns[i % len(patterns)]
        melody = generate_random_melody()
        audio = create_melodic_pattern_audio(pattern, melody, beat_duration)

        filename = os.path.join(pasta, f"padrao_melodico_{i+1}.wav")
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(pasta, f"padrao_melodico_{i+1}_{counter}.wav")
            counter += 1
        
        audio.export(filename, format="wav")

    messagebox.showinfo("Sucesso", f"{num_musicas} áudios salvos em:\n{pasta}")

# ---- INTERFACE GRÁFICA ----

app = ttk.Window(title="Gerador de Ritmos Melódicos (CaioRenatoDot)", themename="darkly", size=(800, 600))
# Opções de tema: flatly, darkly, cyborg, superhero, vapor, solar, morph

# Carregar imagem
imagem_caminho = "logo.png"
if os.path.exists(imagem_caminho):
    imagem = Image.open(imagem_caminho)
    imagem = imagem.resize((120, 120))
    imagem_tk = ImageTk.PhotoImage(imagem)
    ttk.Label(app, image=imagem_tk).pack(pady=(20, 10))

# Variáveis
pasta_var = ttk.StringVar()
num_musicas_var = ttk.StringVar()

def escolher_pasta():
    pasta = filedialog.askdirectory()
    pasta_var.set(pasta)

# Título
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
