# 🎙️ Spinoco Whisper Transcriber

Worker modul pro vysokou kvalitu přepisu audio nahrávek pomocí OpenAI Whisper Large-v3 modelu.

## 🎯 Účel

**Dual-mode transcription module:**
1. **Worker Mode** - Volaný z `transcribe_asr_adapter` v production pipeline
2. **Standalone Mode** - Pro rychlé testy a development

## 🏗️ Dva režimy použití

### 1️⃣ Production: Worker v Pipeline (DOPORUČENO)

```bash
# Tento modul je automaticky volán z transcribe_asr_adapter
cd ../../
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --config input\config.yaml
```

**Výhody:**
- ✅ State tracking (SQLite)
- ✅ Idempotence
- ✅ Retry logic
- ✅ Manifest generation
- ✅ Metrics
- ✅ Progress monitoring

**Volá se pomocí:**
```yaml
# steps/transcribe_asr_adapter/input/config.yaml
run_cmd: "{python} .../spinoco-whisper/main.py --input {audio} --output {out_dir}"
```

### 2️⃣ Development: Standalone

```bash
# Rychlý test jednoho souboru
cd spinoco-whisper
python main.py
```

**Použití:**
- ⚡ Rychlé testy
- 🔬 Experimentování s Whisper parametry
- 🐛 Debug jednotlivých souborů
- 🎯 Jednorázové úkoly

---

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
│   └── processed/        # Zpracované audio soubory (standalone mode)
├── logs/                 # Log soubory (sdílené)
├── main.py              # Spouštěcí bod
└── requirements.txt     # Python dependencies
```

---

## 🚀 Instalace

Instalace je součástí hlavního projektu:

```bash
# Z root složky projektu
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## ⚙️ Konfigurace

### Pro Production (Worker Mode)

Konfigurace je v `steps/transcribe_asr_adapter/input/config.yaml`:

```yaml
asr:
  run_cmd: "{python} .../spinoco-whisper/main.py --input {audio} --output {out_dir}"
  outputs_glob: "**/*_transcription.json"
```

### Pro Standalone Mode

V `spinoco-whisper/.env`:

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

---

## 🎯 CLI API

### Standalone Mode

```bash
python main.py
```

Zpracuje všechny `.ogg` soubory v `INPUT_FOLDER`.

### Worker Mode (voláno z pipeline)

```bash
python main.py --input <audio.ogg> --output <output_dir>
```

**Parametry:**
- `--input` - Cesta k audio souboru
- `--output` - Výstupní složka pro JSON

**Exit codes:**
- `0` - Úspěch (JSON vytvořen)
- `1` - Chyba

**Výstup:**
- `<output_dir>/<filename>_transcription.json`

---

## 📊 Výstupní formát

Každý přepis je uložen jako JSON soubor s kompletními metadaty:

```json
{
  "transcription": {
    "text": "Celý přepsaný text...",
    "language": "cs",
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "Dobrý den, technická podpora"
      }
    ]
  },
  "metadata": {
    "call_date": "2025-09-30T14:30:00",
    "caller_number": "420123456789",
    "duration": "5min30s",
    "recording_id": "193c444a-7e91-11f0-a473-2f775d7c125b",
    "transcribed_at": "2025-09-30T10:15:37Z",
    "whisper_model": "large-v3",
    "audio_file_size": 734567
  },
  "processing_info": {
    "device_used": "cpu",
    "whisper_settings": {
      "temperature": 0.0,
      "best_of": 5,
      "beam_size": 5,
      "condition_on_previous_text": true
    }
  }
}
```

---

## 🔧 Workflow podle režimu

### Worker Mode (v pipeline)
```
1. transcribe_asr_adapter volá: main.py --input audio.ogg --output temp/
2. Whisper zpracuje audio
3. JSON se uloží do temp/
4. transcribe_asr_adapter normalizuje výstup
5. Vytvoří se finální transcripts_*.jsonl
```

**Audio soubory:** Zůstávají v původní složce (`steps/ingest_spinoco/output/runs/<ID>/data/audio/`)

### Standalone Mode
```
1. main.py načte soubory z INPUT_FOLDER
2. Whisper zpracuje každý soubor
3. JSON se uloží do data/transcriptions/
4. OGG soubor se přesune do data/processed/
```

**Audio soubory:** Přesunou se do `processed/`

---

## 🎛️ Optimalizace kvality

- **Model**: `large-v3` (nejlepší dostupný)
- **Temperature**: `0.0` (deterministický výstup)
- **Best of**: `5` (5 pokusů, nejlepší výsledek)
- **Beam search**: `5` (širší hledání)
- **Language**: Explicitně nastaveno na češtinu
- **Verbose mode**: Pro real-time progress visibility
- **Custom prompt**: Optimalizováno pro HVAC/technickou podporu

