# 🎯 Průvodce pro PŘÍŠTĚ

Když budete chtít příště spustit pipeline, použijte tento návod.

---

## ✅ Checklist před spuštěním

- [ ] Aktivovaný virtual environment: `venv\Scripts\activate`
- [ ] V root složce projektu: `cd C:\Users\MCarek\bh-rag\Moje_Python_projekty\spinoco-download`
- [ ] .env soubor existuje (je v .gitignore, ale musí tam být!)

---

## 🚀 Krok za krokem

### 1. Stáhnout nové nahrávky

```powershell
cd steps\ingest_spinoco
..\..\venv\Scripts\python.exe run.py --mode incr --limit 20 --config input\config.yaml
cd ..\..
```

**Výstup:**
```
Celkem načteno XX hovorů ze Spinoco API
...
→ Poznamenejte si RUN_ID z output složky!
```

**Najít RUN_ID:**
```powershell
Get-ChildItem steps\ingest_spinoco\output\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

---

### 2. Transkribovat s monitoringem

```powershell
# Terminal 1: Monitoring
.\watch_all.ps1

# Terminal 2: Transkripce (nahraďte <RUN_ID>!)
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --config input\config.yaml
```

**Co uvidíte:**
- Monitoring: Progress bar, ETA, recent logs
- Terminal 2: "X zpracováno, Y přeskočeno, Z chyb"

**Čekací doba:**
- ~8-10 minut na 2min audio soubor
- Paralelní zpracování 2 souborů najednou

---

### 3. Zkontrolovat výsledky

```powershell
# Najít transcribe run ID
Get-ChildItem steps\transcribe_asr_adapter\output\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# Zobrazit manifest
Get-Content steps\transcribe_asr_adapter\output\runs\<TRANSCRIBE_RUN>\manifest.json | ConvertFrom-Json
```

**Úspěšný výstup:**
```json
{
  "status": "success",
  "counts": {
    "transcribed": 5,
    "skipped": 15,
    "failed": 0
  }
}
```

**`skipped` = normální!** Jsou to nahrávky které nejsou v tomto ingest run.

---

## ⚠️ Když něco nejde

### Problem: Chyba "Audio soubor neexistuje"

**Před opravou:**
```
Transkripce dokončena: 0 zpracováno, 16 chyb  ❌
```

**Po opravě (naše verze):**
```
Transkripce dokončena: 1 zpracováno, 15 přeskočeno, 0 chyb  ✅
```

**Pokud vidíte staré chování:**
→ Ujistěte se že používáte náš upravený kód!

---

### Problem: SQLite state problémy

**Symptomy:**
- Zpracovává soubory které už neexistují
- "X přeskočeno" je divně vysoké

**Řešení:**
```powershell
# Smazat state a začít znovu
Remove-Item "steps\transcribe_asr_adapter\state\transcribed.sqlite*" -Force

# Pak spustit transkripci
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --config input\config.yaml
```

---

### Problem: Monitoring ukazuje starý run

**Řešení:**
```powershell
# Zavřít staré okno, otevřít nové s explicitním run ID
.\watch_all.ps1 -RunId <ACTUAL_RUN_ID>
```

---

## 💡 Pro tips

### Rychlý test (1 soubor)

```powershell
# Použijte limit 1 pro rychlý test
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --limit 1 --config input\config.yaml
```

### Sledování logů bez spouštění

```powershell
# Real-time log stream
.\watch_logs.ps1

# Nebo jen poslední řádky
Get-Content logs\transcriber.log -Tail 20
```

### Rychlejší transkripce (pro testy)

V `spinoco-whisper/.env`:
```env
WHISPER_MODEL=base  # Místo large-v3 = 10x rychlejší!
```

**Warning:** Horší kvalita, jen pro rychlé testy.

---

## 📊 Očekávané výstupy

### Normální úspěch

```
Transkripce dokončena: 3 zpracováno, 13 přeskočeno, 0 chyb
```

✅ **3 transcribed** = nové nahrávky v tomto ingest run  
✅ **13 skipped** = staré nahrávky z minulých běhů  
✅ **0 failed** = žádné skutečné chyby  

### Částečný úspěch

```
Transkripce dokončena: 2 zpracováno, 13 přeskočeno, 1 chyb
```

⚠️ **1 failed** = skutečná chyba (network, corrupt file, atd.)

**Co dělat:**
```powershell
# Retry konkrétního souboru
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run <RUN_ID> --only "<failed_recording_id>" --config input\config.yaml
```

---

## 🎓 Klíčové poznatky

### 1. Skip ≠ Fail

**SKIP** je normální chování když:
- Metadata obsahují více nahrávek než je v audio/ složce
- Používáte různé ingest run_ids
- Spouštíte pipeline opakovaně

**FAIL** je skutečná chyba když:
- Whisper selže
- Network problémy
- Corrupt audio soubor

### 2. OGG soubory se NIKDY nepřesouvají

V novém workflow:
- ✅ OGG zůstávají v `steps/ingest_spinoco/.../audio/`
- ✅ Bezpečné pro retry
- ✅ Žádná ztráta dat

### 3. Monitoring je NUTNÝ

Pro transkripce delší než 5 minut:
- ✅ **VŽDY** použijte `.\watch_all.ps1`
- ✅ Vidíte progress v real-time
- ✅ Víte že to funguje, nejen čekáte

### 4. Config cesty = relativní!

```powershell
# ✅ VŽDY
--config input\config.yaml

# ❌ NIKDY
--config steps\transcribe_asr_adapter\input\config.yaml
```

---

## 📁 Strukturované commandy

### Pro kopírování do dokumentů

```powershell
# === FULL PIPELINE RUN ===

# Step 1: Ingest
cd steps\ingest_spinoco
..\..\venv\Scripts\python.exe run.py --mode incr --limit 20 --config input\config.yaml
cd ..\..
$INGEST_RUN = "<RUN_ID_FROM_OUTPUT>"

# Step 2: Transcribe (2 terminals)
.\watch_all.ps1  # Terminal 1
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run $INGEST_RUN --config input\config.yaml  # Terminal 2

# Step 3: Check results
$TRANSCRIBE_RUN = (Get-ChildItem steps\transcribe_asr_adapter\output\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
Get-Content steps\transcribe_asr_adapter\output\runs\$TRANSCRIBE_RUN\manifest.json | ConvertFrom-Json
```

---

**Příště to bude hladké! 🚀✨**
