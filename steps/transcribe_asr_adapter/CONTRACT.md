# CONTRACT.md - steps/02_transcribe_asr_adapter

## Input Contract

### Povinné vstupy
- **--input-run**: Step run ID předchozího kroku (01_ingest_spinoco)
- **Konfigurace**: `input/config.yaml` nebo `--config`

### Volitelné vstupy
- **--only**: Seznam recording_ids pro retry
- **--limit**: Omezení počtu recordingů
- **--mode**: run/import režim

### Vstupní soubory (z předchozího kroku)
- **manifest.json**: Manifest z předchozího kroku
- **metadata_recordings.jsonl**: Metadata nahrávek
- **audio/<recording_id>.ogg**: Audio soubory

## Output Contract

### Povinné výstupy
1. **manifest.json**: Manifest s metadata běhu
2. **metrics.json**: Metriky výkonu
3. **data/transcripts_recordings.jsonl**: Recording-level transkripty
4. **data/transcripts_calls.jsonl**: Call-level agregované transkripty

### Podmíněné výstupy
- **success.ok**: Pouze při úspěšném běhu
- **error.json**: Pouze při chybách nebo partial success
- **progress.json**: Průběžný progress (vždy)

## Data Formats

### Recording-level JSONL
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
      "temperature": 0.0,
      "language": "cs"
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
  },
  "processing": {
    "asr_settings_hash": "abc123...",
    "transcript_hash": "def456...",
    "processed_at_utc": "2024-08-22T05:43:36Z"
  }
}
```

### Call-level JSONL
```json
{
  "call_id": "20240822_054336_71da9579",
  "duration_s": 458.0,
  "lang": "cs",
  "asr": {
    "provider": "existing",
    "model": "large-v3",
    "device": "cpu",
    "settings": { ... }
  },
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
  },
  "source": {
    "recording_ids": ["20240822_054336_71da9579_p01", "20240822_054336_71da9579_p02"],
    "transcript_source": "existing-json-aggregated"
  }
}
```

## Failure Modes

### 1. Partial Success
- **Status**: `"partial"`
- **Příčina**: Některé nahrávky selhaly při transkripci
- **Akce**: Retry s `--only <failed_ids>`
- **Output**: `error.json` s retry command

### 2. Complete Failure
- **Status**: `"error"`
- **Příčina**: Kritická chyba (konfigurace, externí nástroj)
- **Akce**: Oprava konfigurace, restart
- **Output**: `error.json` s error details

### 3. No Data
- **Status**: `"success"`
- **Příčina**: Žádné nové nahrávky k transkripci
- **Akce**: Normální stav
- **Output**: Prázdné data soubory

## Idempotence

### State Management
- **SQLite**: `state/transcribed.sqlite`
- **Tabulka**: `transcripts`
- **Statusy**: `pending`, `ok`, `failed-transient`, `failed-permanent`

### Hash Tracking
- **asr_settings_hash**: Hash z ASR nastavení
- **transcript_hash**: Hash z textu transkriptu
- **Change detection**: Nové/změněné transkripty

### Idempotent Operations
- ✅ Opakovaný běh neopakuje již zpracované transkripty
- ✅ Partial retry s `--only` funguje
- ✅ State se aktualizuje atomicky

## Režimy práce

### Mode: `run`
- Spustí externí transcriber pro každou nahrávku
- Nahradí placeholdery v `run_cmd`
- Najde výstupní JSON podle `outputs_glob`
- Vhodné pro: Nové transkripce, aktualizace

### Mode: `import`
- Načte existující JSON soubory
- Mapuje na `recording_id` podle názvu
- Nepotřebuje spouštět externí nástroje
- Vhodné pro: Import starých transkriptů

## Performance

### Paralelní zpracování
- **Concurrency**: Konfigurovatelné (default: 2)
- **Threading**: `concurrent.futures.ThreadPoolExecutor`
- **Progress**: Real-time aktualizace

### Metriky
- **Throughput**: Records per minute
- **Runtime**: Celkový čas běhu
- **Counts**: Recordings, transcribed, failed, segments

## Dependencies

### External
- **Předchozí krok**: 01_ingest_spinoco output
- **Externí transcriber**: Whisper nebo jiný ASR nástroj
- **Common library**: ids, state, manifest

### Internal
- **SQLite**: State management
- **JSONL**: Output format
- **YAML**: Configuration
- **Subprocess**: Externí nástroje

## Testing

### Test Scenarios
1. **Happy path**: Import existujících transkriptů → success
2. **Partial fail**: Některé JSONy chybí → partial
3. **Retry**: Retry failed recording → success
4. **Mode run**: Spuštění externího transcriberu

### Test Data
- **Fixtures**: `input/fixtures/`
- **Sample JSON**: Ukázka Whisper výstupu
- **Mock data**: Realistická test data

## Monitoring

### Progress Tracking
- **Phase**: transcription, output, finalize
- **Percentage**: 0-100%
- **ETA**: Odhadovaný čas dokončení
- **Messages**: Popis aktuální aktivity

### Error Reporting
- **Error types**: transcription_error, file_not_found, json_parse_error
- **Retry info**: retry_count, max_retry
- **Context**: recording_id, error message

## Mapování Whisper → Standard

### Vstupní pole (Whisper)
- `transcription.text` → `text`
- `transcription.segments[*].start/end/text` → `segments`
- `metadata.whisper_model` → `asr.model`
- `metadata.device_used` → `asr.device`
- `metadata.beam_size/best_of/temperature` → `asr.settings`

### Výstupní pole (Standard)
- **call_id/recording_id**: Z předchozího kroku
- **asr.provider**: Vždy "existing"
- **metrics**: Vypočtené z dat
- **source**: Metadata o zdroji
- **processing**: Hash pro idempotenci