---

## 📈 Výkon

| Device | Model | Speed | Kvalita |
|--------|-------|-------|---------|
| CPU | large-v3 | ~3-4x audio délky | ⭐⭐⭐⭐⭐ |
| CPU | base | ~0.5x audio délky | ⭐⭐⭐ |
| GPU | large-v3 | ~1x audio délky | ⭐⭐⭐⭐⭐ |

**Paměť:**
- Large-v3: ~4-8 GB RAM (CPU) nebo ~2-4 GB VRAM (GPU)
- Base: ~2-4 GB RAM

**Typické časy (CPU, Large-v3):**
- 2 min audio → ~8 minut
- 5 min audio → ~15 minut
- 10 min audio → ~30 minut

---

## 🔗 Integrace v Pipeline

Tento modul je **worker component** v 3-step pipeline:

```
┌──────────────────────────────────────────────┐
│ Step 1: ingest_spinoco                       │
│ Stáhne OGG soubory ze Spinoco API            │
└────────────┬─────────────────────────────────┘
             │
             │ OGG files
             ↓
┌──────────────────────────────────────────────┐
│ Step 2: transcribe_asr_adapter (ORCHESTRATOR)│
│   ├─→ Volá: spinoco-whisper (WORKER) ←──┐   │
│   ├─→ State tracking                     │   │
│   ├─→ Retry logic                        │   │
│   └─→ Normalizace výstupu                │   │
└────────────┬─────────────────────────────┘   │
             │                                  │
             │ Normalized transcripts           │
             ↓                                  │
┌──────────────────────────────────────────────┘
│ Step 3: anonymize                            
│ Anonymizuje citlivá data                     
└──────────────────────────────────────────────┘
```

**Pro production vždy používejte:**
```bash
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py
```

**Standalone režim je jen pro development!**

---

## 🧪 Testování

### Quick Test (Standalone)

```bash
# Umístěte test.ogg do INPUT_FOLDER
python main.py
# Výstup: data/transcriptions/test_transcription.json
```

### Test v Pipeline

```bash
# S monitoringem
.\watch_all.ps1  # Terminal 1
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --limit 1 --config input\config.yaml  # Terminal 2
```

---

## 📝 Logování

### Log soubor

```
logs/transcriber.log
```

**Formát:** JSON (strukturované logování)

**Sledování:**
```powershell
.\watch_logs.ps1  # Real-time monitoring
```

**Příklad:**
```json
{"module": "transcriber", "event": "Whisper model úspěšně načten", "level": "info", "timestamp": "2025-09-30T10:06:41Z"}
{"module": "transcriber", "event": "🎤 Audio: 0.7 MB, model: large-v3", "level": "info", "timestamp": "2025-09-30T10:06:41Z"}
{"module": "transcriber", "event": "Přepis dokončen", "level": "info", "timestamp": "2025-09-30T10:15:37Z"}
```

---

## 🔄 Kdy použít který režim?

| Use Case | Režim | Proč |
|----------|-------|------|
| Production pipeline | **Worker** (přes transcribe_asr_adapter) | State tracking, retry, manifest |
| Bulk processing | **Worker** (přes transcribe_asr_adapter) | Paralelizace, progress tracking |
| Rychlý test 1 souboru | **Standalone** | Rychlé, jednoduché |
| Experimentování s parametry | **Standalone** | Bez pipeline overhead |
| Debug problematického souboru | **Standalone** | Izolované testování |

---

## ⚠️ Důležité poznámky

### Production
- ✅ **VŽDY** používejte `transcribe_asr_adapter` pro production
- ✅ OGG soubory zůstávají na místě (bezpečné retry)
- ✅ Máte state tracking a idempotenci
- ✅ Můžete sledovat progress

### Standalone
- ⚠️ OGG soubory se **přesouvají** do `processed/`
- ⚠️ Žádný state tracking
- ⚠️ Retry = musíte ručně vrátit soubory
- ✅ Rychlé pro jednorázové testy

---

## 📚 Související dokumentace

- **[../README.md](../README.md)** - Celý projekt
- **[../steps/transcribe_asr_adapter/README.md](../steps/transcribe_asr_adapter/README.md)** - Orchestrator dokumentace
- **[../DATA_FLOW.md](../DATA_FLOW.md)** - Data flow diagram
- **[../MONITORING.md](../MONITORING.md)** - Monitoring guide

---

**Worker Module v Production Pipeline** 🔧⚙️