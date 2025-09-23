# CONTRACT.md - steps/01_ingest_spinoco

## Input Contract

### Povinné vstupy
- **Konfigurace**: `input/config.yaml` nebo `--config`
- **Spinoco API**: Token a base URL v konfiguraci

### Volitelné vstupy
- **--since**: ISO timestamp pro backfill
- **--only**: Seznam recording_ids pro retry
- **--limit**: Omezení počtu recordingů

### Žádné externí soubory
Krok nevyžaduje žádné externí vstupní soubory - vše čte ze Spinoco API.

## Output Contract

### Povinné výstupy
1. **manifest.json**: Manifest s metadata běhu
2. **metrics.json**: Metriky výkonu
3. **data/metadata_call_tasks.jsonl**: Normalizované call metadata
4. **data/metadata_recordings.jsonl**: Normalizované recording metadata

### Podmíněné výstupy
- **success.ok**: Pouze při úspěšném běhu
- **error.json**: Pouze při chybách nebo partial success
- **data/audio/<recording_id>.ogg**: Stažené audio soubory

### Progress tracking
- **progress.json**: Průběžný progress (vždy)

## Data Formats

### Call Task JSONL
```json
{
  "call_id": "20240822_054336_71da9579",
  "spinoco_call_guid": "71da9579-7730-11ee-9300-a3a8e273fd52",
  "last_update_ms": 1724305416000,
  "call_ts_utc": "2024-08-22T05:43:36Z",
  "raw": { /* původní Spinoco data */ }
}
```

### Recording JSONL
```json
{
  "spinoco_recording_id": "recording_001",
  "spinoco_call_guid": "71da9579-7730-11ee-9300-a3a8e273fd52",
  "recording_id": "20240822_054336_71da9579_p01",
  "recording_date_ms": 1724305416000,
  "recording_ts_utc": "2024-08-22T05:43:36Z",
  "duration_s": 229,
  "available": true,
  "raw": { /* původní Spinoco data */ }
}
```

### Audio Files
- **Formát**: OGG Vorbis
- **Název**: `<recording_id>.ogg`
- **Validace**: OGG header ("OggS")

## Failure Modes

### 1. Partial Success
- **Status**: `"partial"`
- **Příčina**: Některé nahrávky selhaly
- **Akce**: Retry s `--only <failed_ids>`
- **Output**: `error.json` s retry command

### 2. Complete Failure
- **Status**: `"error"`
- **Příčina**: Kritická chyba (API, konfigurace)
- **Akce**: Oprava konfigurace, restart
- **Output**: `error.json` s error details

### 3. No Data
- **Status**: `"success"`
- **Příčina**: Žádné nové hovory/nahrávky
- **Akce**: Normální stav
- **Output**: Prázdné data soubory

## Idempotence

### State Management
- **SQLite**: `state/processed.sqlite`
- **Tabulky**: `calls`, `recordings`
- **Statusy**: `pending`, `downloaded`, `failed-transient`, `failed-permanent`, `quarantined`

### Retry Logic
- **Transient chyby**: Retry až do `max_retry`
- **Permanent chyby**: Quarantine
- **Change detection**: Nové/změněné nahrávky

### Idempotent Operations
- ✅ Opakovaný běh neopakuje stažené nahrávky
- ✅ Partial retry s `--only` funguje
- ✅ State se aktualizuje atomicky

## Performance

### Paralelní stahování
- **Concurrency**: Konfigurovatelné (default: 3)
- **Threading**: `concurrent.futures.ThreadPoolExecutor`
- **Progress**: Real-time aktualizace

### Metriky
- **Throughput**: MB/s
- **Runtime**: Celkový čas běhu
- **Counts**: Calls, recordings, downloaded, failed

## Dependencies

### External
- **Spinoco API**: HTTP REST API
- **Common library**: ids, metadata, state, manifest

### Internal
- **SQLite**: State management
- **JSONL**: Output format
- **YAML**: Configuration

## Testing

### Test Scenarios
1. **Happy path**: 1 call, 2 recordings → success
2. **Partial fail**: 1 call, 2 recordings → 1 fail → partial
3. **Retry**: Retry failed recording → success

### Test Data
- **Fixtures**: `input/fixtures/`
- **Fake client**: Simuluje Spinoco API
- **Mock data**: Realistická test data

## Monitoring

### Progress Tracking
- **Phase**: fetch_calls, fetch_recordings, download, snapshots
- **Percentage**: 0-100%
- **ETA**: Odhadovaný čas dokončení
- **Messages**: Popis aktuální aktivity

### Error Reporting
- **Error types**: download_error, invalid_ogg_header, api_error
- **Retry info**: retry_count, max_retry
- **Context**: recording_id, error message
