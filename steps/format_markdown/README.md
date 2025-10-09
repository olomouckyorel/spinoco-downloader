# steps/04_format_markdown

Krok 04: Převod anonymizovaných transkriptů do lidsky čitelného Markdown formátu.

## 🎯 Účel

Převádí anonymizované JSONL transkripty do krásně formátovaných Markdown souborů které jsou:
- ✅ Čitelné v editoru i GitHubu
- ✅ Obsahují časování v přehledném formátu
- ✅ Zobrazují metadata (délka, model, PII stats)
- ✅ Připravené k exportu do HTML/PDF

## 🚀 Použití

### Základní běh

```powershell
venv\Scripts\python.exe steps\format_markdown\run.py --input-run <ANONYMIZE_RUN_ID> --config input\config.yaml
```

### S limitem (test)

```powershell
venv\Scripts\python.exe steps\format_markdown\run.py --input-run <ANONYMIZE_RUN_ID> --limit 5 --config input\config.yaml
```

## 📊 Vstup

### Očekávané soubory

```
steps/anonymize/output/runs/<RUN_ID>/data/
├── transcripts_calls_redacted.jsonl       ← INPUT
└── vault_map/                             (používá se pro referenci)
```

## 📝 Výstup

### Markdown soubory

```
steps/format_markdown/output/runs/<RUN_ID>/data/markdown/
├── 21951d01-8fb0-11f0-9fcd-0763f6d52bb8.md
├── <call_id_2>.md
└── <call_id_3>.md
```

### Příklad Markdown formátu

```markdown
# Hovor 21951d01-8fb0-11f0-9fcd-0763f6d52bb8

## 📊 Metadata

- **Délka:** 00:03:49
- **Jazyk:** cs
- **Model:** large-v3
- **PII nahrazeno:** 0 (žádné citlivé údaje)
- **Segmentů:** 61

## 📝 Přepis

**[00:00:00]** Dobrý den, já najíždím peletářk do tady Pelko, teď jsem skalibroval podavač...

**[00:00:26]** No tak jsi ten vážil kolik? Nějak 400 gramů?

**[00:00:33]** Eee, 3200.

**[00:00:35]** 3200, no tady jsi zadal 400-200 gramů?

...

---

*Vygenerováno z anonymizovaného transkriptu*
```

## ⚙️ Konfigurace

V `input/config.yaml`:

```yaml
format:
  include_metadata: true      # Zahrnout metadata sekci
  time_format: "HH:MM:SS"    # Formát časování

input:
  calls_file: "transcripts_calls_redacted.jsonl"

io:
  input_run_root: "../anonymize/output/runs"
```

## 🎯 Features

- ✅ **Časování:** Každý segment má HH:MM:SS timestamp
- ✅ **Metadata:** Délka, model, PII statistiky
- ✅ **Formátování:** Bold pro timestamps, čitelné odstavce
- ✅ **Rychlost:** ~1000 hovorů/sekunda (jen formátování textu!)
- ✅ **UTF-8:** Plná podpora češtiny

## 📊 Výstupní manifest

```json
{
  "schema": "bh.v1.transcripts_markdown",
  "step_id": "04_format_markdown",
  "status": "success",
  "counts": {
    "calls": 10,
    "formatted": 10,
    "failed": 0
  }
}
```

## 🔗 Pipeline integrace

```
Step 3: Anonymize
  └─ transcripts_calls_redacted.jsonl
          ↓
Step 4: Format Markdown  ← YOU ARE HERE
  └─ markdown/*.md (čitelné pro člověka!)
```

## 💡 Use cases

### Manuální review

- Otevřete `.md` soubor v editoru
- Čtěte přepis s časováním
- PII jsou bezpečně nahrazeny tagy

### Export do PDF

```powershell
# Použijte pandoc nebo jiný tool
pandoc call_id.md -o call_id.pdf
```

### GitHub review

- Commitněte `.md` soubory
- Čitelné přímo na GitHubu
- Diffy jsou přehledné

## ⏱️ Performance

- **Rychlost:** ~1000 hovorů/sekunda
- **Paměť:** Minimální (<100 MB)
- **Čas:** <1 sekunda pro většinu běhů

---

**Rychlý a jednoduchý krok pro lidskou čitelnost!** 📖✨




