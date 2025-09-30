# 🎤 Quick Start - Transkripce s Monitoringem

## 🚀 Nejjednodušší způsob (DOPORUČENO)

### 1. Spusťte master skript
```powershell
.\run_with_monitoring.ps1
```

To automaticky:
- ✅ Otevře monitoring okno s progress barem
- ✅ (Volitelně) Otevře log okno  
- ✅ Spustí transkripci
- ✅ Ukáže progress v real-time

---

## 🔧 Manuální způsob

### Okno 1: Transkripce
```powershell
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode incr --input-run 01K6CPN9XFNSRPCCDZ98A9V2EH --limit 1 --config steps\transcribe_asr_adapter\input\config.yaml
```

### Okno 2: Monitoring
```powershell
.\watch_progress.ps1
```

### Okno 3 (volitelně): Logy
```powershell
.\watch_logs.ps1
```

---

## 📋 Parametry

### Input Run ID
```powershell
# Najdi dostupné runs
Get-ChildItem steps\ingest_spinoco\output\runs -Directory | Select-Object Name, LastWriteTime | Sort-Object LastWriteTime -Descending

# Použij konkrétní run
.\run_with_monitoring.ps1 -InputRun "01K6CPN9XFNSRPCCDZ98A9V2EH"
```

### Limit počtu nahrávek
```powershell
# Zpracuj jen 1 nahrávku (pro test)
.\run_with_monitoring.ps1 -Limit 1

# Zpracuj 5 nahrávek
.\run_with_monitoring.ps1 -Limit 5

# Zpracuj všechny
.\run_with_monitoring.ps1 -Limit 999999
```

### Režim běhu
```powershell
# Incrementální (výchozí) - zpracuje jen nové
.\run_with_monitoring.ps1 -Mode incr

# Backfill - zpracuje i staré
.\run_with_monitoring.ps1 -Mode backfill
```

---

## ⏱️ Jak dlouho to trvá?

| Nahrávek | Audio délka | CPU Time | s GPU |
|----------|-------------|----------|-------|
| 1        | 2 min       | ~8 min   | ~1 min |
| 1        | 5 min       | ~15 min  | ~2 min |
| 5        | 2 min každá | ~40 min  | ~5 min |

**Progress bar vám ukáže přesný odhad!** 📊

---

## 🎯 Co vidíte v monitoring okně

```
=== 📊 TRANSCRIPTION PROGRESS ===
Run ID: 01K6CRXRE9WWRCVZ8W2KYCXQNP
Time: 09:15:30

Phase: transcription
[████████████████░░░░░░░░░░░░] 65.0%
Status: Zpracováno 13/20 nahrávek (OK: 12, FAIL: 1)
Updated: 2025-09-30T09:15:28Z

ETA: ~8 minutes

--- 📝 Recent Logs ---
[09:14:12] INFO - Začínám přepis souboru: audio_003.ogg
[09:14:12] INFO - 🎤 Audio: 3.2 MB, model: large-v3, device: cpu
[09:14:12] INFO - ⏳ Transkripce běží... (může trvat několik minut)
[09:15:28] INFO - Přepis dokončen: audio_003.ogg
[09:15:28] INFO - Přepis uložen: transcriptions/audio_003_transcription.json
```

---

## 🚨 Troubleshooting

### "Nothing is happening"
1. Zkontrolujte logy: `.\watch_logs.ps1`
2. Zkontrolujte CPU: `Get-Process python`
3. Whisper loading trvá 10-20 sekund - buďte trpěliví

### "It's too slow"
Použijte rychlejší model v `spinoco-whisper/.env`:
```env
WHISPER_MODEL=base  # Místo large-v3
```

### "Error in logs"
1. Přečtěte chybovou zprávu v `.\watch_logs.ps1`
2. Zkontrolujte `steps/transcribe_asr_adapter/output/runs/<RUN_ID>/error.json`
3. Opravte problém a spusťte retry:
```powershell
venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --input-run 01K6CPN9XFNSRPCCDZ98A9V2EH --only "failed_recording_id"
```

---

## 📂 Výstupy

Po dokončení najdete:

### Transkripty
```
steps/transcribe_asr_adapter/output/runs/<RUN_ID>/data/
├── transcripts_recordings.jsonl  # Recording-level
└── transcripts_calls.jsonl       # Call-level (agregované)
```

### Metriky
```
steps/transcribe_asr_adapter/output/runs/<RUN_ID>/
├── manifest.json      # Metadata běhu
├── metrics.json       # Statistiky
└── success.ok         # Success marker
```

---

## 💡 Pro další zpracování

Po transkripci můžete spustit anonymizaci:
```powershell
venv\Scripts\python.exe steps\anonymize\run.py --input-run <TRANSCRIBE_RUN_ID> --config steps\anonymize\input\config.yaml
```

---

**Více informací: [`MONITORING.md`](MONITORING.md)**

**Happy transcribing! 🎙️✨**
