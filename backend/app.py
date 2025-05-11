import sys
from pydub.generators import Sine
from pydub import AudioSegment
import os
import random

BPM = 100
BEAT_DURATION_MS = int(60000 / BPM)
TOTAL_AUDIO_DURATION_MS = 6000

def get_symbol_duration_ms(symbol):
    if symbol == "♩":
        return BEAT_DURATION_MS
    elif symbol == "♪":
        return BEAT_DURATION_MS // 2
    elif symbol == "𝅗𝅥":
        return BEAT_DURATION_MS * 2
    return BEAT_DURATION_MS

def create_melodic_pattern_audio(pattern, melody):
    audio = AudioSegment.silent(duration=0)
    for i, symbol in enumerate(pattern):
        tone = melody[i % len(melody)]
        duration = get_symbol_duration_ms(symbol)
        tone = tone[:min(len(tone), duration - 10)]
        silence = AudioSegment.silent(duration=duration - len(tone))
        audio += tone + silence

    if len(audio) < TOTAL_AUDIO_DURATION_MS:
        audio += AudioSegment.silent(duration=TOTAL_AUDIO_DURATION_MS - len(audio))
    elif len(audio) > TOTAL_AUDIO_DURATION_MS:
        audio = audio[:TOTAL_AUDIO_DURATION_MS]
    return audio

def generate_random_melody():
    notas = [
        Sine(261.63).to_audio_segment(duration=100).apply_gain(-3),  # C4
        Sine(329.63).to_audio_segment(duration=100).apply_gain(-3),  # E4
        Sine(392.00).to_audio_segment(duration=100).apply_gain(-3),  # G4
        Sine(523.25).to_audio_segment(duration=100).apply_gain(-3),  # C5
        Sine(440.00).to_audio_segment(duration=100).apply_gain(-3),  # A4
    ]
    return [random.choice(notas) for _ in range(16)]

def completar_pattern(pattern):
    total_beats = sum({
        "♩": 1, "♪": 0.5, "𝅗𝅥": 2
    }[s] for s in pattern)
    while total_beats < 10:
        pattern.append("♪")
        total_beats += 0.5
    return pattern

def gerar_audios(pasta, num_musicas):
    patterns = [
        ["♩"] * 10,
        ["♪"] * 20,
        ["♩", "♪", "♩", "♪", "♩", "♪", "♩", "♪", "♩", "♪"],
        ["𝅗𝅥", "𝅗𝅥", "♩", "♩", "♪", "♪"],
        ["♩", "♩", "♩", "♩", "♩", "♩", "♪", "♪", "♪", "♪"],
        ["𝅗𝅥", "♩", "♩", "𝅗𝅥", "♪", "♪"],
    ]

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
        print(f"Áudio gerado: {filename}")

    print(f"\n{num_musicas} áudios gerados com sucesso na pasta: {pasta}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python app.py <caminho_da_pasta> <quantidade>")
        sys.exit(1)

    pasta = sys.argv[1]
    try:
        quantidade = int(sys.argv[2])
    except ValueError:
        print("Erro: a quantidade precisa ser um número inteiro.")
        sys.exit(1)

    if not os.path.exists(pasta):
        print("Erro: a pasta informada não existe.")
        sys.exit(1)

    gerar_audios(pasta, quantidade)
