# 🚀 Quick Reference - Spinoco Pipeline

Rychlá nápověda pro denní použití. Kopírujte příkazy a nahraďte `<RUN_ID>`.

---

## ⚡ Nejpoužívanější příkazy

### 1️⃣ Stáhnout nové nahrávky ze Spinoco

```powershell
cd steps\ingest_spinoco
..\..\venv\Scripts\python.exe run.py --mode incr --limit 20 --config input\config.yaml
cd ..\..
```

**Výstup:** RUN_ID (např. `01K6D1GKWDC2Q3XH14JA0WM6VB`)

---

### 2️⃣ Transkribovat nahrávky (S MONITORINGEM!)

```powershell
# Terminal 1: Monitoring
.\watch_all.ps1

# Terminal 2: Transkripce
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <INGEST_RUN_ID> --config input\config.yaml
```

**Čeká:** ~5-10 minut na soubor (3-4x délky audia)

---

### 3️⃣ Zkontrolovat výsledky

```powershell
# Najdi nejnovější transcribe run
Get-ChildItem steps\transcribe_asr_adapter\output\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# Zobraz manifest
Get-Content steps\transcribe_asr_adapter\output\runs\<RUN_ID>\manifest.json | ConvertFrom-Json | Select-Object status, counts
```

---

## 🔧 Troubleshooting příkazy

### Smazat SQLite state (fresh start)

```powershell
Remove-Item "steps\transcribe_asr_adapter\state\transcribed.sqlite*" -Force
```

### Zkontrolovat poslední logy

```powershell
Get-Content logs\transcriber.log -Tail 10
```

### Sledovat logy v real-time

```powershell
.\watch_logs.ps1
```

### Najít všechny run IDs

```powershell
# Ingest runs
Get-ChildItem steps\ingest_spinoco\output\runs -Directory | Select-Object Name, LastWriteTime | Sort-Object LastWriteTime -Descending

# Transcribe runs
Get-ChildItem steps\transcribe_asr_adapter\output\runs -Directory | Select-Object Name, LastWriteTime | Sort-Object LastWriteTime -Descending
```

---

## 📊 Očekávané výstupy

### Úspěšný ingest

```
Celkem načteno 16 hovorů ze Spinoco API
Hovor XXX: nalezeno 1 nahrávek
...
→ RUN_ID: 01K6D1GKWDC2Q3XH14JA0WM6VB
→ Staženo: 1-5 OGG souborů (záleží na novinkách)
```

### Úspěšná transkripce

```
Zpracováno 16/16 nahrávek (OK: 1, SKIP: 15, FAIL: 0)
Transkripce dokončena: 1 zpracováno, 15 přeskočeno, 0 chyb
→ RUN_ID: 01K6D2SAAVS5XQ11E6867V2NJ9
→ Výstup: transcripts_recordings.jsonl, transcripts_calls.jsonl
```

**SKIP není chyba!** = nahrávky nebyly v tomto ingest run_id.

---

## ⚠️ Normální varování (ignorujte)

```
⚠️ Neočekávaný formát názvu souboru: 3a243241-8fb0-11f0-9fcd-0763f6d52bb8.ogg
```

**Proč:** Spinoco používá UUID, ne datový formát  
**Je to problém?** NE - metadata jsou v metadata_recordings.jsonl  
**Transkripce funguje?** ANO - normálně  

---

## 🎯 Běžné use cases

### Use case 1: Denní stahování + transkripce

```powershell
# 1. Stáhnout nové hovory
cd steps\ingest_spinoco
..\..\venv\Scripts\python.exe run.py --mode incr --limit 50 --config input\config.yaml
cd ..\..
# → Poznamenat RUN_ID

# 2. Transkribovat (s monitoringem)
.\watch_all.ps1  # Terminal 1
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --config input\config.yaml  # Terminal 2
```

### Use case 2: Zpracovat starší data

```powershell
# Použít existující ingest run
$OLD_RUN = "01K6CPN9XFNSRPCCDZ98A9V2EH"

venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run $OLD_RUN --config input\config.yaml
```

### Use case 3: Retry konkrétního souboru

```powershell
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --only "recording_id_XXX" --config input\config.yaml
```

---

## 🕐 Časování

| Krok | Typický čas |
|------|-------------|
| Ingest 20 hovorů | ~2-5 min |
| Whisper loading | ~10-20 sec |
| Transcribe 1 soubor (2 min audio) | ~8 min |
| Transcribe 5 souborů (parallel) | ~20-30 min |
| Celý pipeline (stažení + transkripce 5) | ~30-40 min |

---

## 💾 Kde jsou data

### OGG soubory (audio)
```
steps/ingest_spinoco/output/runs/<RUN_ID>/data/audio/*.ogg
```
✅ **Zůstávají tam napořád!**

### Transkripty
```
steps/transcribe_asr_adapter/output/runs/<RUN_ID>/data/
├── transcripts_recordings.jsonl
└── transcripts_calls.jsonl
```

### Logy
```
logs/transcriber.log  (JSON formát)
```

---

## 🚨 Když něco nejde

### 1. Zkontrolujte config cestu
```powershell
# ✅ SPRÁVNĚ
--config input\config.yaml

# ❌ ŠPATNĚ
--config steps\transcribe_asr_adapter\input\config.yaml
```

### 2. Zkontrolujte logy
```powershell
Get-Content logs\transcriber.log -Tail 20
```

### 3. Smazat state a zkusit znovu
```powershell
Remove-Item "steps\transcribe_asr_adapter\state\transcribed.sqlite*" -Force
```

### 4. Sledovat monitoring
```powershell
.\watch_all.ps1 -RunId <ACTUAL_RUN_ID>
```

---

**Happy processing! 🎤✨**

**Další dokumentace:**
- [README.md](README.md) - Hlavní přehled
- [START_TRANSCRIPTION.md](START_TRANSCRIPTION.md) - Quick start
- [MONITORING.md](MONITORING.md) - Monitoring guide
- [DATA_FLOW.md](DATA_FLOW.md) - Data flow
