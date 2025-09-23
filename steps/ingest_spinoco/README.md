# steps/01_ingest_spinoco

Krok 01: Stahování metadata hovorů a nahrávek ze Spinoco API.

## Přehled

Tento krok zajišťuje:
- ✅ **Ingest** metadata hovorů ze Spinoco API
- ✅ **Download** audio nahrávek (OGG formát)
- ✅ **Idempotence** pomocí SQLite state
- ✅ **Partial-fail** handling s retry logikou
- ✅ **Manifest/metrics** pro traceability
- ✅ **Bronze layer** output pro další kroky

## CLI

```bash
python run.py [OPTIONS]

Options:
  --mode {backfill,incr,dry}     Režim běhu (default: incr)
  --run-id <str>                 Step run ID (jinak vygeneruje ULID)
  --since <ISO>                  ISO timestamp pro backfill
  --only <recording_ids>         Cílený retry (comma-separated)
  --max-retry <int>              Max retry (default: 3)
  --limit <int>                  Omez počet recordingů
  --config <path>                Konfigurační soubor
```

## Příklady použití

### Incrementální běh
```bash
python run.py --mode incr
```

### Backfill od určitého data
```bash
python run.py --mode backfill --since 2024-01-01T00:00:00Z
```

### Retry konkrétních nahrávek
```bash
python run.py --only "20240822_054336_71da9579_p01,20240822_054336_71da9579_p02"
```

### Test s limitem
```bash
python run.py --limit 10 --config input/config.example.yaml
```

## Konfigurace

Kopíruj `input/config.example.yaml` do `config.yaml` a uprav:

```yaml
auth:
  api_base_url: "https://api.spinoco.com"
  token: "YOUR_TOKEN"

fetch:
  page_size: 100
  since: null

retry:
  max_retry: 3
  delay_seconds: 5

download:
  concurrency: 3
  validate_ogg_header: true
  temp_suffix: ".partial"

logging:
  level: "INFO"
  format: "json"
```

## Výstupy

### Struktura výstupů
```
output/runs/<STEP_RUN_ID>/
├── manifest.json          # Manifest s metadata
├── metrics.json           # Metriky běhu
├── progress.json          # Průběžný progress
├── success.ok            # Úspěšný běh
├── error.json            # Chyby (pokud jsou)
└── data/
    ├── metadata_call_tasks.jsonl
    ├── metadata_recordings.jsonl
    └── audio/
        ├── <recording_id>.ogg
        └── ...
```

### Manifest
```json
{
  "schema": "bh.v1.raw_audio",
  "schema_version": "1.0.0",
  "step_id": "01_ingest_spinoco",
  "step_run_id": "01J9ZC3AC9V2J9FZK2C3R8K9TQ",
  "status": "success",
  "outputs": {
    "primary": "metadata_recordings.jsonl",
    "aux": {
      "calls": "metadata_call_tasks.jsonl",
      "audio_dir": "audio/"
    }
  },
  "counts": {
    "calls": 1,
    "recordings": 2,
    "downloaded": 2,
    "failed": 0
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
- Quarantine: podezřelé soubory

### State Management
- SQLite databáze: `state/processed.sqlite`
- Idempotence: neopakuje již stažené
- Change detection: nové/změněné nahrávky

## Testování

```bash
# Spusť testy
python -m pytest tests/ -v

# Test s fake clientem
python run.py --limit 5 --config input/config.example.yaml
```

## Dependencies

- **common/lib**: ids, metadata, state, manifest
- **requests**: HTTP client pro Spinoco API
- **PyYAML**: Konfigurace
- **concurrent.futures**: Paralelní stahování

## Troubleshooting

### Časté problémy

1. **403 Forbidden**: Zkontroluj API token
2. **OGG validation failed**: Poškozené audio soubory
3. **Partial success**: Některé nahrávky selhaly - použij retry

### Logy
- Progress: `output/runs/<STEP_RUN_ID>/progress.json`
- Chyby: `output/runs/<STEP_RUN_ID>/error.json`
- State: `state/processed.sqlite`
