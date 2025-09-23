# tools/

Nástroje pro testování a správu pipeline.

## smoke5.py

One-shot smoke test na 5 nahrávek. Sekvenčně spustí:

1. **steps/01_ingest_spinoco** - stáhne 5 nahrávek ze Spinoca
2. **steps/02_transcribe_asr_adapter** - přepíše je pomocí Whisper

### Použití

```bash
# Základní použití (5 nahrávek)
python tools/smoke5.py

# Vlastní limit
python tools/smoke5.py --limit 3

# Pomocí wrapper scriptů
./scripts/smoke5.sh
scripts/smoke5.bat
```

### Požadavky

Před spuštěním musí existovat:

- `steps/ingest_spinoco/input/config.yaml` (zkopíruj z `.example.yaml` a vyplň token)
- `steps/transcribe_asr_adapter/input/config.yaml` (zkopíruj z `.example.yaml`)

### Výstup

Smoke test vytvoří:

- **Ingest run**: `steps/ingest_spinoco/output/runs/<ULID>/`
  - `data/audio/*.ogg` - stažené nahrávky
  - `manifest.json` - metadata běhu
  - `metrics.json` - statistiky

- **Transcribe run**: `steps/transcribe_asr_adapter/output/runs/<ULID>/`
  - `data/transcripts_recordings.jsonl` - recording-level transkripty
  - `data/transcripts_calls.jsonl` - call-level transkripty
  - `manifest.json` - metadata běhu
  - `metrics.json` - statistiky

### Barevný výstup

- 🔧 **RUNNING** - krok běží
- ✅ **SUCCESS** - krok úspěšný
- ❌ **FAILED** - krok selhal
- ⚠️ **WARNING** - částečný úspěch

### Návratové kódy

- `0` - Úspěch (včetně partial success)
- `1` - Selhání (chybějící config, ingest fail, transcribe hard fail)

### Příklady výstupu

```
============================================================
 SMOKE TEST - 5 NAHRÁVEK
============================================================
Limit: 5 nahrávek

============================================================
 KONTROLA KONFIGURACÍ
============================================================
✅ Všechny konfigurace existují

============================================================
 KROK 1: INGEST SPINOCO
============================================================
🔧 INGEST [RUNNING]
Příkaz: python run.py --mode incr --limit 5 --max-retry 2 --config input/config.yaml
...
🔧 INGEST [SUCCESS]
✅ Dokončeno za 45.2s

============================================================
 KROK 2: TRANSCRIBE ASR ADAPTER
============================================================
🔧 TRANSCRIBE [RUNNING]
Příkaz: python run.py --mode incr --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --limit 5 --max-retry 2 --config input/config.yaml
...
🔧 TRANSCRIBE [SUCCESS]
✅ Dokončeno za 120.5s

============================================================
 SHRNUTÍ VÝSLEDKŮ
============================================================
📁 CESTY K SOUBORŮM:
  INGEST manifest:   steps/ingest_spinoco/output/runs/01J9ZC3AC9V2J9FZK2C3R8K9TQ/manifest.json
  INGEST metrics:    steps/ingest_spinoco/output/runs/01J9ZC3AC9V2J9FZK2C3R8K9TQ/metrics.json
  TRANSCRIBE manifest: steps/transcribe_asr_adapter/output/runs/01J9ZC4BD8W3K0GLZ4D4S9L0TR/manifest.json
  TRANSCRIBE metrics:  steps/transcribe_asr_adapter/output/runs/01J9ZC4BD8W3K0GLZ4D4S9L0TR/metrics.json

📊 METRIKY:
  INGEST:
    📥 Recordings total: 5
    ✅ Downloaded OK:     5
    ❌ Failed:            0
  TRANSCRIBE:
    📥 Recordings total: 5
    ✅ Transcribed OK:    5
    ❌ Failed:            0
    📞 Calls total:       3

📄 VÝSTUPNÍ SOUBORY:
  ✅ transcripts_recordings.jsonl: steps/transcribe_asr_adapter/output/runs/01J9ZC4BD8W3K0GLZ4D4S9L0TR/data/transcripts_recordings.jsonl
  ✅ transcripts_calls.jsonl: steps/transcribe_asr_adapter/output/runs/01J9ZC4BD8W3K0GLZ4D4S9L0TR/data/transcripts_calls.jsonl

============================================================
 FINÁLNÍ STATUS
============================================================
🎉 SMOKE TEST ÚSPĚŠNÝ!

💡 Prohlédni si výsledky:
   📖 Otevři: steps/transcribe_asr_adapter/output/runs/01J9ZC4BD8W3K0GLZ4D4S9L0TR/data/transcripts_calls.jsonl
```

### Troubleshooting

**Chybějící konfigurace:**
```
❌ Chybí konfigurační soubor: steps/ingest_spinoco/input/config.yaml
   Zkopíruj steps/ingest_spinoco/input/config.example.yaml a vyplň token
```
→ Zkopíruj `.example.yaml` soubory a vyplň API token

**Ingest selhal:**
```
❌ Ingest selhal - ukončuji
```
→ Zkontroluj API token a připojení k Spinocu

**Transcribe partial success:**
```
⚠️ SMOKE TEST ČÁSTEČNĚ ÚSPĚŠNÝ (partial success)
```
→ Některé nahrávky se nepodařilo přepsat, ale výsledky jsou k dispozici

**Transcribe hard fail:**
```
❌ SMOKE TEST SELHAL
```
→ Zkontroluj Whisper instalaci a konfiguraci
