import tkinter as tk
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

    # Função para gerar uma melodia aleatória com notas diferentes e variações
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
        melody = generate_random_melody()  # Gerar uma nova melodia aleatória para cada música
        audio = create_melodic_pattern_audio(pattern, melody, beat_duration)

        # Verifica se o arquivo já existe e cria um nome único
        filename = os.path.join(pasta, f"padrao_melodico_{i+1}.wav")
        counter = 1
        while os.path.exists(filename):
            filename = os.path.join(pasta, f"padrao_melodico_{i+1}_{counter}.wav")
            counter += 1
        
        audio.export(filename, format="wav")

    messagebox.showinfo("Sucesso", f"{num_musicas} áudios salvos em:\n{pasta}")

app = tk.Tk()

app.title("Gerador de Padrões Rítmicos Melódicos (CaioRenatoDot)")
app.geometry("800x600")
app.config(bg="#F0F0F0")

imagem_caminho = "logo.png"
imagem = Image.open(imagem_caminho)
imagem = imagem.resize((120, 120))
imagem_tk = ImageTk.PhotoImage(imagem)

imagem_label = tk.Label(app, image=imagem_tk, bg="#F0F0F0")
imagem_label.image = imagem_tk
imagem_label.pack(pady=(20, 10))

pasta_var = tk.StringVar()
num_musicas_var = tk.StringVar()

def escolher_pasta():
    pasta = filedialog.askdirectory()
    pasta_var.set(pasta)

title_label = tk.Label(app, text="Gerador de Padrões Rítmicos Melódicos", font=("Helvetica", 16, "bold"), bg="#F0F0F0", fg="#333")
title_label.pack(pady=10)

tk.Label(app, text="Selecione a pasta de destino:", font=("Arial", 12), bg="#F0F0F0").pack(pady=5)

frame = tk.Frame(app, bg="#F0F0F0")
frame.pack(pady=10)

tk.Entry(frame, textvariable=pasta_var, width=40, font=("Arial", 12), bd=2, relief="solid").pack(side=tk.LEFT, padx=10, pady=5)
tk.Button(frame, text="Procurar", command=escolher_pasta, bg="#5DADE2", fg="white", font=("Arial", 12, "bold"), width=10, relief="raised", height=2).pack(side=tk.LEFT)

tk.Label(app, text="Quantas músicas você deseja gerar?", font=("Arial", 12), bg="#F0F0F0").pack(pady=5)
tk.Entry(app, textvariable=num_musicas_var, width=5, font=("Arial", 12), bd=2, relief="solid").pack(pady=5)

tk.Button(app, text="Gerar Áudios", command=gerar_audios, bg="#5DADE2", fg="white", font=("Arial", 14, "bold"), width=20, height=2, relief="raised", padx=10, pady=10).pack(pady=20)

watermark_label = tk.Label(app, text="Feito por CaioRenatoDot", font=("Arial", 8), bg="#F0F0F0", fg="#888", anchor="se")
watermark_label.pack(side=tk.BOTTOM, padx=10, pady=5, anchor="se")

app.mainloop()
