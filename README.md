# Spinoco Download

Profesionální Python aplikace pro stahování hovorů ze Spinoco API a jejich nahrávání na SharePoint.

## 🎯 Funkce

- **Automatické stahování hovorů** ze Spinoco pomocí Call and Chat Transcription API
- **Upload na SharePoint** s podporou složkové struktury
- **Stahování nahrávek** v .ogg formátu
- **Stahování transkriptů** v JSON formátu
- **Metadata export** s detailními informacemi o hovorech
- **Synchronizační stav** - pokračování od posledního běhu
- **Paralelní zpracování** s konfigurovatelným limitem
- **Strukturované logování** s barevným výstupem
- **Template systém** pro názvy souborů (inspirovaný oficiálním Spinoco connectorem)

## 📁 Struktura projektu

```
spinoco-download/
├── src/                          # Zdrojové kódy
│   ├── __init__.py
│   ├── config.py                 # Konfigurace aplikace
│   ├── logger.py                 # Logging systém
│   ├── spinoco_client.py         # Spinoco API klient
│   ├── sharepoint_client.py      # SharePoint klient
│   └── main.py                   # Hlavní aplikace
├── config/                       # Konfigurační soubory
│   ├── env.example               # Příklad konfigurace
│   └── sync_state.json          # Stav synchronizace (auto-generovaný)
├── logs/                         # Log soubory
├── tests/                        # Testy
├── docs/                         # Dokumentace
├── requirements.txt              # Python závislosti
├── .gitignore                   # Git ignore
└── README.md                    # Tato dokumentace
```

## 🚀 Rychlý start

### 1. Naklonuj projekt

```bash
git clone https://github.com/your-username/spinoco-download.git
cd spinoco-download
```

### 2. Vytvoř virtuální prostředí

```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Nainstaluj závislosti

```bash
pip install -r requirements.txt
```

### 4. Nakonfiguruj aplikaci

Zkopíruj `config/env.example` jako `config/.env` a vyplň své údaje:

```bash
cp config/env.example config/.env
```

Upravte soubor `config/.env`:

```env
# Spinoco API Configuration
SPINOCO_API_KEY=your_spinoco_api_key_here
SPINOCO_BASE_URL=https://api.spinoco.com
SPINOCO_ACCOUNT_ID=your_account_id

# SharePoint Configuration
SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/yoursite
SHAREPOINT_USERNAME=your_username@yourcompany.com
SHAREPOINT_PASSWORD=your_password_or_app_password
SHAREPOINT_FOLDER_PATH=/Shared Documents/Spinoco Calls

# Application Settings
LOG_LEVEL=INFO
MAX_CONCURRENT_DOWNLOADS=5
DOWNLOAD_BATCH_SIZE=100
RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=5
```

### 5. Otestuj připojení

Před prvním spuštěním aplikace doporučujeme otestovat připojení:

```bash
py test_connection.py
```

Tento script ověří:
- ✅ Kompletnost konfigurace
- ✅ Připojení k Spinoco API
- ✅ Připojení k SharePoint (nebo lokální test)
- ✅ Vytvoření cílové složky

### 6. Test režim (doporučeno pro první spuštění)

Pro bezpečné testování nastav v `config/.env`:

```env
# Test mode - stáhni jen 5 nahrávek lokálně, nemazej ze Spinoco
TEST_MODE=true
MAX_TEST_RECORDINGS=5
LOCAL_DOWNLOAD_PATH=./test_recordings
```

Pak spusť:

```bash
py -m src.main
```

**Test režim:**
- ✅ Stáhne jen 5 nejstarších nahrávek
- ✅ Uloží lokálně do `./test_recordings/`
- ✅ NEMAZÁŽE ze Spinoco
- ✅ Zkontroluje velikosti souborů
- ✅ Vytvoří strukturu složek podle měsíců

### 7. Produkční režim

Po úspěšném testu nastav:

```env
TEST_MODE=false
```

A spusť produkční verzi:

```bash
py -m src.main
```

## ⚙️ Konfigurace

### Proměnné prostředí

| Proměnná | Popis | Výchozí hodnota |
|----------|-------|----------------|
| `SPINOCO_API_KEY` | API klíč ze Spinoco | **povinné** |
| `SPINOCO_BASE_URL` | URL Spinoco API | `https://api.spinoco.com` |
| `SHAREPOINT_SITE_URL` | URL SharePoint site | **povinné** |
| `SHAREPOINT_USERNAME` | SharePoint username | **povinné** |
| `SHAREPOINT_PASSWORD` | SharePoint heslo | **povinné** |
| `SHAREPOINT_FOLDER_PATH` | Cesta ke složce na SharePoint | `/Shared Documents/Spinoco Calls` |
| `LOG_LEVEL` | Úroveň logování | `INFO` |
| `MAX_CONCURRENT_DOWNLOADS` | Max. paralelních stahování | `5` |
| `DOWNLOAD_BATCH_SIZE` | Velikost dávky | `100` |

### Template pro názvy souborů

Aplikace podporuje template systém pro názvy souborů podobný oficiálnímu Spinoco connectoru:

```python
# Příklad template
"{{due_date|yyyyMMddHHmmss}}-{{task_id}}"
```

**Podporované placeholdery:**
- `{{due_date|format}}` - datum s formátováním (Java formát)
- `{{task_id}}` - ID úkolu
- `{{call_from}}` - číslo volajícího
- `{{call_to}}` - číslo volaného

**Automatické přípony:**
- `.ogg` - nahrávky hovorů
- `.trans.json` - transkripty
- `.meta.json` - metadata

## 📊 Výstupní soubory

### 1. Nahrávky (`.ogg`)
Binární audio soubory v open-source Ogg Vorbis formátu.

