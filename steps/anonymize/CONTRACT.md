# CONTRACT.md - steps/03_anonymize

## Input Contract

### Povinné vstupy
- **--input-run**: Step run ID předchozího kroku (02_transcribe_asr_adapter)
- **Konfigurace**: `input/config.yaml` nebo `--config`

### Volitelné vstupy
- **--only**: Seznam call_ids pro retry
- **--limit**: Omezení počtu hovorů
- **--mode**: backfill/incr/dry režim

### Vstupní soubory (z předchozího kroku)
- **manifest.json**: Manifest z předchozího kroku
- **transcripts_recordings.jsonl**: Recording-level transkripty
- **transcripts_calls.jsonl**: Call-level agregované transkripty

## Output Contract

### Povinné výstupy
1. **manifest.json**: Manifest s metadata běhu
2. **metrics.json**: Metriky anonymizace
3. **data/transcripts_recordings_redacted.jsonl**: Redigované recording-level transkripty
4. **data/transcripts_calls_redacted.jsonl**: Redigované call-level transkripty

### Podmíněné výstupy
- **success.ok**: Pouze při úspěšném běhu
- **error.json**: Pouze při chybách nebo partial success
- **progress.json**: Průběžný progress (vždy)
- **data/vault_map/<call_id>.json**: Mapování tag → salted hash (pokud povoleno)

## Data Formats

### Recording-level redigovaný JSONL
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
    "settings": { ... }
  },
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Dobrý den, volám vám z čísla @PHONE_1"
    },
    {
      "start": 5.2,
      "end": 10.5,
      "text": "Můj email je @EMAIL_1 a IBAN je @IBAN_1"
    }
  ],
  "text": "Dobrý den, volám vám z čísla @PHONE_1. Můj email je @EMAIL_1 a IBAN je @IBAN_1.",
  "pii_stats": {
    "total_replacements": 3,
    "by_type": {
      "PHONE": 1,
      "EMAIL": 1,
      "IBAN": 1
    }
  },
  "source": {
    "audio_path": "audio/20240822_054336_71da9579_p01.ogg",
    "transcript_source": "existing-json"
  },
  "processing": {
    "asr_settings_hash": "abc123",
    "transcript_hash": "def456",
    "processed_at_utc": "2024-08-22T05:43:36Z"
  }
}
```

### Call-level redigovaný JSONL
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
      "text": "Dobrý den, volám vám z čísla @PHONE_1",
      "recording_id": "20240822_054336_71da9579_p01"
    },
    {
      "start": 5.2,
      "end": 10.5,
      "text": "Můj email je @EMAIL_1 a IBAN je @IBAN_1",
      "recording_id": "20240822_054336_71da9579_p01"
    }
  ],
  "text": "[--- 20240822_054336_71da9579_p01 ---]\n\nDobrý den, volám vám z čísla @PHONE_1...",
  "pii_stats": {
    "total_replacements": 5,
    "by_type": {
      "PHONE": 2,
      "EMAIL": 2,
      "IBAN": 1
    }
  },
  "source": {
    "recording_ids": ["20240822_054336_71da9579_p01", "20240822_054336_71da9579_p02"],
    "transcript_source": "existing-json-aggregated"
  },
  "processing": {
    "asr_settings_hash": "abc123",
    "transcript_hash": "ghi789",
    "processed_at_utc": "2024-08-22T05:43:36Z"
  }
}
```

### Vault Map JSON
```json
{
  "@PHONE_1": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
  "@EMAIL_1": "f6e5d4c3b2a1098765432109876543210987654321fedcba0987654321fedcba",
  "@IBAN_1": "9z8y7x6w5v4u3210987654321098765432109876543210zyxwvu0987654321"
}
```

## Failure Modes

### 1. Partial Success
- **Status**: `"partial"`
- **Příčina**: Některé hovory selhaly při redigování
- **Akce**: Retry s `--only <failed_call_ids>`
- **Output**: `error.json` s retry command

### 2. Complete Failure
- **Status**: `"error"`
- **Příčina**: Kritická chyba (konfigurace, I/O)
- **Akce**: Oprava konfigurace, restart
- **Output**: `error.json` s error details

