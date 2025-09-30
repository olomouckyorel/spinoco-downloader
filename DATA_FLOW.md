# 📊 Data Flow - Od Spinoco k Transkriptu

Kompletní flow dat od stažení OGG souborů ze Spinoco po finální transkripty.

---

## 🗂️ Struktura složek

### 1️⃣ Stažené OGG soubory (z Spinoco API)

```
steps/ingest_spinoco/output/runs/<INGEST_RUN_ID>/
└── data/
    ├── audio/
    │   ├── 193c444a-7e91-11f0-a473-2f775d7c125b.ogg  ⬅️ OGG SOUBORY ZDE
    │   ├── 61d115c1-8fa9-11f0-84bf-2d516126679c.ogg
    │   ├── 653335bc-8fad-11f0-9fcd-0763f6d52bb8.ogg
    │   ├── c12a8b58-8fac-11f0-9fcd-0763f6d52bb8.ogg
    │   └── d2b2d041-8fab-11f0-9b3a-815973e7b774.ogg
    ├── metadata_call_tasks.jsonl
    └── metadata_recordings.jsonl
```

**Vlastnosti:**
- ✅ **Zůstávají na místě** - nikdy se nemaž

ou
- 📦 **Formát**: OGG (Vorbis audio)
- 📝 **Metadata**: V `metadata_recordings.jsonl`
- 🔗 **Propojení**: `recording_id` → název souboru

---

### 2️⃣ Hotové transkripty

```
steps/transcribe_asr_adapter/output/runs/<TRANSCRIBE_RUN_ID>/
├── manifest.json                     # Metadata běhu
├── metrics.json                      # Statistiky
├── progress.json                     # Progress tracking
├── success.ok                        # Success marker
└── data/
    ├── transcripts_recordings.jsonl  ⬅️ HLAVNÍ VÝSTUP (recording-level)
    ├── transcripts_calls.jsonl       ⬅️ AGREGOVANÉ (call-level)
    └── temp/
        └── <recording_id>/
            └── <recording_id>_transcription.json  # Původní Whisper JSON
```

**Vlastnosti:**
- ✅ **Zůstávají na místě** - nikdy se nemažou
- 📄 **Formáty**: 
  - `transcripts_recordings.jsonl` - Jeden řádek = jeden audio soubor
  - `transcripts_calls.jsonl` - Jeden řádek = jeden hovor (může mít víc recordings)
