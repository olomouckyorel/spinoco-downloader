# steps/02_transcribe_asr_adapter

Krok 02: Adaptace existující Whisper transkripce do standardizovaného formátu.

## Přehled

Tento krok zajišťuje:
- ✅ **Adaptaci** existující Whisper JSON výstupu
- ✅ **Normalizaci** do recording-level a call-level formátu
- ✅ **Idempotenci** pomocí SQLite state
- ✅ **Partial-fail** handling s retry logikou
- ✅ **Manifest/metrics** pro traceability
- ✅ **Bronze → Silver** transformace

## CLI

```bash
python run.py [OPTIONS]

Options:
  --mode {backfill,incr,dry}     Režim běhu (default: incr)
  --input-run <STEP_RUN_ID>      Step run ID předchozího kroku (povinné)
  --run-id <str>                 Step run ID (jinak vygeneruje ULID)
  --only <recording_ids>         Cílený retry (comma-separated)
  --max-retry <int>              Max retry (default: 2)
  --limit <int>                  Omez počet recordingů
  --config <path>                Konfigurační soubor
```

## Příklady použití

### Import existujících transkriptů
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --mode import
```

### Spuštění externího transcriberu
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --mode run
```

### Retry konkrétních nahrávek
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --only "20240822_054336_71da9579_p01"
```

## Konfigurace

Kopíruj `input/config.example.yaml` do `config.yaml` a uprav:

```yaml
asr:
  provider: "existing"                # explicitně
  mode: "run"                         # 'run' = spouštět tvůj skript, 'import' = jen načíst existující JSONy
  run_cmd: "python ../spinoco-whisper/main.py --input {audio} --output {out_dir}"
  outputs_glob: "**/*_transcription.json"
  language: "cs"

io:
  input_run_root: "../ingest_spinoco/output/runs"
  max_parallel: 2

retry:
  max_retry: 2
  delay_seconds: 5
```

## Režimy práce

### Mode: `run`
Spustí externí transcriber pro každou nahrávku:
- Nahradí `{audio}` a `{out_dir}` v `run_cmd`
- Spustí příkaz pomocí subprocess
- Najde výstupní JSON podle `outputs_glob`

### Mode: `import`
Načte existující JSON soubory:
- Hledá soubory podle `outputs_glob`
- Mapuje na `recording_id` podle názvu souboru
- Nepotřebuje spouštět externí nástroje

## Výstupy

### Struktura výstupů
```
output/runs/<STEP_RUN_ID>/
├── manifest.json              # Manifest s metadata
├── metrics.json               # Metriky běhu
├── progress.json              # Průběžný progress
├── success.ok                 # Úspěšný běh
├── error.json                 # Chyby (pokud jsou)
└── data/
    ├── transcripts_recordings.jsonl
    └── transcripts_calls.jsonl
```

### Recording-level format
```json
{
  "call_id": "20240822_054336_71da9579",
  "recording_id": "20240822_054336_71da9579_p01",
  "duration_s": 229.0,
  "lang": "cs",
  "asr": {
    "provider": "existing",
    "model": "large-v3",
    "device": "cpu",
    "settings": {
      "beam_size": 5,
      "best_of": 5,
      "temperature": 0.0
    }
  },
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Testovací přepis hovoru"
    }
  ],
  "text": "Testovací přepis hovoru o technické podpoře...",
  "metrics": {
    "seg_count": 15,
    "avg_seg_len_s": 15.3
  },
  "source": {
    "audio_path": "audio/20240822_054336_71da9579_p01.ogg",
    "transcript_source": "existing-json"
  }
}
```

### Call-level format
```json
{
  "call_id": "20240822_054336_71da9579",
  "duration_s": 458.0,
  "lang": "cs",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Testovací přepis hovoru",
      "recording_id": "20240822_054336_71da9579_p01"
    }
  ],
  "text": "[--- 20240822_054336_71da9579_p01 ---]\n\nTestovací přepis...",
  "metrics": {
    "recording_count": 2,
    "total_segments": 30,
    "avg_seg_len_s": 15.3
  }
}
```

## Error Handling

### Partial Success
Pokud některé nahrávky selžou:
- Status: `"partial"`
- `error.json` obsahuje seznam failed recording_ids
- Retry command pro opravu

### Retry Logika
- Transient chyby: retry_count < max_retry
- Permanent chyby: retry_count >= max_retry
- Idempotence: neopakuje již zpracované

### State Management
- SQLite databáze: `state/transcribed.sqlite`
- Tracking: asr_settings_hash, transcript_hash
- Change detection: nové/změněné transkripty

## Mapování Whisper → Náš formát

### Vstupní Whisper JSON
```json
{
  "transcription": {
    "text": "...",
    "language": "cs",
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "..."
      }
    ]
  },
  "metadata": {
    "whisper_model": "large-v3",
    "device_used": "cpu",
    "beam_size": 5
  }
}
```

### Výstupní normalizovaný formát
- **call_id/recording_id**: Z předchozího kroku
- **asr.provider**: Vždy "existing"
- **asr.model**: Z `metadata.whisper_model`
- **asr.settings**: Všechny Whisper parametry
- **segments**: Pouze start/end/text
- **metrics**: Vypočtené z dat

## Testování

```bash
# Test s fixtures
python run.py --input-run test_run --mode import --config input/config.example.yaml

# Test s limitem
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --limit 5
```

## Dependencies

- **common/lib**: ids, state, manifest
- **PyYAML**: Konfigurace
- **concurrent.futures**: Paralelní zpracování
- **hashlib**: Hash pro idempotenci

## Troubleshooting

### Časté problémy

1. **Input manifest neexistuje**: Zkontroluj `--input-run`
2. **Audio soubory chybí**: Spusť předchozí krok
3. **JSON nenalezen**: Zkontroluj `outputs_glob` pattern
4. **Partial success**: Některé nahrávky selhaly - použij retry

### Logy
- Progress: `output/runs/<STEP_RUN_ID>/progress.json`
- Chyby: `output/runs/<STEP_RUN_ID>/error.json`
- State: `state/transcribed.sqlite`
