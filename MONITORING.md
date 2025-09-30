# 📊 Monitoring Guide - Sledování Transkripce

Transkripce trvá dlouho (8-15 minut na audio). Zde je návod jak sledovat progress.

## 🎯 Quick Start

### 1. Spusťte transkripci
```powershell
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run 01K6CPN9XFNSRPCCDZ98A9V2EH --limit 1 --config steps\transcribe_asr_adapter\input\config.yaml
```

### 2. V dalším okně sledujte progress
```powershell
.\watch_progress.ps1
```

NEBO sledujte logy:
```powershell
.\watch_logs.ps1
```

---

## 📊 Monitoring nástroje

### ✅ `watch_progress.ps1` - Progress Dashboard
**Nejlepší pro vizuální přehled**

```powershell
.\watch_progress.ps1
```

Co zobrazuje:
- 📊 Progress bar s % dokončení
- ⏱️ Aktuální fáze (transcription, output, atd.)
- 💬 Status zpráva (kolik nahrávek zpracováno)
- ⏳ ETA (odhadovaný zbývající čas)
- 📝 Poslední 5 log řádků

Aktualizuje se každé 2 sekundy.

### ✅ `watch_logs.ps1` - Real-time Logy
**Nejlepší pro debugging**

```powershell
.\watch_logs.ps1
```

Co zobrazuje:
- 📝 Real-time stream všech logů
- 🎨 Barevné rozlišení (INFO/WARNING/ERROR)
- 🔔 Beep při chybě
- ⏱️ Timestamp každé zprávy

### ✅ Manuální sledování progress.json
```powershell
# Najdi nejnovější run
$runId = Get-ChildItem steps\transcribe_asr_adapter\output\runs -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name

# Sleduj progress
while ($true) {
    Clear-Host
    Get-Content "steps\transcribe_asr_adapter\output\runs\$runId\progress.json" | ConvertFrom-Json | Format-List
    Start-Sleep -Seconds 2
}
```

### ✅ Sledování logů tail style
```powershell
Get-Content logs\transcriber.log -Wait -Tail 20
```

---

## 🕐 Typické časy transkripce

| Audio délka | Whisper model | CPU | GPU | 
|-------------|---------------|-----|-----|
| 2 min       | large-v3     | 8 min | 1 min |
| 5 min       | large-v3     | 15 min | 2 min |
| 10 min      | large-v3     | 30 min | 4 min |

**Pravidlo**: Na CPU je to ~3-4x delší než délka audia

---

## 🎬 Co vidíte během transkripce

### Fáze 1: Inicializace
```
[08:53:43] INFO - Whisper device nastaven na: cpu
[08:53:43] INFO - Načítám Whisper model: large-v3
[08:53:59] INFO - Whisper model úspěšně načten
```
⏱️ Trvá: ~10-20 sekund

### Fáze 2: Transkripce
```
[08:54:00] INFO - Začínám přepis souboru: audio.ogg
[08:54:00] INFO - 🎤 Audio: 5.2 MB, model: large-v3, device: cpu
[08:54:00] INFO - ⏳ Transkripce běží... (může trvat několik minut)
```

**S `verbose=True` uvidíte v terminálu:**
```
[00:00.000 --> 00:05.200] Dobrý den, technická podpora
[00:05.200 --> 00:08.400] Volám ohledně problému s kotlem
...
```
⏱️ Trvá: 3-4x délky audia na CPU

### Fáze 3: Dokončení
```
[09:06:40] INFO - Přepis dokončen: audio.ogg
[09:06:40] INFO - Přepis uložen: data\transcriptions\audio_transcription.json
[09:06:40] INFO - Soubor přesunut: audio.ogg -> processed/
```
⏱️ Trvá: <1 sekunda

---

## 🚨 Co dělat když to vypadá zaseknuté

### 1. Zkontrolujte logy
```powershell
Get-Content logs\transcriber.log -Tail 5
```

### 2. Zkontrolujte CPU/RAM
```powershell
Get-Process python | Select-Object CPU, WorkingSet, ProcessName
```

Whisper large-v3 potřebuje:
- CPU: 50-100% jednoho jádra
- RAM: 4-8 GB

### 3. Pokud nic neběží > 5 minut
Možná proces zamrzl. Zkuste:
- Ctrl+C pro zastavení
- Zkontrolujte error logy
- Spusťte znovu

---

## 💡 Pro rychlejší transkripci

### Použijte menší model
V `spinoco-whisper/.env`:
```env
WHISPER_MODEL=base  # Místo large-v3
```

Rychlost: **10x rychlejší**, ale horší kvalita

### Použijte GPU
Pokud máte NVIDIA GPU:
```env
WHISPER_DEVICE=cuda
```

Rychlost: **3-5x rychlejší**

---

## 📁 Kde najít výstupy

### Transkripty
```
spinoco-whisper/data/transcriptions/
└── <recording_id>_transcription.json
```

### Zpracované audio
```
spinoco-whisper/data/processed/
└── <recording_id>.ogg
```

### Progress a metriky
```
steps/transcribe_asr_adapter/output/runs/<RUN_ID>/
├── progress.json      # Real-time progress
├── manifest.json      # Final manifest
├── metrics.json       # Statistiky
└── success.ok         # Success marker
```

---

## 🎓 Tipy

1. **Nechte běžet na pozadí** - Otevřete monitoring v druhém terminálu
2. **Nepanikařte** - 8-12 minut je normální pro 2min audio
3. **Sledujte CPU** - Pokud CPU=0%, něco je špatně
4. **Verbose mode** - `verbose=True` v transcriberu pro detailní progress

---

**Happy transcribing! 🎤✨**
