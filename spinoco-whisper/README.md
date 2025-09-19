# 🎙️ Spinoco Whisper Transcriber

Vysoká kvalita přepisu audio nahrávek pomocí OpenAI Whisper Large-v3 modelu.

## 🎯 Účel

Tento modul přepisuje audio soubory (.ogg) stažené ze Spinoco API na text s nejvyšší možnou kvalitou. Používá Whisper Large-v3 model optimalizovaný pro češtinu.

## 🏗️ Architektura

```
spinoco-whisper/
├── src/
│   ├── transcriber.py    # Hlavní transcription logic
│   ├── config.py         # Konfigurace
│   └── logger.py         # Strukturované logování
├── config/
│   └── env.example       # Template pro .env
├── data/
│   ├── transcriptions/   # Výstupní JSON soubory
│   └── processed/        # Zpracované audio soubory
├── logs/                 # Log soubory
├── main.py              # Spouštěcí bod
└── requirements.txt     # Python dependencies
```

## 🚀 Instalace

1. **Vytvoření virtuálního prostředí:**
```bash
cd spinoco-whisper
python -m venv venv
venv\Scripts\activate  # Windows
```

2. **Instalace závislostí:**
```bash
pip install -r requirements.txt
```

3. **Konfigurace:**
```bash
copy config\env.example .env
# Upravte .env podle potřeby
```

## ⚙️ Konfigurace

Klíčové nastavení v `.env`:

```env
# Whisper model (large-v3 pro nejvyšší kvalitu)
WHISPER_MODEL=large-v3
WHISPER_LANGUAGE=czech

# Cesty
INPUT_FOLDER=../downloaded_recordings
OUTPUT_FOLDER=./data/transcriptions

# Kvalita (pro nejvyšší kvalitu)
WHISPER_TEMPERATURE=0.0
WHISPER_BEST_OF=5
WHISPER_BEAM_SIZE=5
```

## 🎯 Použití

### Automatické zpracování všech souborů:
```bash
python main.py
```

### Programové použití:
```python
from src.transcriber import TranscriberModule

transcriber = TranscriberModule()
result = transcriber.transcribe_file(Path("audio.ogg"))
```

## 📊 Výstupní formát

Každý přepis je uložen jako JSON soubor s kompletními metadaty:

```json
{
  "transcription": {
    "text": "Celý přepsaný text...",
    "language": "cs",
    "segments": [...]
  },
  "metadata": {
    "call_date": "2024-01-15T14:30:00",
    "caller_number": "420123456789",
    "duration": "5min30s",
    "recording_id": "abc12345"
  },
  "processing_info": {
    "whisper_model": "large-v3",
    "device_used": "cuda"
  }
}
```

## 🔧 Workflow

1. **Input**: Audio soubory v `INPUT_FOLDER`
2. **Processing**: Whisper Large-v3 přepis
3. **Output**: JSON soubory v `OUTPUT_FOLDER`
4. **Cleanup**: Zpracované audio → `processed/`

## 🎛️ Optimalizace kvality

- **Model**: `large-v3` (nejlepší dostupný)
- **Temperature**: `0.0` (deterministický výstup)
- **Best of**: `5` (5 pokusů, nejlepší výsledek)
- **Beam search**: `5` (širší hledání)
- **Language**: Explicitně nastaveno na češtinu

## 📈 Výkon

- **Rychlost**: ~1-2x real-time na GPU
- **Kvalita**: Nejvyšší dostupná
- **Paměť**: ~2-4 GB VRAM (GPU) nebo ~8 GB RAM (CPU)

## 🔗 Integrace

Tento modul je součástí většího pipeline:
1. `spinoco-download` → stahuje audio
2. **`spinoco-whisper`** → přepisuje na text  ← WE ARE HERE
3. `spinoco-filter` → filtruje technické dotazy
4. `spinoco-categorizer` → kategorizuje problémy
5. `spinoco-knowledge` → ukládá do knowledge base