- 📁 **temp/** - Originální Whisper výstupy pro debugging

---

### 3️⃣ Whisper modul (interní)

```
spinoco-whisper/
├── data/
│   ├── transcriptions/               ⬅️ VÝSTUPY WHISPER MODULU
│   │   ├── 193c444a-7e91-11f0-a473-2f775d7c125b_transcription.json
│   │   ├── 20250821_151918_420775646545_4_2min23s_193c444a_transcription.json
│   │   ├── 20250822_083016_420602404900_4_3min49s_ee5e06e7_transcription.json
│   │   ├── 20250822_084608_420583034592_4_11min17s_19db0e55_transcription.json
│   │   ├── 20250903_101835_420603815590_4_1min36s_5c826d37_transcription.json
│   │   └── 20250903_125136_420737937451_4_6min53s_ff1dba9f_transcription.json
│   └── processed/                    ⬅️ ZPRACOVANÉ OGG SOUBORY
│       ├── 20250821_151918_420775646545_4_2min23s_193c444a.ogg
│       ├── 20250822_083016_420602404900_4_3min49s_ee5e06e7.ogg
│       ├── 20250822_084608_420583034592_4_11min17s_19db0e55.ogg
│       ├── 20250903_101835_420603815590_4_1min36s_5c826d37.ogg
│       └── 20250903_125136_420737937451_4_6min53s_ff1dba9f.ogg
└── logs/
    └── transcriber.log               ⬅️ LOGY WHISPER MODULU
```

**Vlastnosti:**
- 🔄 **Starý workflow** - přímé volání Whisper modulu
- ✅ **OGG soubory se přesouvají** z input → `processed/`
- 📝 **Transkripty** zůstávají v `transcriptions/`

---

## 🔄 Data Flow Diagram

### Mode 1: **Nový workflow** (transcribe_asr_adapter)

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: ingest_spinoco                                      │
│                                                               │
│  Spinoco API  →  OGG soubory                                 │
│                  steps/ingest_spinoco/output/runs/           │
│                  └── <RUN_ID>/data/audio/*.ogg               │
│                      ↓                                        │
│                  metadata_recordings.jsonl                   │
│                  (recording_id, call_id, ...)                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ OGG soubory ZŮSTÁVAJÍ na místě
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: transcribe_asr_adapter                              │
│                                                               │
│  1. Načte metadata z předchozího run_id                      │
│  2. Pro každý recording:                                     │
│     a) Najde OGG soubor v ingest/output/runs/<ID>/audio/    │
│     b) Spustí Whisper transcriber (spinoco-whisper/main.py) │
│     c) Whisper vytvoří JSON v temp/ složce                   │
│     d) Adaptér normalizuje JSON do našeho formátu            │
│  3. Zapíše výsledky:                                         │
│     - transcripts_recordings.jsonl (recording-level)         │
│     - transcripts_calls.jsonl (call-level)                   │
│                                                               │
│  ✅ OGG soubory ZŮSTÁVAJÍ ve source složce                   │
│  ✅ Transkripty se ukládají do output/runs/<RUN_ID>/        │
└─────────────────────────────────────────────────────────────┘
```

### Mode 2: **Starý workflow** (přímý Whisper)

```
┌─────────────────────────────────────────────────────────────┐
│  spinoco-whisper/main.py                                     │
│                                                               │
│  Input folder  →  OGG soubory                                │
│  (konfigurovatelné)                                          │
│      ↓                                                        │
│  Whisper Large-v3                                            │
│      ↓                                                        │
│  data/transcriptions/*_transcription.json                    │
│      ↓                                                        │
│  OGG soubor se PŘESUNE do data/processed/                    │
│                                                               │
│  ⚠️  Tento režim se používá pouze pro standalone testy       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Logování

### Hlavní log soubor

```
logs/transcriber.log
```

**Obsah:**
- JSON formát (strukturované logování)
- Timestamp každé události
- Levely: INFO, WARNING, ERROR
- Real-time zápis během transkripce

**Příklad:**
```json
{"module": "transcriber", "event": "Načítám Whisper model: large-v3", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:06:12.157364Z"}
{"module": "transcriber", "event": "Whisper model úspěšně načten", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:06:41.145327Z"}
{"module": "transcriber", "event": "Začínám přepis souboru: 193c444a.ogg", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:06:41.158825Z"}
{"module": "transcriber", "event": "🎤 Audio: 0.7 MB, model: large-v3, device: cpu", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:06:41.161117Z"}
{"module": "transcriber", "event": "⏳ Transkripce běží...", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:06:41.161407Z"}
{"module": "transcriber", "event": "Přepis dokončen: 193c444a.ogg", "logger": "src.transcriber", "level": "info", "timestamp": "2025-09-30T10:15:37Z"}
```

---

## ❓ FAQ

### Q: Kde jsou originální OGG soubory?
**A:** `steps/ingest_spinoco/output/runs/<RUN_ID>/data/audio/*.ogg`
- ✅ Zůstávají tam napořád
- Můžete je použít pro retry nebo další zpracování

### Q: Přesouvají nebo mažou se OGG soubory?
**A:** **NE!** V novém workflow (transcribe_asr_adapter) zůstávají OGG soubory na místě.
- ✅ Bezpečné - můžete transkribovat opakovaně
- ✅ Idempotentní - žádná ztráta dat

### Q: Kam se ukládají transkripty?
**A:** `steps/transcribe_asr_adapter/output/runs/<RUN_ID>/data/`
- `transcripts_recordings.jsonl` - Recording-level (jeden řádek = jeden audio)
- `transcripts_calls.jsonl` - Call-level (jeden řádek = jeden hovor)

### Q: Co je v temp/ složce?
**A:** Originální Whisper JSON výstupy pro debugging
- Obsahuje kompletní Whisper metadata
- Používá se pro mapování do normalizovaného formátu

### Q: Kde se loguje?
**A:** `logs/transcriber.log` (JSON formát)
- Real-time logging během transkripce
- Sledujte pomocí `.\watch_logs.ps1`

### Q: Jaký je rozdíl mezi starým a novým workflow?
**A:** 
| Feature | Nový (transcribe_asr_adapter) | Starý (spinoco-whisper) |
|---------|-------------------------------|-------------------------|
| OGG soubory | Zůstávají na místě | Přesouvají se do processed/ |
| Výstup | Normalizovaný JSONL | Whisper JSON |
| State tracking | SQLite s idempotencí | Přesun souborů |
| Retry | Bezpečný | Musíte vrátit soubory |
| Pipeline | Součást 3-step pipeline | Standalone |

---

## 🔍 Jak to zjistit v kódu

### OGG soubory se nepřesouvají

**V `steps/transcribe_asr_adapter/run.py`:**
```python
# Řádek 299-302
audio_path = input_run_root / input_run_id / "data" / "audio" / f"{recording_id}.ogg"

if not audio_path.exists():
    raise FileNotFoundError(f"Audio soubor neexistuje: {audio_path}")
```
→ Jen **NAČÍTÁ** cestu, nikdy nemazání

### Transkripty se zapisují

**V `steps/transcribe_asr_adapter/run.py`:**
```python
# Řádek 470-475
recordings_path = self.data_dir / self.config['output']['transcripts_recordings']
with open(recordings_path, 'w', encoding='utf-8') as f:
    for result in results['successful']:
        transcript = result['transcript']
        json.dump(transcript, f, ensure_ascii=False)
        f.write('\n')
```
→ **ZAPÍŠE** do output/runs/<RUN_ID>/data/

### Logování

**V `spinoco-whisper/src/transcriber.py`:**
```python
# Řádek 24
self.logger = logger.bind(module="transcriber")

# Řádek 101
self.logger.info(f"Začínám přepis souboru: {audio_path.name}")
```
→ **LOGUJE** do logs/transcriber.log

---

## 📊 Příklad reálného flow

### 1. Stažení (ingest_spinoco)
```
RUN_ID: 01K6CPN9XFNSRPCCDZ98A9V2EH
Staženo: 5 OGG souborů
Umístění: steps/ingest_spinoco/output/runs/01K6CPN9XFNSRPCCDZ98A9V2EH/data/audio/
```

### 2. Transkripce (transcribe_asr_adapter)
```
INPUT_RUN: 01K6CPN9XFNSRPCCDZ98A9V2EH
RUN_ID: 01K6CTGKEGRGEK1M03NREVFXKH

Proces:
1. Načte metadata z 01K6CPN9XFNSRPCCDZ98A9V2EH
2. Najde OGG v audio/ složce (ZŮSTÁVÁ tam!)
3. Spustí Whisper → vytvoří JSON
4. Normalizuje do JSONL
5. Zapíše do output/runs/01K6CTGKEGRGEK1M03NREVFXKH/data/

Výstupy:
- transcripts_recordings.jsonl (1 nahrávka = 1 řádek)
- transcripts_calls.jsonl (1 hovor = 1 řádek)
```

### 3. Anonymizace (anonymize)
```
INPUT_RUN: 01K6CTGKEGRGEK1M03NREVFXKH
RUN_ID: 01K6XXXXXX...

Načte transkripty a anonymizuje citlivá data
```

---

**Všechno je bezpečné a reprodukovatelné! 🔒**