### 2. Transkripty (`.trans.json`)
```json
{
  "recordingId": "52e382d6-d34d-11eb-ab26-2348089bd31c",
  "transcription": [
    {
      "id": "52e382d6-d34d-11eb-ab26-2348089bd31c",
      "endpoint": {"__tpe": "ContactEndPoint"},
      "recognized": [
        {
          "offset": 8200000,
          "duration": 26400000,
          "displayText": "Dobrý den, jak vám mohu pomoci?",
          "alternatives": []
        }
      ]
    }
  ]
}
```

### 3. Metadata (`.meta.json`)
```json
{
  "task_id": "52e382d6-d34d-11eb-ab26-2348089bd31c",
  "last_update": 1624361479364,
  "task_type": "CallSessionTask",
  "direction": "Terminating",
  "phone_numbers": {
    "caller": "+420123456789",
    "callee": "+420987654321"
  },
  "result": [...],
  "hashtags": [...],
  "export_timestamp": 1640995200000
}
```

## 🔄 Jak to funguje

1. **Inicializace** - Aplikace se připojí ke Spinoco API a SharePoint
2. **Načtení stavu** - Pokračuje od posledního úspěšného běhu
3. **Získání úkolů** - Stáhne nové/změněné hovory ze Spinoco
4. **Zpracování v dávkách** - Paralelně zpracovává hovory
5. **Stahování souborů** - Stáhne nahrávky a transkripty
6. **Upload na SharePoint** - Nahraje soubory do správné složkové struktury
7. **Uložení stavu** - Uloží pokrok pro další běh

## 📝 Logování

Aplikace používá strukturované logování s barevným výstupem:

```
2024-01-15 10:30:00 [INFO] 🚀 Spouštím Spinoco Download aplikaci
2024-01-15 10:30:01 [INFO] ✅ Klienti úspěšně inicializováni
2024-01-15 10:30:02 [INFO] 📞 Zpracovávám hovor task_id=52e382d6-d34d-11eb-ab26-2348089bd31c
2024-01-15 10:30:03 [INFO] ⬇️ Stahuji nahrávku recording_id=93efca85-808b-11e9-b0d5-17306d0fc297
2024-01-15 10:30:05 [INFO] ✅ Nahrávka úspěšně nahrána filename=20240115103000-52e382d6.ogg size_mb=2.4
```

Log soubory jsou uloženy ve složce `logs/`.

## 🔧 API Reference

### SpinocoClient

Implementuje [Spinoco Call and Chat Transcription API](https://help.spinoco.com/):

```python
async with SpinocoClient(api_token="your_token") as client:
    # Získej hovory od určitého času
    async for task in client.get_tasks_since(since_timestamp=1640995200000):
        # Zpracuj hovor
        recordings = await client.get_call_recordings(task)
        
        for recording in recordings:
            # Stáhni nahrávku
            audio_data = await client.download_recording(task.id, recording.id)
            
            # Stáhni transkript
            transcript = await client.download_transcription(task.id, recording.id)
```

### SharePointClient

Klient pro SharePoint Online:

```python
async with SharePointClient(
    site_url="https://company.sharepoint.com/sites/site",
    username="user@company.com",
    password="password"
) as client:
    # Nahraj soubor
    await client.upload_file(
        file_content=audio_data,
        filename="recording.ogg",
        folder_path="/Shared Documents/Calls"
    )
```

## 🧪 Testování

### Rychlý test připojení

```bash
# Test konfigurace a připojení
python test_connection.py
```

### Jednotkové testy

```bash
# Spusť všechny testy
python -m pytest tests/

# Spusť s coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## 📈 Monitoring a metriky

Aplikace poskytuje detailní statistiky:

```
📊 Finální statistiky synchronizace
duration: 0:05:23
tasks_processed: 150
recordings_downloaded: 142
transcriptions_downloaded: 89
files_uploaded: 381
errors: 0
```

## 🔒 Bezpečnost

- **API klíče** jsou načítány z environment variables
- **Hesla** nejsou logována ani ukládána v plain textu
- **HTTPS** komunikace s Spinoco API i SharePoint
- **Retry logika** s exponential backoff
- **Rate limiting** pro API calls

## 🚨 Troubleshooting

### Časté problémy

**1. Chyba autentifikace Spinoco**
```
❌ HTTP chyba při získávání úkolů status_code=401
```
→ Zkontroluj `SPINOCO_API_KEY` v `.env` souboru

**2. SharePoint connection failed**
```
❌ Chyba při připojení k SharePoint
```
→ Zkontroluj URL, username a heslo pro SharePoint

**3. Nahrávka není dostupná**
```
⏳ Nahrávka ještě není dostupná
```
→ Nahrávka se ještě zpracovává ve Spinoco, zkus později

### Debug režim

Pro detailní logování nastav:
```env
LOG_LEVEL=DEBUG
```

## 🤝 Přispívání

1. Fork projekt
2. Vytvoř feature branch (`git checkout -b feature/nova-funkcnost`)
3. Commitni změny (`git commit -am 'Přidej novou funkcnost'`)
4. Push do branch (`git push origin feature/nova-funkcnost`)
5. Vytvoř Pull Request

## 📄 Licence

MIT License - viz [LICENSE](LICENSE) soubor.

## 🙏 Poděkování

- **Spinoco** za poskytnutí API dokumentace a oficiálního connectoru
- **Microsoft** za SharePoint API
- **Python community** za skvělé knihovny

## 📞 Podpora

Pro podporu a dotazy:
- 📧 Email: your.email@company.com
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/spinoco-download/issues)
- 📖 Dokumentace: [Wiki](https://github.com/your-username/spinoco-download/wiki)

---

**Vytvořeno s ❤️ pro efektivní správu hovorových dat**
