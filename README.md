# 🎶 RythmImitation - Gerador e Treinador de Padrões Rítmicos 🎶
![Image](https://github.com/user-attachments/assets/f3b3f4e0-7e58-4fbd-afee-860ce7e61984)

O **RythmImitation** gera **padrões rítmicos melódicos**, toca-os na hora com a partitura na tela e
treina você para **imitá-los**: o app toca o ritmo, você repete na barra de espaço e recebe uma nota
de precisão para cada batida. Também exporta lotes de áudios (WAV/MP3/MIDI) com gabarito, mantendo o
uso original de criar arquivos de 6 segundos a 100 BPM. 🥁🎹

## ✨ Funcionalidades

- **Ouça na hora** ▶ — reprodução em tempo real com cursor que acompanha a partitura e destaca a nota que está soando.
- **Partitura de verdade** 🎼 — clave de sol, compassos, colchetes, barras de ligação, pausas, pontos, tercinas, linhas suplementares e nomes das notas (Dó, Ré, Mi…).
- **Modo treino (imitação)** 🎯 — contagem → o app toca o ritmo → contagem → você toca junto com o metrônomo (Espaço, Enter ou clique). Cada nota fica verde/laranja/vermelha, com porcentagem, tendência (adiantado/atrasado) e histórico de tentativas.
- **Treino de ouvido** 🎧 — esconde as notas durante o treino e só revela a partitura no final.
- **Calibração de latência** ⏱ — mede o atraso do seu fone/teclado para a pontuação ser justa.
- **4 níveis de dificuldade** — de semínimas e mínimas até semicolcheias, síncopes, tercinas e contratempos. Os compassos são sempre completos e escritos de forma legível.
- **Compassos 2/4, 3/4, 4/4 e 5/4**, de 1 a 8 compassos, andamento de 40 a 200 BPM.
- **7 escalas** (incluindo a original Dó-Mi-Sol-Lá, maior, menor, pentatônicas e blues) com melodias que andam por graus e resolvem na tônica.
- **6 timbres sintetizados** — piano elétrico, marimba, violão (Karplus-Strong), flauta, senoide clássica e bloco de madeira (só ritmo). Sem cliques, com volume nivelado e afinação exata.
- **Sementes reprodutíveis** 🔁 — cada ritmo tem um número; digite-o para recriar exatamente o mesmo exercício (ótimo para professores).
- **Exportação**: áudio WAV (MP3 se o `ffmpeg` estiver instalado) e **MIDI**, individual ou em **lote** (até 500), com opção de metrônomo, contagem e **duração exata** (ex.: 6 s), além de **gabarito CSV** com figuras, notas e sementes.

## ⌨️ Atalhos

| Tecla | Ação |
|---|---|
| `Espaço` | Tocar/parar (no treino: bater o ritmo) |
| `N` | Novo ritmo |
| `T` | Treinar imitação |
| `Esc` | Parar |
| `Ctrl+S` / `Ctrl+M` | Salvar áudio / MIDI |

## 🚀 Como usar

**Executável (Windows):** rode `dist/RythmImitation.exe`. Não precisa de Python.

**Pelo código-fonte:**

```bash
pip install -r requirements.txt
python main.py          # ou: python -m rythm_imitation
```

## 🛠️ Desenvolvimento

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest          # testes
.venv\Scripts\python build.py           # gera dist/RythmImitation.exe
```

`dist/RythmImitation.exe --selftest relatorio.txt` abre o app, toca um ritmo em volume zero e grava um relatório. É útil para validar o executável gerado.

### Estrutura

```
rythm_imitation/
  theory.py    figuras, células rítmicas por nível, escalas e geração de padrões
  synth.py     síntese (numpy), metrônomo, normalização e exportação WAV/MP3
  midi.py      escrita de arquivos .mid sem dependências
  player.py    reprodução em tempo real com relógio sincronizado ao DAC
  scoring.py   alinhamento ótimo batidas × notas (programação dinâmica)
  notation.py  desenho da partitura no Canvas
  app.py       interface (ttkbootstrap)
tests/         testes de teoria, áudio, MIDI, pontuação e interface
```

## 🧰 Tecnologias

- `numpy`: síntese de áudio. 🎧
- `sounddevice` (PortAudio): reprodução de baixa latência, com `winsound` como reserva. 🔊
- `ttkbootstrap` / `tkinter`: interface gráfica. 🖥️
- `PyInstaller`: executável do Windows. 📦

Feito por **CaioRenatoDot**.