### 3. No Data
- **Status**: `"success"`
- **Příčina**: Žádné hovory k redigování
- **Akce**: Normální stav
- **Output**: Prázdné data soubory

## Idempotence

### Deterministic Redigování
- **Regex patterns**: Deterministické výsledky
- **Tag ordering**: Per call deterministické
- **Vault map**: Přepíše se při změnách
- **No state DB**: Redigování je čistě funkční

### Idempotent Operations
- ✅ Opakovaný běh vytvoří identické výsledky
- ✅ Stejné PII hodnoty dostanou stejné tagy
- ✅ Vault map je konzistentní s redigovaným textem

## PII Detection Rules

### Telefonní čísla
- **Pattern**: `(\+?420[\s-]?)?(\d[\s-]?){9,11}`
- **Examples**: `+420 123 456 789`, `777 888 999`, `123456789`
- **Replacement**: `@PHONE_1`, `@PHONE_2`, atd.
- **Limitations**: Může chybět některé formáty

### Email adresy
- **Pattern**: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`
- **Examples**: `jan.novak@example.com`, `info@firma.cz`
- **Replacement**: `@EMAIL_1`, `@EMAIL_2`, atd.
- **Limitations**: Může chybět některé domény

### IBAN
- **Pattern**: `\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b`
- **Examples**: `CZ65 0800 0000 1920 0014 5399`
- **Replacement**: `@IBAN_1`, `@IBAN_2`, atd.
- **Limitations**: Může chybět některé formáty

### Adresy (vypnuto)
- **Pattern**: `\b\d+\s+[A-Za-záčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\s]+(?:ulice|třída|náměstí|nábřeží)\b`
- **Status**: Vypnuto v konfiguraci
- **Plán**: Rozšíření o NER model

## Performance

### Paralelní zpracování
- **Concurrency**: Konfigurovatelné (default: 2)
- **Threading**: `concurrent.futures.ThreadPoolExecutor`
- **Progress**: Real-time aktualizace

### Metriky
- **Throughput**: Calls per minute
- **Runtime**: Celkový čas běhu
- **PII counts**: Počty náhrad podle typu

## Dependencies

### External
- **Předchozí krok**: 02_transcribe_asr_adapter output
- **Common library**: ids, manifest

### Internal
- **JSONL**: Input/output format
- **YAML**: Configuration
- **Regex**: PII detection
- **Hashlib**: Salted hash pro vault map

## Testing

### Test Scenarios
1. **Happy path**: Redigování hovorů s PII → success
2. **Partial fail**: Některé hovory selžou → partial
3. **Retry**: Retry failed calls → success
4. **Idempotence**: Stejné vstupy → identické výsledky

### Test Data
- **Fixtures**: `input/fixtures/`
- **Sample transcripts**: Ukázky s PII
- **Mock data**: Realistická test data

## Monitoring

### Progress Tracking
- **Phase**: anonymization, output, finalize
- **Percentage**: 0-100%
- **ETA**: Odhadovaný čas dokončení
- **Messages**: Popis aktuální aktivity

### Error Reporting
- **Error types**: anonymization_error, io_error, config_error
- **Context**: call_id, error message
- **Retry info**: Retry command pro opravu

## Mapování Input → Output

### Vstupní soubory
- **transcripts_recordings.jsonl**: Recording-level transkripty
- **transcripts_calls.jsonl**: Call-level agregované transkripty

### Výstupní soubory
- **transcripts_recordings_redacted.jsonl**: Redigované recordingy
- **transcripts_calls_redacted.jsonl**: Redigované calls
- **vault_map/<call_id>.json**: Mapování tag → salted hash

### Transformace
- **PII → Tags**: Deterministic replacement
- **PII stats**: Přidány do každého záznamu
- **Vault map**: Audit trail pro PII hodnoty
- **Manifest**: Aktualizován s PII metriky

## Limity a plány

### Současné limity
- **Regex-based**: Může chybět některé PII varianty
- **Adresy vypnuty**: Plánuje se NER rozšíření
- **Jména**: Nejsou detekována (plánuje se NER)

### Plánované rozšíření
- **NER model**: Pro detekci jmen a adres
- **Kontextová analýza**: Lepší PII detekce
- **Custom patterns**: Uživatelské regex vzory
- **Audit log**: Detailní logování PII náhrad
