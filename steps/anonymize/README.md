# steps/03_anonymize

Krok 03: Redigování PII z transkriptů s deterministickým tagováním.

## Přehled

Tento krok zajišťuje:
- ✅ **Redigování PII** z transkriptů pomocí regex-based detekce
- ✅ **Deterministické tagování** per call (@PHONE_1, @EMAIL_1, atd.)
- ✅ **Vault map** s salted hash pro audit (lokálně, mimo repo)
- ✅ **Recording-level a call-level** redigované výstupy
- ✅ **Manifest/metrics** pro traceability
- ✅ **Silver → Gold** transformace

## CLI

```bash
python run.py [OPTIONS]

Options:
  --mode {backfill,incr,dry}     Režim běhu (default: incr)
  --input-run <STEP_RUN_ID>      Step run ID předchozího kroku (povinné)
  --run-id <str>                 Step run ID (jinak vygeneruje ULID)
  --only <call_ids>              Cílený retry (comma-separated)
  --limit <int>                  Omez počet hovorů
  --config <path>                Konfigurační soubor
```

## Příklady použití

### Redigování všech hovorů
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ
```

### Redigování konkrétních hovorů
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --only "20240822_054336_71da9579,20240822_063016_71da9579"
```

### Test s limitem
```bash
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --limit 5
```

## Konfigurace

Kopíruj `input/config.example.yaml` do `config.yaml` a uprav:

```yaml
anonymize:
  tags_prefix: "@"
  redact_phone: true
  redact_email: true
  redact_iban: true
  redact_address: false          # začneme hard PII; adresy přidáme později
  keep_call_id: true             # call_id/recording_id NEMAŽEME (nejsou PII)
  make_vault_map: true           # uložit lokální mapu náhrad (salted hash)

io:
  input_run_root: "../transcribe_asr_adapter/output/runs"
  max_parallel: 2
```

## PII Detekce

### Podporované typy PII

**Telefonní čísla:**
- Vzory: `(\+?420[\s-]?)?(\d[\s-]?){9,11}`
- Příklady: `+420 123 456 789`, `777 888 999`, `123456789`
- Náhrada: `@PHONE_1`, `@PHONE_2`, atd.

**Email adresy:**
- Vzory: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`
- Příklady: `jan.novak@example.com`, `info@firma.cz`
- Náhrada: `@EMAIL_1`, `@EMAIL_2`, atd.

**IBAN:**
- Vzory: `\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b`
- Příklady: `CZ65 0800 0000 1920 0014 5399`
- Náhrada: `@IBAN_1`, `@IBAN_2`, atd.

**Adresy (vypnuto):**
- Základní regex pro české adresy
- Plánuje se rozšíření o NER (Named Entity Recognition)

### Deterministic Tagging

**Per Call:**
- První nalezený telefon → `@PHONE_1`
- Druhý nalezený telefon → `@PHONE_2`
- Stejné pořadí pro emaily a IBAN

**Konzistence:**
- Stejné PII hodnoty dostanou stejný tag
- Tagy jsou deterministické napříč běhy
- Vault map obsahuje salted hash pro audit

## Výstupy

### Struktura výstupů
```
output/runs/<STEP_RUN_ID>/
├── manifest.json              # Manifest s metadata běhu
├── metrics.json               # Metriky anonymizace
├── progress.json              # Průběžný progress
├── success.ok                 # Úspěšný běh
├── error.json                 # Chyby (pokud jsou)
└── data/
    ├── transcripts_recordings_redacted.jsonl
    ├── transcripts_calls_redacted.jsonl
    └── vault_map/
        ├── <call_id>.json     # Mapování tag → salted hash
        └── ...
```

### Recording-level redigovaný formát
```json
{
  "call_id": "20240822_054336_71da9579",
  "recording_id": "20240822_054336_71da9579_p01",
  "duration_s": 229.0,
  "lang": "cs",
  "asr": { ... },
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
  "source": { ... },
  "processing": { ... }
}
```

### Call-level redigovaný formát
```json
{
  "call_id": "20240822_054336_71da9579",
  "duration_s": 458.0,
  "lang": "cs",
  "asr": { ... },
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Dobrý den, volám vám z čísla @PHONE_1",
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
  "source": { ... },
  "processing": { ... }
}
```

### Vault Map formát
```json
{
  "@PHONE_1": "a1b2c3d4e5f6...",
  "@EMAIL_1": "f6e5d4c3b2a1...",
  "@IBAN_1": "9z8y7x6w5v4u3..."
}
```

## Error Handling

### Partial Success
Pokud některé hovory selžou:
- Status: `"partial"`
- `error.json` obsahuje seznam failed call_ids
- Retry command pro opravu

### Retry Logika
- Deterministic redigování → idempotentní operace
- Opakovaný běh vytvoří identické výsledky
- Vault map se přepíše při změnách

### State Management
- **Žádná DB**: Redigování je deterministické
- **Vault map**: Lokální soubory pro audit
- **Change detection**: Hash-based kontrola v testech

## Metriky

### PII Statistiky
- **total_replacements**: Celkový počet náhrad
- **pii_counts**: Počty podle typu (PHONE, EMAIL, IBAN)
- **calls_redacted**: Počet úspěšně redigovaných hovorů
- **recordings_total**: Celkový počet recordingů

### Performance
- **runtime_s**: Celkový čas běhu
- **throughput_calls_per_min**: Propustnost hovorů za minutu
- **Paralelní zpracování**: Konfigurovatelné (default: 2)

## Testování

```bash
# Test s fixtures
python run.py --input-run test_run --config input/config.example.yaml

# Test s limitem
python run.py --input-run 01J9ZC3AC9V2J9FZK2C3R8K9TQ --limit 3
```

## Dependencies

- **common/lib**: ids, manifest
- **PyYAML**: Konfigurace
- **concurrent.futures**: Paralelní zpracování
- **hashlib**: Salted hash pro vault map
- **re**: Regex patterny pro PII detekci

## Troubleshooting

### Časté problémy

1. **Input manifest neexistuje**: Zkontroluj `--input-run`
2. **Transcript soubory chybí**: Spusť předchozí krok
3. **PII nedetekováno**: Zkontroluj regex patterny
4. **Partial success**: Některé hovory selhaly - použij retry

### Logy
- Progress: `output/runs/<STEP_RUN_ID>/progress.json`
- Chyby: `output/runs/<STEP_RUN_ID>/error.json`
- Vault map: `output/runs/<STEP_RUN_ID>/data/vault_map/`

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

## Mapování Input → Output

### Vstupní transkripty
- **transcripts_recordings.jsonl**: Recording-level transkripty
- **transcripts_calls.jsonl**: Call-level agregované transkripty

### Výstupní redigované transkripty
- **transcripts_recordings_redacted.jsonl**: Redigované recordingy
- **transcripts_calls_redacted.jsonl**: Redigované calls
- **vault_map/**: Mapování tag → salted hash

### Transformace
- **PII → Tags**: Deterministic replacement
- **PII stats**: Přidány do každého záznamu
- **Vault map**: Audit trail pro PII hodnoty
- **Manifest**: Aktualizován s PII metriky
